"""Storage proofs for the heartbeat record.

The certificate signs a block hash and a state root. Instead of trusting an RPC
node's eth_call for the value of the `heartbeat` text record at that block, we
fetch an eth_getProof for the resolver's storage slots and verify the Merkle
Patricia proofs locally against the signed state root:

    state root -> account leaf of the resolver (nonce, balance, storageRoot, codeHash)
    storageRoot -> the record's slot(s)

Two storage layouts are known and tried in turn, and the layout is accepted only
if its proven value equals the value the resolver itself returns through
resolve(name, data) at the same block.

ENS permissioned resolver, Sepolia beta implementation 0x14f09fd0..cf243
(contracts-v2 commit 71a3b73), plain storage after the access-control slots:
    slot 259  mapping(bytes32 node => uint256 recordId) _recordIds
    slot 260  mapping(uint256 recordId => Record) _records
    Record { bytes contenthash; string name; mapping addresses; mapping texts; ... }
    so texts sits at struct offset 3, and
    texts[key] = keccak(bytes(key) . (keccak(recordId . 260) + 3))
Found by tracing one resolve() call on an Anvil fork of Sepolia and confirmed
against the on-chain values of heartbeat, heir and sealed. See NOTES.md.

MockResolver (our Foundry test double, Anvil):
    slot 2    mapping(bytes32 node => mapping(bytes32 keyHash => string)) records
    records[node][keccak(key)] = keccak(keccak(key) . keccak(node . 2))
"""
from __future__ import annotations

import math

import rlp
from eth_utils import keccak
from trie import HexaryTrie
from web3 import Web3

ENS_BETA_RECORD_IDS_SLOT = 259
ENS_BETA_RECORDS_SLOT = 260
ENS_BETA_TEXTS_OFFSET = 3
MOCK_RECORDS_SLOT = 2


class ProofError(Exception):
    pass


def e32(x: int) -> bytes:
    return x.to_bytes(32, "big")


def h(*parts: bytes) -> int:
    return int.from_bytes(keccak(b"".join(parts)), "big")


# ------------------------------------------------------------------ slot derivation

def ens_beta_record_id_slot(node: bytes) -> int:
    return h(node, e32(ENS_BETA_RECORD_IDS_SLOT))


def ens_beta_text_slot(record_id: int, key: str) -> int:
    base = h(e32(record_id), e32(ENS_BETA_RECORDS_SLOT))
    return h(key.encode(), e32(base + ENS_BETA_TEXTS_OFFSET))


def mock_text_slot(node: bytes, key: str) -> int:
    inner = keccak(node + e32(MOCK_RECORDS_SLOT))
    return h(keccak(key.encode()), inner)


def long_string_data_slots(slot: int, length: int) -> list[int]:
    start = h(e32(slot))
    return [start + i for i in range(math.ceil(length / 32))]


# ------------------------------------------------------------------ proof verification

def _raw_nodes(proof) -> list:
    return [rlp.decode(bytes(n)) for n in proof]


def verify_account(address: str, state_root: bytes, account_proof) -> dict:
    """Prove the resolver's account leaf against the state root. Returns its storage root."""
    key = keccak(bytes.fromhex(address[2:]))
    leaf = HexaryTrie.get_from_proof(state_root, key, _raw_nodes(account_proof))
    if not leaf:
        raise ProofError("resolver account absent from the proven state")
    nonce, balance, storage_root, code_hash = rlp.decode(leaf)
    return {"storage_root": bytes(storage_root), "code_hash": bytes(code_hash), "nodes": len(account_proof)}


def verify_storage(storage_root: bytes, slot: int, proof) -> int:
    """Prove one storage slot against the storage root. Absent slots prove as zero."""
    key = keccak(e32(slot))
    leaf = HexaryTrie.get_from_proof(storage_root, key, _raw_nodes(proof))
    if not leaf:
        return 0
    return int.from_bytes(rlp.decode(leaf), "big")


def decode_solidity_string(main: int, data_words: list[int] | None = None) -> tuple[str | None, int | None]:
    """Short strings live in the slot, last byte = 2*len. Long strings keep 2*len+1 in the
    slot and the bytes in keccak(slot)+i. Returns (value, needed_length) where value is None
    when the data words are still required."""
    raw = e32(main)
    if main == 0:
        return "", None
    if raw[-1] % 2 == 0:
        n = raw[-1] // 2
        return raw[:n].decode(), None
    length = (main - 1) // 2
    if data_words is None:
        return None, length
    data = b"".join(e32(w) for w in data_words)[:length]
    return data.decode(), length


# ------------------------------------------------------------------ the check

def prove_text(w3: Web3, resolver: str, node: bytes, key: str, block_number: int, state_root: bytes,
               expected: str | None = None) -> dict:
    """Prove the text record `key` of `node` on `resolver` at `block_number` against `state_root`.
    Tries the known layouts and accepts the one whose proven value matches `expected`
    (the value resolve() returned) when given."""
    addr = Web3.to_checksum_address(resolver)
    header = w3.eth.get_block(block_number)
    if bytes(header["stateRoot"]) != state_root:
        raise ProofError(f"header state root at block {block_number} differs from the certificate")

    candidates = []
    rid_slot = ens_beta_record_id_slot(node)
    rid = int.from_bytes(bytes(w3.eth.get_storage_at(addr, rid_slot, block_identifier=block_number)), "big")
    if rid:
        candidates.append(("ens-beta", [rid_slot, ens_beta_text_slot(rid, key)], rid))
    candidates.append(("mock", [mock_text_slot(node, key)], None))

    errors = []
    for layout, slots, want_rid in candidates:
        try:
            proof = w3.eth.get_proof(addr, slots, block_identifier=block_number)
            acct = verify_account(addr, state_root, proof["accountProof"])
            if bytes(proof["storageHash"]) != acct["storage_root"]:
                raise ProofError("storageHash in the response differs from the proven account leaf")
            values = [verify_storage(acct["storage_root"], s, sp["proof"]) for s, sp in zip(slots, proof["storageProof"])]
            storage_nodes = sum(len(sp["proof"]) for sp in proof["storageProof"])
            if want_rid is not None and values[0] != want_rid:
                raise ProofError("proven recordId differs from the one read")
            main = values[-1]
            value, length = decode_solidity_string(main)
            if value is None:  # long string, prove its data words too
                data_slots = long_string_data_slots(slots[-1], length)
                p2 = w3.eth.get_proof(addr, data_slots, block_identifier=block_number)
                if bytes(p2["storageHash"]) != acct["storage_root"]:
                    raise ProofError("storageHash changed between proofs")
                words = [verify_storage(acct["storage_root"], s, sp["proof"]) for s, sp in zip(data_slots, p2["storageProof"])]
                storage_nodes += sum(len(sp["proof"]) for sp in p2["storageProof"])
                value, _ = decode_solidity_string(main, words)
                slots = slots + data_slots
            if expected is not None and value != expected:
                raise ProofError(f"proven value {value!r} differs from resolve() value {expected!r}")
            return {"layout": layout, "slots": [hex(s) for s in slots], "value": value,
                    "account_nodes": acct["nodes"], "storage_nodes": storage_nodes,
                    "state_root": "0x" + state_root.hex(), "block_number": block_number}
        except Exception as ex:  # try the next layout
            errors.append(f"{layout}: {type(ex).__name__} {str(ex)[:80]}")
    raise ProofError("; ".join(errors))
