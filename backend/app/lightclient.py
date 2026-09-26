"""Mock light client.

Stands in for a finality proof on Anvil. Four demo signers attest to the
checkpoint at each demo-epoch boundary, three signatures required. On Sepolia
the same interface would be backed by the beacon chain's finalized checkpoint.
The relation checker treats the certificate as the "finalized descendant" in
the four opening conditions.
"""
from __future__ import annotations

from eth_account import Account
from eth_keys import keys
from eth_utils import keccak

from .chain import Chain

PREFIX = b"SEALED-FINALITY-V1"


def checkpoint_message(epoch: int, block_hash: str, state_root: str) -> bytes:
    return keccak(PREFIX + epoch.to_bytes(8, "big") + bytes.fromhex(block_hash[2:]) + bytes.fromhex(state_root[2:]))


def recover(msg_hash: bytes, sig: bytes) -> str:
    v = sig[64]
    v = v - 27 if v >= 27 else v
    s = keys.Signature(signature_bytes=sig[:64] + bytes([v]))
    return s.recover_public_key_from_msg_hash(msg_hash).to_checksum_address()


class MockLightClient:
    threshold = 3

    def __init__(self, chain: Chain, signer_keys: list[str], blocks_per_epoch: int, lag_epochs: int = 1):
        self.chain = chain
        self.signers = [Account.from_key(k) for k in signer_keys]
        self.signer_addresses = [a.address for a in self.signers]
        self.bpe = blocks_per_epoch
        self.lag = lag_epochs

    def current_epoch(self) -> int:
        return self.chain.block_number() // self.bpe

    def finalized(self, at_epoch: int | None = None) -> dict:
        """Certificate for the boundary block of the latest finalized demo epoch,
        or for an explicit earlier epoch (used by the wrong-witness demo)."""
        if at_epoch is not None:
            epoch = at_epoch
        elif self.chain.is_anvil():
            epoch = self.current_epoch() - self.lag  # Anvil has no finality, emulate a fixed lag
        else:
            # A real chain: certify the block the consensus layer has actually finalized, and
            # name its epoch. Using that block rather than the epoch boundary keeps the state
            # proofs within the ~128 blocks of history public RPC nodes keep.
            fin = self.chain.block("finalized")
            return self._certificate(fin["number"] // self.bpe, fin)
        epoch = max(epoch, 0)
        blk = self.chain.block(epoch * self.bpe)
        return self._certificate(epoch, blk)

    def _certificate(self, epoch: int, blk: dict) -> dict:
        msg = checkpoint_message(epoch, blk["hash"], blk["state_root"])
        sigs = [self.signers[i].unsafe_sign_hash(msg).signature.hex() for i in range(self.threshold)]
        return {
            "epoch": epoch,
            "block_number": blk["number"],
            "block_hash": blk["hash"],
            "state_root": blk["state_root"],
            "timestamp": blk["timestamp"],
            "signatures": ["0x" + s if not s.startswith("0x") else s for s in sigs],
        }

    def verify(self, cert: dict) -> tuple[bool, str]:
        msg = checkpoint_message(int(cert["epoch"]), cert["block_hash"], cert["state_root"])
        seen = set()
        for s in cert.get("signatures", []):
            try:
                addr = recover(msg, bytes.fromhex(s[2:]))
            except Exception:
                continue
            if addr in self.signer_addresses:
                seen.add(addr)
        ok = len(seen) >= self.threshold
        # the certificate must also describe a real block on this chain
        try:
            blk = self.chain.block(cert["block_hash"])
            same = blk["number"] == int(cert["block_number"]) and blk["state_root"] == cert["state_root"]
        except Exception:
            same = False
        detail = f"{len(seen)} of {len(self.signer_addresses)} signers valid, block {'matches' if same else 'unknown'}"
        return ok and same, detail
