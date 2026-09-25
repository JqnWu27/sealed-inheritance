"""ENSv2 Sepolia beta helper. Every command is one small step you can run and read.

    RPC_URL=... python scripts/ens_sepolia.py resolver yutotanaka.eth
    RPC_URL=... python scripts/ens_sepolia.py deploy-resolver            # Yuto's own permissioned resolver
    RPC_URL=... python scripts/ens_sepolia.py set-resolver yutotanaka.eth 0x...  # point the name at it
    RPC_URL=... python scripts/ens_sepolia.py records yutotanaka.eth hana.eth 0xStudio
    RPC_URL=... python scripts/ens_sepolia.py pubkey hana.eth
    RPC_URL=... python scripts/ens_sepolia.py grant yutotanaka.eth 0xStudio 0xOpener
    RPC_URL=... python scripts/ens_sepolia.py read yutotanaka.eth heartbeat

Addresses are the ENSv2 beta table in the ENS docs, verified against the deployed
bytecode on Sat 26 Sep, see NOTES.md. The permissioned resolver takes the
DNS-encoded name in its setters, has no bare text() getter, and answers reads
through resolve(name, data). Keys come from backend/.demo-keys.json.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from eth_account import Account  # noqa: E402
from web3 import Web3  # noqa: E402

from app.chain import Chain  # noqa: E402
from app.config import load_keys, settings  # noqa: E402
from app.names import dns_encode, namehash  # noqa: E402

UNIVERSAL_RESOLVER_V2 = "0x5d25c1d6acbb71b7a28aa7899618a3412a8303e3"
PERMISSIONED_RESOLVER_IMPL = "0x14f09fd05d4585759e54844dc9b00147131cf243"
VERIFIABLE_FACTORY = "0x9e726eb570beb6bceb495ab8cda7df517d4e841c"
ETH_REGISTRY = "0x657ea849311d3d5823348dded7c2aaafb3ede09e"

ROLE_SET_TEXT = 1 << 4
# Every role slot and every admin slot, the value the ENS docs pass to initialize for the owner.
ALL_ROLES = int("0x" + "1" * 64, 16)

UNIVERSAL_RESOLVER_ABI = [
    {"type": "function", "name": "findResolver", "stateMutability": "view",
     "inputs": [{"name": "name", "type": "bytes"}],
     "outputs": [{"name": "resolver", "type": "address"}, {"name": "node", "type": "bytes32"}, {"name": "offset", "type": "uint256"}]},
    {"type": "function", "name": "resolve", "stateMutability": "view",
     "inputs": [{"name": "name", "type": "bytes"}, {"name": "data", "type": "bytes"}],
     "outputs": [{"name": "result", "type": "bytes"}, {"name": "resolver", "type": "address"}]},
]

# Selectors checked against the bytecode at PERMISSIONED_RESOLVER_IMPL.
PERMISSIONED_RESOLVER_ABI = [
    {"type": "function", "name": "setText", "stateMutability": "nonpayable",
     "inputs": [{"name": "name", "type": "bytes"}, {"name": "key", "type": "string"}, {"name": "value", "type": "string"}], "outputs": []},
    {"type": "function", "name": "resolve", "stateMutability": "view",
     "inputs": [{"name": "name", "type": "bytes"}, {"name": "data", "type": "bytes"}], "outputs": [{"name": "", "type": "bytes"}]},
    {"type": "function", "name": "grantSetterRoles", "stateMutability": "nonpayable",
     "inputs": [{"name": "setter", "type": "bytes"}, {"name": "account", "type": "address"}], "outputs": [{"name": "", "type": "bool"}]},
    {"type": "function", "name": "revokeRoles", "stateMutability": "nonpayable",
     "inputs": [{"name": "resource", "type": "uint256"}, {"name": "roleBitmap", "type": "uint256"}, {"name": "account", "type": "address"}],
     "outputs": [{"name": "", "type": "bool"}]},
    {"type": "function", "name": "hasRoles", "stateMutability": "view",
     "inputs": [{"name": "resource", "type": "uint256"}, {"name": "roleBitmap", "type": "uint256"}, {"name": "account", "type": "address"}],
     "outputs": [{"name": "", "type": "bool"}]},
    {"type": "function", "name": "decodeSetter", "stateMutability": "view",
     "inputs": [{"name": "setter", "type": "bytes"}],
     "outputs": [{"name": "arg", "type": "bytes"}, {"name": "resource", "type": "uint256"}, {"name": "roleBitmap", "type": "uint256"}]},
    {"type": "function", "name": "initialize", "stateMutability": "nonpayable",
     "inputs": [{"name": "grants", "type": "tuple[]", "components": [{"name": "account", "type": "address"}, {"name": "roleBitmap", "type": "uint256"}]},
                {"name": "calls", "type": "bytes[]"}], "outputs": []},
]

# PublicResolverV2 style resolver, ENSv1 shape, used for Hana's name if she keeps the default.
LEGACY_RESOLVER_ABI = [
    {"type": "function", "name": "setText", "stateMutability": "nonpayable",
     "inputs": [{"name": "node", "type": "bytes32"}, {"name": "key", "type": "string"}, {"name": "value", "type": "string"}], "outputs": []},
    {"type": "function", "name": "text", "stateMutability": "view",
     "inputs": [{"name": "node", "type": "bytes32"}, {"name": "key", "type": "string"}], "outputs": [{"name": "", "type": "string"}]},
]

FACTORY_ABI = [
    {"type": "function", "name": "deployProxy", "stateMutability": "nonpayable",
     "inputs": [{"name": "implementation", "type": "address"}, {"name": "salt", "type": "uint256"}, {"name": "data", "type": "bytes"}],
     "outputs": [{"name": "", "type": "address"}]},
    {"type": "event", "name": "ProxyDeployed", "anonymous": False,
     "inputs": [{"name": "sender", "type": "address", "indexed": False}, {"name": "proxyAddress", "type": "address", "indexed": False},
                {"name": "salt", "type": "uint256", "indexed": False}, {"name": "implementation", "type": "address", "indexed": False}]},
]

REGISTRY_ABI = [
    {"type": "function", "name": "setResolver", "stateMutability": "nonpayable",
     "inputs": [{"name": "anyId", "type": "uint256"}, {"name": "resolver", "type": "address"}], "outputs": []},
    {"type": "function", "name": "getResolver", "stateMutability": "view",
     "inputs": [{"name": "label", "type": "string"}], "outputs": [{"name": "", "type": "address"}]},
    {"type": "function", "name": "ownerOf", "stateMutability": "view",
     "inputs": [{"name": "tokenId", "type": "uint256"}], "outputs": [{"name": "", "type": "address"}]},
]

TEXT_SELECTOR_ABI = [{"type": "function", "name": "text", "stateMutability": "view",
                      "inputs": [{"name": "node", "type": "bytes32"}, {"name": "key", "type": "string"}],
                      "outputs": [{"name": "", "type": "string"}]}]

RECORD_KEYS = ["heir", "vault", "heartbeat", "sealed", "disclosure"]


def chain():
    return Chain(os.environ.get("RPC_URL", settings.rpc_url), ROOT / "contracts" / "out")


def cs(a: str) -> str:
    return Web3.to_checksum_address(a)


def label_of(name: str) -> str:
    return name.split(".")[0]


def universal(c: Chain):
    return c.w3.eth.contract(address=cs(UNIVERSAL_RESOLVER_V2), abi=UNIVERSAL_RESOLVER_ABI)


def find_resolver(c: Chain, name: str) -> str:
    resolver, node, _ = universal(c).functions.findResolver(dns_encode(name)).call()
    print(f"{name}: resolver {resolver}, node 0x{node.hex()}")
    return resolver


def resolver_contract(c: Chain, addr: str):
    return c.w3.eth.contract(address=cs(addr), abi=PERMISSIONED_RESOLVER_ABI)


def text_calldata(c: Chain, node: bytes, key: str) -> bytes:
    t = c.w3.eth.contract(abi=TEXT_SELECTOR_ABI)
    return bytes.fromhex(t.encode_abi("text", args=[node, key])[2:])


def read_text(c: Chain, name: str, key: str) -> str:
    out, resolver = universal(c).functions.resolve(dns_encode(name), text_calldata(c, namehash(name), key)).call()
    value = c.w3.codec.decode(["string"], out)[0]
    print(f"{name} {key} = {value!r}  (resolver {resolver})")
    return value


def set_text(c: Chain, resolver: str, name: str, key: str, value: str, key_hex: str):
    """Write through whichever resolver shape the name has."""
    R = resolver_contract(c, resolver)
    try:
        rcpt = c.send(R.functions.setText(dns_encode(name), key, value), key_hex)
    except Exception as e:  # PublicResolverV2 shape
        print(f"  DNS-name setter failed ({str(e)[:60]}), trying the bytes32 shape")
        L = c.w3.eth.contract(address=cs(resolver), abi=LEGACY_RESOLVER_ABI)
        rcpt = c.send(L.functions.setText(namehash(name), key, value), key_hex)
    print(f"set {key} on {name} tx {Web3.to_hex(rcpt['transactionHash'])}")


def deploy_resolver(c: Chain, owner_hex: str, version: int = 0) -> str:
    """Yuto's own permissioned resolver: a UUPS proxy from the VerifiableFactory,
    initialised with every role for Yuto. Salt follows the ENS docs example."""
    owner = Account.from_key(owner_hex).address
    salt = int.from_bytes(Web3.keccak(c.w3.codec.encode(
        ["bytes32", "address", "uint256"], [Web3.keccak(text="OwnedResolver"), owner, version])), "big")
    impl = resolver_contract(c, PERMISSIONED_RESOLVER_IMPL)
    init = impl.encode_abi("initialize", args=[[(owner, ALL_ROLES)], []])
    F = c.w3.eth.contract(address=cs(VERIFIABLE_FACTORY), abi=FACTORY_ABI)
    rcpt = c.send(F.functions.deployProxy(cs(PERMISSIONED_RESOLVER_IMPL), salt, bytes.fromhex(init[2:])), owner_hex)
    logs = F.events.ProxyDeployed().process_receipt(rcpt)
    proxy = logs[0]["args"]["proxyAddress"] if logs else "(see receipt)"
    print(f"deployed permissioned resolver for {owner}: {proxy} tx {Web3.to_hex(rcpt['transactionHash'])}")
    return proxy


def set_resolver(c: Chain, name: str, resolver: str, owner_hex: str):
    label = label_of(name)
    Rg = c.w3.eth.contract(address=cs(ETH_REGISTRY), abi=REGISTRY_ABI)
    before = Rg.functions.getResolver(label).call()
    token_id = int.from_bytes(Web3.keccak(text=label), "big")
    rcpt = c.send(Rg.functions.setResolver(token_id, cs(resolver)), owner_hex)
    after = Rg.functions.getResolver(label).call()
    print(f"{name}: resolver {before} -> {after} tx {Web3.to_hex(rcpt['transactionHash'])}")


def grant(c: Chain, name: str, studio: str, opener: str, owner_hex: str):
    """Scoped setter roles: Studio may write heartbeat and sealed, Opener may write disclosure."""
    R = resolver_contract(c, find_resolver(c, name))
    for key, account in (("heartbeat", studio), ("sealed", studio), ("disclosure", opener)):
        # The setter calldata names the function and the key. Name and value are ignored by decodeSetter.
        setter = bytes.fromhex(R.encode_abi("setText", args=[b"", key, ""])[2:])
        arg, resource, bitmap = R.functions.decodeSetter(setter).call()
        rcpt = c.send(R.functions.grantSetterRoles(setter, cs(account)), owner_hex)
        ok = R.functions.hasRoles(resource, bitmap, cs(account)).call()
        print(f"granted setText[{key}] (resource 0x{resource:x}, roles 0x{bitmap:x}) to {account}: hasRoles {ok} tx {Web3.to_hex(rcpt['transactionHash'])}")


def main(argv: list[str]):
    cmd = argv[0]
    keys = load_keys()
    c = chain()
    print(f"chain {c.chain_id}, block {c.block_number()}")
    if cmd == "resolver":
        find_resolver(c, argv[1])
    elif cmd == "deploy-resolver":
        deploy_resolver(c, keys["owner"], int(argv[1]) if len(argv) > 1 else 0)
    elif cmd == "set-resolver":
        set_resolver(c, argv[1], argv[2], keys["owner"])
    elif cmd == "records":
        name, heir, vault = argv[1], argv[2], argv[3]
        resolver = find_resolver(c, name)
        set_text(c, resolver, name, "heir", heir, keys["owner"])
        set_text(c, resolver, name, "vault", vault, keys["owner"])
    elif cmd == "pubkey":
        heir = argv[1]
        set_text(c, find_resolver(c, heir), heir, "pubkey.x25519", "0x" + keys["heir_x25519_pk"], keys.get("heir_eth", keys["owner"]))
    elif cmd == "grant":
        grant(c, argv[1], argv[2], argv[3], keys["owner"])
    elif cmd == "read":
        name = argv[1]
        for key in (argv[2:] or RECORD_KEYS):
            read_text(c, name, key)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:] or ["help"])
