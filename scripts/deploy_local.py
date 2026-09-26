"""Deploy the demo to a local Anvil node with the MockResolver standing in for
the ENSv2 permissioned resolver, then write backend/.env.local.

Usage (from repo root, backend venv):
    python scripts/deploy_local.py [--rpc http://127.0.0.1:8545]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from eth_account import Account  # noqa: E402
from eth_utils import keccak  # noqa: E402
from web3 import Web3  # noqa: E402

from app.chain import Chain  # noqa: E402
from app.config import load_keys, settings  # noqa: E402
from app.names import dns_encode, namehash  # noqa: E402

ETH = 10**18


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", default=settings.rpc_url)
    a = ap.parse_args()

    keys = load_keys()
    chain = Chain(a.rpc, ROOT / "contracts" / "out")
    if not chain.is_anvil():
        sys.exit(f"deploy_local.py only runs against Anvil, refusing {a.rpc}. For Sepolia use scripts/sepolia-all.sh.")
    owner = Account.from_key(keys["owner"])
    checker = Account.from_key(keys["checker"])
    watchtower = Account.from_key(keys["watchtower"])
    for acct in (owner, watchtower):
        chain.set_balance(acct.address, 100 * ETH)

    owner_dns = dns_encode(settings.owner_name)
    owner_node = namehash(settings.owner_name)
    heir_node = namehash(settings.heir_name)

    resolver = chain.deploy("MockResolver", keys["owner"])
    R = chain.contract("MockResolver", resolver)
    chain.send(R.functions.setOwner(owner_node, owner.address), keys["owner"])
    chain.send(R.functions.setOwner(heir_node, owner.address), keys["owner"])  # demo: owner manages both names locally

    studio = chain.deploy("Studio", keys["owner"], owner.address, owner_dns, resolver, settings.blocks_per_epoch)
    opener = chain.deploy("Opener", keys["owner"], checker.address, resolver)

    # scoped grants, mirroring grantSetterRoles on ENSv2
    for key in ("heartbeat", "sealed"):
        chain.send(R.functions.grantSetter(owner_node, key, studio, True), keys["owner"])
    chain.send(R.functions.grantSetter(owner_node, "disclosure", opener, True), keys["owner"])

    # owner-written records
    chain.send(R.functions.setText(owner_dns, "heir", settings.heir_name), keys["owner"])
    chain.send(R.functions.setText(owner_dns, "vault", studio), keys["owner"])
    chain.send(R.functions.setText(dns_encode(settings.heir_name), "pubkey.x25519", "0x" + keys["heir_x25519_pk"]), keys["owner"])

    chain.set_balance(studio, 10 * ETH)

    # the name itself: a registry double holds the owner's name token, the owner approves the
    # Opener as operator and plans the handover to the heir, exactly the ENSv2 flow on Sepolia
    registry = chain.deploy("MockRegistry", keys["owner"])
    G = chain.contract("MockRegistry", registry)
    token_id = int.from_bytes(keccak(text=settings.owner_name.split(".")[0]), "big")
    heir = Account.from_key(keys["heir_eth"]).address
    chain.send(G.functions.mint(owner.address, token_id), keys["owner"])
    chain.send(G.functions.setApprovalForAll(opener, True), keys["owner"])
    chain.send(chain.contract("Opener", opener).functions.setHandover(owner_dns, registry, token_id, heir), keys["owner"])

    env = ROOT / "backend" / ".env.local"
    env.write_text(
        f"RPC_URL={a.rpc}\nCHAIN_ID={chain.chain_id}\nRESOLVER={resolver}\nSTUDIO={studio}\nOPENER={opener}\n"
        f"BLOCKS_PER_EPOCH={settings.blocks_per_epoch}\nWINDOW_EPOCHS={settings.window_epochs}\n"
        f"HORIZON_EPOCHS={settings.horizon_epochs}\nLOCK_SECONDS={settings.lock_seconds}\n"
        f"REGISTRY={registry}\nNAME_TOKEN_ID={hex(token_id)}\n"
    )
    print(f"resolver  {resolver}\nstudio    {studio}\nopener    {opener}\nregistry  {registry}  token {hex(token_id)[:12]}… owned by owner, handover planned to {heir}")
    print(f"owner     {owner.address}\nchecker   {checker.address}\nwatchtower {watchtower.address}")
    print(f"vault balance {Web3.from_wei(chain.w3.eth.get_balance(Web3.to_checksum_address(studio)), 'ether')} ETH")
    print(f"wrote {env}")


if __name__ == "__main__":
    main()
