"""Wire the ENSv2 name handover on Sepolia: a new Opener that, at the first opening,
moves yutotanaka.eth from the owner to the heir. Run from the repo root in WSL.

    ~/eth-tokyo/venv/bin/python scripts/sepolia_handover.py check    # read-only: token id, owner, approval, handover plan
    ~/eth-tokyo/venv/bin/python scripts/sepolia_handover.py deploy   # new Opener + disclosure setter role, updates .env.sepolia and docs/config.json
    ~/eth-tokyo/venv/bin/python scripts/sepolia_handover.py approve  # owner approves the Opener as operator on the ETHRegistry
    ~/eth-tokyo/venv/bin/python scripts/sepolia_handover.py plan     # owner calls Opener.setHandover(name, registry, tokenId, heir)
    ~/eth-tokyo/venv/bin/python scripts/sepolia_handover.py all      # deploy, approve, plan, check

Reads backend/.env.sepolia itself (file values win over the shell environment, so a
stale OPENER exported earlier cannot leak in). Keys come from backend/.demo-keys.json.
The RPC_URL is never printed.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "backend" / ".env.sepolia"
CONFIG_JSON = ROOT / "docs" / "config.json"
SEPOLIA = 11155111
ZERO = "0x0000000000000000000000000000000000000000"


def load_env_file() -> None:
    if not ENV_FILE.exists():
        sys.exit(f"missing {ENV_FILE}")
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()


load_env_file()
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from eth_account import Account  # noqa: E402
from web3 import Web3  # noqa: E402

from app.chain import Chain  # noqa: E402
from app.config import load_keys, settings  # noqa: E402
from app.names import dns_encode, namehash  # noqa: E402
from ens_sepolia import ETH_REGISTRY, cs, find_resolver, resolver_contract  # noqa: E402

# Shapes checked against the ETHRegistry ABI (notes/ETHRegistry.json) and on chain.
REGISTRY_ABI = [
    {"type": "function", "name": "getTokenId", "stateMutability": "view",
     "inputs": [{"name": "anyId", "type": "uint256"}], "outputs": [{"name": "", "type": "uint256"}]},
    {"type": "function", "name": "ownerOf", "stateMutability": "view",
     "inputs": [{"name": "tokenId", "type": "uint256"}], "outputs": [{"name": "", "type": "address"}]},
    {"type": "function", "name": "isApprovedForAll", "stateMutability": "view",
     "inputs": [{"name": "account", "type": "address"}, {"name": "operator", "type": "address"}],
     "outputs": [{"name": "", "type": "bool"}]},
    {"type": "function", "name": "setApprovalForAll", "stateMutability": "nonpayable",
     "inputs": [{"name": "operator", "type": "address"}, {"name": "approved", "type": "bool"}], "outputs": []},
]


def txh(rcpt) -> str:
    return Web3.to_hex(rcpt["transactionHash"])


def registry(c: Chain):
    return c.w3.eth.contract(address=cs(ETH_REGISTRY), abi=REGISTRY_ABI)


def token_id_of(c: Chain, name: str) -> int:
    """anyId = uint256(keccak256(label)), the registry maps it to the current token id."""
    any_id = int.from_bytes(Web3.keccak(text=name.split(".")[0]), "big")
    return registry(c).functions.getTokenId(any_id).call()


def read_handover(c: Chain, opener: str):
    """The handover(node) tuple, or None when this Opener predates handover."""
    try:
        return c.contract("Opener", opener).functions.handover(namehash(settings.owner_name)).call()
    except Exception as e:
        print(f"  handover() not available on Opener {opener} (old version): {type(e).__name__}")
        return None


def fmt_handover(h) -> str:
    if h[0] == ZERO:
        return "not configured (registry 0x0)"
    return f"registry {h[0]}, tokenId 0x{h[1]:064x}, owner {h[2]}, heir {h[3]}"


def check(c: Chain, keys: dict, opener: str) -> None:
    reg = registry(c)
    owner = Account.from_key(keys["owner"]).address
    heir = Account.from_key(keys["heir_eth"]).address
    token_id = token_id_of(c, settings.owner_name)
    current = reg.functions.ownerOf(token_id).call()
    approved = reg.functions.isApprovedForAll(current, cs(opener)).call()
    print(f"check {settings.owner_name} on ETHRegistry {ETH_REGISTRY}")
    print(f"  token id   0x{token_id:064x}")
    print(f"  ownerOf    {current}  ({'the demo owner' if current == owner else 'NOT the demo owner ' + owner})")
    print(f"  heir       {heir}  ({settings.heir_name}, keys['heir_eth'])")
    print(f"  opener     {opener} approved as operator by {current}: {approved}")
    h = read_handover(c, opener)
    if h is not None:
        print(f"  handover   {fmt_handover(h)}")


def grant_disclosure(c: Chain, opener: str, owner_hex: str) -> None:
    """Same steps as ens_sepolia.grant for the single key `disclosure`."""
    found = find_resolver(c, settings.owner_name)
    if found.lower() != settings.resolver.lower():
        print(f"  note: RESOLVER in env is {settings.resolver}, the name resolves through {found}; granting on the latter")
    R = resolver_contract(c, found)
    setter = bytes.fromhex(R.encode_abi("setText", args=[b"", "disclosure", ""])[2:])
    _, resource, bitmap = R.functions.decodeSetter(setter).call()
    rcpt = c.send(R.functions.grantSetterRoles(setter, cs(opener)), owner_hex)
    ok = R.functions.hasRoles(resource, bitmap, cs(opener)).call()
    print(f"  granted setText[disclosure] (resource 0x{resource:x}, roles 0x{bitmap:x}) to {opener}: hasRoles {ok} tx {txh(rcpt)}")
    if not ok:
        sys.exit("  role grant did not take, stopping")


def update_env(opener: str) -> None:
    lines = ENV_FILE.read_text().splitlines()
    keep = [ln for ln in lines if not ln.startswith("OPENER=")]
    idx = next((i for i, ln in enumerate(lines) if ln.startswith("OPENER=")), len(keep))
    keep.insert(idx, f"OPENER={opener}")
    ENV_FILE.write_text("\n".join(keep) + "\n")
    print(f"  {ENV_FILE.relative_to(ROOT)}: OPENER={opener}")


def update_config(opener: str) -> None:
    cfg = json.loads(CONFIG_JSON.read_text())
    cfg["opener"] = opener
    CONFIG_JSON.write_text(json.dumps(cfg, indent=2))
    print(f"  {CONFIG_JSON.relative_to(ROOT)}: opener={opener}")


def deploy(c: Chain, keys: dict) -> str:
    checker = Account.from_key(keys["checker"]).address
    old = settings.opener
    print(f"deploy Opener(checker {checker}, resolver {settings.resolver}) from the owner")
    art = c._artifact("Opener")  # same as Chain.deploy, kept inline so the tx hash can be printed
    C = c.w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"]["object"])
    rcpt = c.send(C.constructor(checker, cs(settings.resolver)), keys["owner"])
    new = rcpt["contractAddress"]
    print(f"  old Opener {old}\n  new Opener {new} tx {txh(rcpt)}")
    grant_disclosure(c, new, keys["owner"])
    update_env(new)
    update_config(new)
    return new


def approve(c: Chain, keys: dict, opener: str) -> None:
    owner = Account.from_key(keys["owner"]).address
    print(f"approve Opener {opener} as operator for {owner} on ETHRegistry {ETH_REGISTRY}")
    if read_handover(c, opener) is None:
        print("  warning: this Opener cannot hand over, run deploy first")
    rcpt = c.send(registry(c).functions.setApprovalForAll(cs(opener), True), keys["owner"])
    ok = registry(c).functions.isApprovedForAll(owner, cs(opener)).call()
    print(f"  setApprovalForAll tx {txh(rcpt)}; isApprovedForAll {ok}")


def plan(c: Chain, keys: dict, opener: str) -> None:
    heir = Account.from_key(keys["heir_eth"]).address
    token_id = token_id_of(c, settings.owner_name)
    print(f"plan handover of {settings.owner_name} (token 0x{token_id:064x}) to {heir} on Opener {opener}")
    if read_handover(c, opener) is None:
        sys.exit("  this Opener has no setHandover, run deploy first")
    O = c.contract("Opener", opener)
    rcpt = c.send(O.functions.setHandover(dns_encode(settings.owner_name), cs(ETH_REGISTRY), token_id, heir), keys["owner"])
    print(f"  setHandover tx {txh(rcpt)}")
    print(f"  handover   {fmt_handover(read_handover(c, opener))}")


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "help"
    if cmd not in ("check", "deploy", "approve", "plan", "all"):
        print(__doc__)
        sys.exit(1)
    keys = load_keys()
    c = Chain(settings.rpc_url, ROOT / "contracts" / "out")
    print(f"chain {c.chain_id}, block {c.block_number()}; RESOLVER {settings.resolver}, OPENER {settings.opener}, "
          f"{settings.owner_name} -> {settings.heir_name}")
    if c.chain_id != SEPOLIA:
        sys.exit(f"expected Sepolia ({SEPOLIA}), refusing to continue")
    opener = settings.opener
    if cmd == "check":
        check(c, keys, opener)
    elif cmd == "deploy":
        deploy(c, keys)
    elif cmd == "approve":
        approve(c, keys, opener)
    elif cmd == "plan":
        plan(c, keys, opener)
    else:
        opener = deploy(c, keys)
        approve(c, keys, opener)
        plan(c, keys, opener)
        check(c, keys, opener)


if __name__ == "__main__":
    main(sys.argv[1:])
