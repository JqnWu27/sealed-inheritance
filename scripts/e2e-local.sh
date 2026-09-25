#!/usr/bin/env bash
# One-command local demo on Anvil: seal, heartbeat, silence, wrong witness, open, heir reads, slip pays.
# Requires WSL/Linux, Foundry in ~/.foundry/bin, backend venv at ~/eth-tokyo/venv (override with VENV=...).
export PATH="$HOME/.foundry/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${VENV:-$HOME/eth-tokyo/venv}"
PY="$VENV/bin/python"
cd "$ROOT"

pkill -f "uvicorn app.api:app" 2>/dev/null || true
pkill -f "anvil --chain-id" 2>/dev/null || true
sleep 1
rm -f backend/.demo-state.json
nohup anvil --chain-id 11155111 --block-time 1 --silent > backend/.anvil.log 2>&1 &
sleep 3

(cd contracts && forge build >/dev/null 2>&1) || { echo "forge build failed"; exit 1; }
"$PY" scripts/deploy_local.py || { echo "deploy failed"; exit 1; }
set -a; source backend/.env.local; set +a
(cd backend && nohup "$VENV/bin/uvicorn" app.api:app --host 127.0.0.1 --port 8000 > .api.log 2>&1 &)
for i in $(seq 1 20); do curl -s localhost:8000/health >/dev/null 2>&1 && break; sleep 1; done

j() { "$PY" -c 'import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=1)[:'"${1:-1200}"'])'; }
post() { curl -s -X POST "localhost:8000$1" -H 'content-type: application/json' -d "${2:-{\}}"; }

HEIR=$(curl -s localhost:8000/health | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["heir_eth"])')
echo "== 1 seal";       post /seal "{\"will\":\"60 percent of the studio to Hana, 40 percent to Ren. The client list is in the desk drawer.\",\"transfers\":[{\"to\":\"$HEIR\",\"amount_wei\":\"6000000000000000000\"}]}" | j 700
echo "== 2 records";    curl -s localhost:8000/records | j 700
echo "== 3 witness now, expect sealed"; curl -s localhost:8000/witness | "$PY" -c 'import sys,json; d=json.load(sys.stdin); print("ok" if d["ok"] else "sealed", [c["detail"] for c in d["checks"]])'
echo "== 4 heartbeat";  post /heartbeat | j 500
echo "== 5 clock, 100 blocks of silence"; post /clock '{"blocks":100}' | j 200
echo "== 6 wrong witness, expect sealed"; post "/decrypt?stale_epochs=8&force=true" | "$PY" -c 'import sys,json; d=json.load(sys.stdin); print(d["status"]); print("\n".join(d["trace"]))'
echo "== 7 open";       post /decrypt | "$PY" -c 'import sys,json; d=json.load(sys.stdin); print(d["status"]); print("\n".join(d["trace"]))'
echo "== 8 records after open"; curl -s localhost:8000/records | j 700
echo "== 9 heir reads the will"; post /heir/open '{}' | "$PY" -c 'import sys,json; b=json.load(sys.stdin)["bundle"]; print(b["will"]); print("slips:", len(b["slips"]))'
SLIP=$(post /heir/open '{}' | "$PY" -c 'import sys,json; b=json.load(sys.stdin)["bundle"]; print(json.dumps(b["slips"][0]))')
echo "== 10 slip before lock, expect rejected"; post /heir/execute "$SLIP" | j 300
echo "== 11 clock past the lock"; post /clock "{\"seconds\":$((LOCK_SECONDS + 10*8*12 + 5))}" | j 200
echo "== 12 slip after lock, expect paid"; post /heir/execute "$SLIP" | j 300
echo "== 13 heir balance"; cast balance "$HEIR" --ether --rpc-url http://127.0.0.1:8545
echo "== 14 attack, forged silence against the consensus spec"; "${SPEC_PYTHON:-$HOME/eth-tokyo/specvenv/bin/python}" attack/slashing.py --forgers 44 2>&1 | tail -8
echo; echo "API still running on :8000, Anvil on :8545. Stop with: pkill -f uvicorn; pkill -f anvil"
