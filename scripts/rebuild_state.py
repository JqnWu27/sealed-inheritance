"""Rebuild the backend's local state file from the chain alone.

    set -a; source backend/.env.sepolia; set +a
    python scripts/rebuild_state.py [--will "text"] [--amount-eth 0.01]

Everything an opener needs is public: the envelope is stored by Studio, and the
statement it is encrypted to travels inside the envelope. The state file is only a
cache for the owner's next heartbeat (the will text and the transfer list) and
for the UI. Losing it loses nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from eth_account import Account  # noqa: E402
from web3 import Web3  # noqa: E402
from eth_utils import keccak  # noqa: E402

from app import crypto  # noqa: E402
from app.chain import Chain  # noqa: E402
from app.config import STATE_PATH, load_keys, settings  # noqa: E402


def condition_string(st: dict) -> str:
    return (f"anchor={st['anchor']['epoch']}:{st['anchor']['block_hash'][:10]}"
            f";from={st['predicate']['from_epoch']};N={st['predicate']['window']};H={st['horizon']};rel={st['relation']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--will", default="60 percent of the studio to Hana, 40 percent to the apprentices. The client list is in the desk drawer, the password is the year we founded.")
    ap.add_argument("--amount-eth", type=float, default=0.01)
    a = ap.parse_args()
    if not settings.studio:
        sys.exit("STUDIO is not set, source the env file first")
    chain = Chain(settings.rpc_url, ROOT / "contracts" / "out")
    keys = load_keys()
    heir = Account.from_key(keys["heir_eth"]).address
    studio = chain.contract("Studio", settings.studio)
    n = int(studio.functions.nonce().call())
    print(f"chain {chain.chain_id}, Studio {settings.studio}, {n} window(s) on chain")
    windows = {}
    for w in range(1, n + 1):
        ct = bytes(studio.functions.sealedEnvelope(w).call())
        packed = crypto.unpack_ciphertext(ct)
        st = packed["statement"]
        windows[str(w)] = {"statement": st, "ct_hash": Web3.to_hex(keccak(ct)), "condition": condition_string(st)}
        print(f"  window {w}: {len(ct)} bytes, anchor {st['anchor']['epoch']}, from {st['predicate']['from_epoch']}, N {st['predicate']['window']}, H {st['horizon']}")
    state = {"will": a.will, "transfers": [{"to": heir, "amount_wei": str(int(a.amount_eth * 10**18))}], "windows": windows, "opened": None}
    STATE_PATH.write_text(json.dumps(state, indent=2))
    print(f"wrote {STATE_PATH}")


if __name__ == "__main__":
    main()
