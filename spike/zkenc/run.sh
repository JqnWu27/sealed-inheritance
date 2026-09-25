#!/usr/bin/env bash
# Spike: can the public zkenc tool (github.com/flyinglimao/zkenc) encapsulate and
# decapsulate our silence circuit end to end? Everything it prints goes into
# RESULT.md next to this script. zkenc is cloned OUTSIDE the repository and
# used as a third-party tool; none of its code is copied here.
export PATH="$HOME/.cargo/bin:$PATH"
HERE="$(cd "$(dirname "$0")" && pwd)"
ZK="$HOME/eth-tokyo/zkenc"
OUT="$HERE/RESULT.md"
log() { echo "$*" | tee -a "$OUT"; }

echo "# zkenc spike, $(date -u +%Y-%m-%dT%H:%MZ)" > "$OUT"
log ""
log "## 1. clone and build"
if [ ! -d "$ZK" ]; then git clone --depth 1 https://github.com/flyinglimao/zkenc "$ZK" 2>&1 | tail -2 | tee -a "$OUT"; fi
log "commit: $(cd "$ZK" && git log --oneline -1)"
(cd "$ZK" && cargo build --release -p zkenc-cli 2>&1 | tail -5) | tee -a "$OUT"
CLI="$(ls "$ZK"/target/release/zkenc* 2>/dev/null | head -1)"
log "cli: ${CLI:-not built}"

log ""
log "## 2. compile the silence circuit"
cd "$HERE"
circom silence.circom --r1cs --wasm --sym -o . 2>&1 | tail -3 | tee -a "$OUT"

log ""
log "## 3. witnesses"
cat > input_true.json <<'EOF'
{"N": 10, "E": 13, "h": 2}
EOF
cat > input_false.json <<'EOF'
{"N": 10, "E": 5, "h": 2}
EOF
node silence_js/generate_witness.js silence_js/silence.wasm input_true.json witness_true.wtns 2>&1 | tail -2 | tee -a "$OUT"
node silence_js/generate_witness.js silence_js/silence.wasm input_false.json witness_false.wtns 2>&1 | tail -2 | tee -a "$OUT"
log "true witness: $( [ -f witness_true.wtns ] && echo generated || echo failed )"
log "false witness: $( [ -f witness_false.wtns ] && echo generated || echo 'rejected by the circuit, as expected' )"

if [ -n "$CLI" ]; then
  log ""
  log "## 4. zkenc encap / decap"
  "$CLI" --help 2>&1 | head -30 | tee -a "$OUT"
  log "--- fill in the exact encap/decap invocations from --help, then record: does decap return the same key that encap produced?"
fi

log ""
log "## 5. conclusion"
log "(write one paragraph: build status, encap status, decap status, key match yes/no, and the decision)"
