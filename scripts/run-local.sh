#!/usr/bin/env bash
# Start Anvil, deploy the demo, and run the backend. WSL/Linux.
set -e
export PATH="$HOME/.foundry/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${VENV:-$HOME/eth-tokyo/venv}"
PY="$VENV/bin/python"

cd "$ROOT/contracts" && forge build >/dev/null
cd "$ROOT"

if ! curl -s -X POST -H 'content-type: application/json' --data '{"jsonrpc":"2.0","id":1,"method":"web3_clientVersion","params":[]}' http://127.0.0.1:8545 >/dev/null 2>&1; then
  echo "starting anvil"
  nohup anvil --chain-id 11155111 --block-time 1 --silent > "$ROOT/backend/.anvil.log" 2>&1 &
  sleep 2
fi

"$PY" scripts/deploy_local.py
set -a; source backend/.env.local; set +a
cd backend && exec "$VENV/bin/uvicorn" app.api:app --host 0.0.0.0 --port 8000
