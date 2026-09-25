#!/usr/bin/env bash
# Sepolia in one sitting. Each step is printed and can be re-run alone with the
# commands shown in scripts/ens_sepolia.py. Stops at the first failure.
#
#   RPC_URL=https://ethereum-sepolia-rpc.publicnode.com OWNER_NAME=yutotanaka.eth HEIR_NAME=hana.eth bash scripts/sepolia-all.sh
#
# Before running: both names registered on https://app.ens.dev, the owner name
# from the demo owner account in backend/.demo-keys.json, and test ETH on the
# owner, the watchtower and the heir addresses printed by step 0.
set -euo pipefail
export PATH="$HOME/.foundry/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${VENV:-$HOME/eth-tokyo/venv}"
PY="$VENV/bin/python"
cd "$ROOT"
: "${RPC_URL:?set RPC_URL}"
export OWNER_NAME="${OWNER_NAME:-yutotanaka.eth}"
export HEIR_NAME="${HEIR_NAME:-hana.eth}"
export WINDOW_EPOCHS="${WINDOW_EPOCHS:-3}"
export HORIZON_EPOCHS="${HORIZON_EPOCHS:-60}"
export LOCK_SECONDS="${LOCK_SECONDS:-1200}"

echo "== 0 accounts and balances"
"$PY" - <<'PY'
import sys; sys.path.insert(0, "backend")
from app.config import load_keys, settings
from eth_account import Account
from web3 import Web3
import os
w3 = Web3(Web3.HTTPProvider(os.environ["RPC_URL"]))
k = load_keys()
for who in ("owner", "watchtower", "heir_eth"):
    a = Account.from_key(k[who]).address
    print(f"  {who:10s} {a}  {Web3.from_wei(w3.eth.get_balance(a), 'ether'):.4f} ETH")
PY

echo "== 1 resolver of $OWNER_NAME"
"$PY" scripts/ens_sepolia.py resolver "$OWNER_NAME"
if [ -z "${RESOLVER:-}" ]; then
  echo "== 2 deploy the owner's permissioned resolver"
  RESOLVER=$("$PY" scripts/ens_sepolia.py deploy-resolver | tee /dev/stderr | sed -n 's/.*: \(0x[0-9a-fA-F]\{40\}\) tx.*/\1/p' | tail -1)
  echo "   RESOLVER=$RESOLVER"
  echo "== 3 point $OWNER_NAME at it"
  "$PY" scripts/ens_sepolia.py set-resolver "$OWNER_NAME" "$RESOLVER"
else
  echo "== 2,3 using RESOLVER=$RESOLVER from the environment"
fi

echo "== 4 build and deploy Studio and Opener"
(cd contracts && forge build >/dev/null)
"$PY" scripts/deploy_sepolia.py --resolver "$RESOLVER" --owner-name "$OWNER_NAME"
set -a; source backend/.env.sepolia; set +a

echo "== 5 heir and vault records, heir pubkey"
"$PY" scripts/ens_sepolia.py records "$OWNER_NAME" "$HEIR_NAME" "$STUDIO"
"$PY" scripts/ens_sepolia.py pubkey "$HEIR_NAME"

echo "== 6 scoped setter roles for Studio and Opener"
"$PY" scripts/ens_sepolia.py grant "$OWNER_NAME" "$STUDIO" "$OPENER"

echo "== 7 read back through the universal resolver"
"$PY" scripts/ens_sepolia.py read "$OWNER_NAME"
"$PY" scripts/ens_sepolia.py read "$HEIR_NAME" pubkey.x25519

echo "== 8 fill docs/config.json for the live page"
"$PY" - <<PY
import json
p = "docs/config.json"; c = json.load(open(p))
c.update({"name": "$OWNER_NAME", "heir": "$HEIR_NAME", "studio": "$STUDIO", "opener": "$OPENER", "rpc": "$RPC_URL", "blocks_per_epoch": int("${BLOCKS_PER_EPOCH:-32}")})
json.dump(c, open(p, "w"), indent=2); print(open(p).read())
PY

cat <<EOF

Done. Next, in three terminals:
  1. cd backend && set -a && source .env.sepolia && set +a && $VENV/bin/uvicorn app.api:app --host 127.0.0.1 --port 8000
  2. open http://localhost:8000/ , Seal once, Heartbeat once. Both are real Sepolia transactions.
  3. $PY backend/watchtower.py --every 60      # opens after $WINDOW_EPOCHS finalized epochs of silence
Commit NOTES.md (addresses) and docs/config.json. Never commit backend/.env.sepolia.
EOF
