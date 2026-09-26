"""Deploy Studio and Opener to Sepolia against the owner name's ENSv2 resolver.

    RPC_URL=https://... python scripts/deploy_sepolia.py --resolver 0x... [--owner-name yutotanaka.eth]

Writes backend/.env.sepolia. Then grant the scoped roles with scripts/ens_sepolia.py grant.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from eth_account import Account  # noqa: E402
from web3 import Web3  # noqa: E402

from app.chain import Chain  # noqa: E402
from app.config import load_keys, settings  # noqa: E402
from app.names import dns_encode  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolver", required=True)
    ap.add_argument("--owner-name", default=settings.owner_name)
    ap.add_argument("--blocks-per-epoch", type=int, default=32)  # one mainnet-style epoch = 32 blocks on Sepolia
    a = ap.parse_args()

    rpc = os.environ.get("RPC_URL")
    if not rpc:
        sys.exit("set RPC_URL")
    keys = load_keys()
    chain = Chain(rpc, ROOT / "contracts" / "out")
    owner = Account.from_key(keys["owner"])
    checker = Account.from_key(keys["checker"])
    bal = chain.w3.eth.get_balance(owner.address)
    print(f"owner {owner.address} balance {Web3.from_wei(bal, 'ether')} ETH on chain {chain.chain_id}")
    if bal < Web3.to_wei(0.05, "ether"):
        sys.exit("fund the owner address first")

    studio = chain.deploy("Studio", keys["owner"], owner.address, dns_encode(a.owner_name), Web3.to_checksum_address(a.resolver), a.blocks_per_epoch)
    print(f"Studio  {studio}")
    opener = chain.deploy("Opener", keys["owner"], checker.address, Web3.to_checksum_address(a.resolver))
    print(f"Opener  {opener}")

    env = ROOT / "backend" / ".env.sepolia"
    env.write_text(
        f"RPC_URL={rpc}\nCHAIN_ID={chain.chain_id}\nRESOLVER={a.resolver}\n"
        f"UNIVERSAL_RESOLVER=0x5d25c1d6acbb71b7a28aa7899618a3412a8303e3\nSTUDIO={studio}\nOPENER={opener}\n"
        f"BLOCKS_PER_EPOCH={a.blocks_per_epoch}\nWINDOW_EPOCHS={settings.window_epochs}\nHORIZON_EPOCHS={settings.horizon_epochs}\n"
        f"LOCK_SECONDS={settings.lock_seconds}\nOWNER_NAME={a.owner_name}\nHEIR_NAME={settings.heir_name}\n"
        f"SEALED_STATE_PATH={ROOT / 'backend' / '.demo-state.sepolia.json'}\n"  # never share state with the Anvil demo
        "BEACON_API=https://ethereum-sepolia-beacon-api.publicnode.com,https://lodestar-sepolia.chainsafe.io\n"
    )
    print(f"wrote {env}")
    print("next: python scripts/ens_sepolia.py grant", a.owner_name, studio, opener)


if __name__ == "__main__":
    main()
