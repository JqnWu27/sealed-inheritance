const API = location.origin.includes(":8000") ? "" : "http://127.0.0.1:8000";
const $ = (id) => document.getElementById(id);
let health = null;
let epochBlocks = 8;
let windowEpochs = 10;
let lockSeconds = 20 * 8 * 12;

async function get(path) { const r = await fetch(API + path); return r.json(); }
async function post(path, body) {
  const r = await fetch(API + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body || {}) });
  return r.json();
}
function log(id, lines) {
  const el = $(id);
  el.innerHTML = lines.map((l) => {
    const cls = l.startsWith("[ok]") ? "ok" : (l.startsWith("[FAIL]") || l.includes("no key") || l.includes("stays closed")) ? "fail" : "";
    return `<span class="${cls}">${escapeHtml(l)}</span>`;
  }).join("\n");
  el.scrollTop = el.scrollHeight;
}
function escapeHtml(s) { return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
function short(h, n = 14) { return h && h.length > n ? h.slice(0, n) + "…" : h; }

async function refresh() {
  try {
    const r = await get("/records");
    $("c-block").textContent = r.block;
    $("c-epoch").textContent = r.epoch;
    $("c-fin").textContent = r.finalized_epoch;
    $("c-window").textContent = r.window;
    $("c-vault").textContent = r.vault_balance_eth.toFixed(2);
    $("r-heir").textContent = r.records.heir || "–";
    $("r-vault").textContent = r.records.vault || "–";
    $("r-heartbeat").textContent = r.records.heartbeat || "–";
    $("r-sealed").textContent = r.records.sealed || "–";
    $("r-disclosure").textContent = r.records.disclosure || "empty";
    const opened = !!r.records.disclosure;
    const st = $("status");
    st.textContent = r.records.sealed ? (opened ? "OPENED" : "SEALED") : "–";
    st.className = "badge " + (opened ? "opened" : "sealed");
    if (r.heir_balance_eth !== undefined) $("heir-balance").textContent = Number(r.heir_balance_eth).toFixed(2);
  } catch (e) { /* backend not up yet */ }
}

async function init() {
  health = await get("/health");
  $("heir-addr").value = health.heir_eth;
  if (health.anvil === false) {
    // Real chain: no clock control, epochs pass in real time, transactions link to Etherscan.
    document.querySelector(".clockbtns").innerHTML = '<span class="net">Sepolia, real time, one epoch every 6.4 min</span>';
    window._explorer = "https://sepolia.etherscan.io/tx/";
  }
  const cfg = await get("/config").catch(() => null);
  if (cfg) {
    epochBlocks = cfg.blocks_per_epoch; windowEpochs = cfg.window_epochs; lockSeconds = cfg.lock_seconds;
    document.querySelectorAll(".oname").forEach((e) => (e.textContent = cfg.owner_name));
  }
  await refresh();
  setInterval(refresh, 4000);
}

$("btn-seal").onclick = async () => {
  const amount = Math.round(parseFloat($("amount").value || "0") * 1e18).toString();
  log("owner-log", ["sealing…"]);
  const out = await post("/seal", { will: $("will").value, transfers: [{ to: health.heir_eth, amount_wei: amount }] });
  log("owner-log", out.log || [JSON.stringify(out)]);
  $("opened").classList.add("hidden");
  refresh();
};
$("btn-heartbeat").onclick = async () => {
  log("owner-log", ["heartbeat…"]);
  const out = await post("/heartbeat");
  log("owner-log", out.log || [JSON.stringify(out)]);
  refresh();
};

$("btn-open").onclick = async () => {
  const stale = $("stale").checked;
  log("trace", ["building witness from the finalized chain…"]);
  const out = await post(stale ? "/decrypt?stale_epochs=8&force=true" : "/decrypt");
  const lines = out.trace || [JSON.stringify(out)];
  log("trace", [...lines, out.status === "opened" ? "→ OPENED" : "→ sealed"]);
  if (out.status === "opened") {
    const b = await post("/heir/open", {});
    $("will-out").textContent = b.bundle.will;
    $("opened").classList.remove("hidden");
    window._slip = b.bundle.slips[0];
  }
  refresh();
};
$("btn-execute").onclick = async () => {
  if (!window._slip) return;
  $("exec-out").textContent = "submitting…";
  const out = await post("/heir/execute", window._slip);
  if (out.status === "paid" && window._explorer) {
    $("exec-out").innerHTML = `paid, <a href="${window._explorer}${out.tx}" target="_blank" rel="noopener">tx ${short(out.tx)}</a>`;
  } else {
    $("exec-out").textContent = out.status === "paid" ? `paid, tx ${short(out.tx)}` : `rejected, ${out.reason}`;
  }
  refresh();
};

$("btn-attack").onclick = async () => {
  $("attack-status").textContent = "running the consensus spec…";
  $("btn-attack").disabled = true;
  try {
    const a = await post("/attack?forgers=44");
    document.querySelectorAll(".te").forEach((e) => (e.textContent = a.target_epoch));
    $("v-canon").textContent = a.attestation_canonical.target_root;
    $("v-forged").textContent = a.attestation_forged.target_root;
    const tb = $("slash-table").querySelector("tbody");
    // Electra correlation penalty at the midpoint of the withdrawal period:
    // penalty = balance * min(3 * slashed_stake / total_stake, 1). With 44 of 64 that is the whole stake.
    const corr = Math.min(3 * a.forgers / a.validators, 1);
    tb.innerHTML = a.rows.slice(0, 8).map((r) =>
      `<tr><td>${r.validator}${r.is_proposer ? " (proposer)" : ""}</td><td class="bad">SLASHED</td><td>${r.balance_before_eth.toFixed(2)}</td><td class="bad">-${(r.balance_before_eth - r.balance_after_eth).toFixed(2)}</td><td class="bad">${corr >= 1 ? "-all, " + r.balance_after_eth.toFixed(2) : "-" + (r.balance_after_eth * corr).toFixed(2)}</td><td>${r.withdrawable_epoch}</td></tr>`
    ).join("") + `<tr><td colspan="6">… ${a.rows.length} validators in total</td></tr>`;
    const totalStake = a.rows.reduce((acc, r) => acc + r.balance_before_eth, 0);
    $("slash-total").textContent = `${a.forgers} of ${a.validators} validators slashed. Immediately ${a.initial_penalty_eth_each} ETH each, ${a.total_initial_penalty_eth} ETH. More than one third of the stake signed both votes, so the correlation penalty at the midpoint takes ${corr >= 1 ? "their entire remaining stake, about " + Math.round(totalStake).toLocaleString() + " ETH" : (corr * 100).toFixed(0) + " percent of their stake"}. Had his validators finalized the forged history he could have read the will. This is the price, and the money never moves.`;
    $("attack-out").classList.remove("hidden");
    $("attack-status").textContent = "";
  } catch (e) {
    $("attack-status").textContent = "attack script failed, see backend log";
  }
  $("btn-attack").disabled = false;
};

document.querySelectorAll("[data-clock]").forEach((b) => {
  b.onclick = async () => {
    const k = b.dataset.clock;
    if (k === "epoch") await post("/clock", { blocks: epochBlocks });
    if (k === "silence") await post("/clock", { blocks: epochBlocks * (windowEpochs + 2) });
    if (k === "lock") await post("/clock", { seconds: lockSeconds + windowEpochs * epochBlocks * 12 + 5 });
    refresh();
  };
});

init();
