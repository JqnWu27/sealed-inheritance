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
    // when must Yuto check in again? the condition opens at finalized epoch max(last heartbeat, sealed from) + N
    const sealedRec = r.records.sealed || "";
    const mFrom = /from=(\d+)/.exec(sealedRec), mN = /N=(\d+)/.exec(sealedRec);
    if (mFrom && mN) {
      const h = parseInt(r.records.heartbeat || "-1", 10), N = parseInt(mN[1], 10);
      const due = Math.max(h, parseInt(mFrom[1], 10)) + N, left = due - r.finalized_epoch;
      const opened = !!r.records.disclosure && r.records.disclosure.includes(`window=${r.window};`);
      $("c-due").textContent = opened ? "opened" : left > 0 ? `in ${left} epoch${left === 1 ? "" : "s"}` : "passed, the will can be opened";
      $("c-due-wrap").className = "due" + (left > 0 || opened ? "" : " late");
      $("r-due").textContent = opened ? "" : left > 0
        ? `Yuto must check in again before finalized epoch ${due}, ${left} epoch${left === 1 ? "" : "s"} left of ${N}`
        : `no heartbeat for ${N} epochs, silence complete since finalized epoch ${due}`;
    } else {
      $("c-due").textContent = "–"; $("r-due").textContent = "";
    }
    $("r-sealed").textContent = r.records.sealed || "–";
    $("r-disclosure").textContent = r.records.disclosure || "empty";
    const ownerLabel = r.name_owner_label === "owner" ? "Yuto" : r.name_owner_label === "heir" ? "Hana" : (r.name_owner_label || "–");
    // the inheritance block: one card per name, the parent first, then its subnames; a card turns green once the name moved
    const names = (r.names && r.names.length) ? r.names : [{ name: r.name, owner: r.name_owner, label: ownerLabel }];
    $("tree").innerHTML = names.map((n, i) => {
      const changed = !!n.owner && n.label !== "Yuto";
      return `<div class="tcard ${changed ? "changed" : ""}"><div class="tname">${i ? "└ " : ""}${escapeHtml(n.name)}${i ? " · subname, in Yuto's own registry" : " · the name"}</div>` +
        `<div class="towner"${i ? "" : ' id="r-owner"'}>${escapeHtml(n.label)}</div>` +
        `<div class="taddr">${n.owner ? escapeHtml(short(n.owner, 10)) : "–"}${changed ? " · was Yuto" : ""}</div></div>`;
    }).join("");
    const moved = names.filter((n) => n.owner && n.label !== "Yuto").length;
    const pill = $("inherit-state");
    pill.textContent = moved ? `after the opening: ${moved} of ${names.length} name${names.length > 1 ? "s" : ""} moved to the heir${moved > 1 ? "s" : ""}` : "before the opening: everything is Yuto's";
    pill.className = "pill" + (moved ? " moved" : "");
    const children = names.slice(1);
    const handed = children.filter((n) => n.owner && n.label !== "Yuto");
    $("handover-out").textContent = r.name_owner_is_heir
      ? `${r.name} is now owned by Hana` + handed.map((n) => `, ${n.name} by ${n.label}`).join("") + "."
      : "";
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
    document.querySelectorAll(".anvil-only").forEach((e) => e.classList.add("hidden"));
    window._explorer = "https://sepolia.etherscan.io/tx/";
  }
  if (location.search.includes("money")) document.querySelectorAll(".money").forEach((e) => e.classList.remove("money"));
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

async function runAttack(rewrite) {
  const status = $("attack-status");
  status.textContent = rewrite ? "running the consensus spec, then rewriting history…" : "running the consensus spec…";
  $("btn-attack").disabled = true; $("btn-attack-2").disabled = true;
  try {
    const a = await post(rewrite ? "/attack/rewrite?forgers=44" : "/attack?forgers=22");
    if (a.detail) throw new Error(a.detail);
    document.querySelectorAll(".te").forEach((e) => (e.textContent = a.target_epoch));
    $("v-canon").textContent = a.attestation_canonical.target_root;
    $("v-forged").textContent = a.attestation_forged.target_root;
    const tb = $("slash-table").querySelector("tbody");
    // Electra correlation penalty at the midpoint: balance * min(3 * slashed_stake / total_stake, 1).
    const corr = Math.min(3 * a.forgers / a.validators, 1);
    tb.innerHTML = a.rows.slice(0, 8).map((r) =>
      `<tr><td>${r.validator}${r.is_proposer ? " (proposer)" : ""}</td><td class="bad">SLASHED</td><td>${r.balance_before_eth.toFixed(2)}</td><td class="bad">-${(r.balance_before_eth - r.balance_after_eth).toFixed(2)}</td><td class="bad">${corr >= 1 ? "-all, " + r.balance_after_eth.toFixed(2) : "-" + (r.balance_after_eth * corr).toFixed(2)}</td><td>${r.withdrawable_epoch}</td></tr>`
    ).join("") + `<tr><td colspan="6">… ${a.rows.length} validators in total</td></tr>`;
    const totalStake = a.rows.reduce((acc, r) => acc + r.balance_before_eth, 0);
    const share = a.forgers / a.validators >= 2 / 3 ? "Two thirds" : "A third";
    const penalty = `${a.forgers} of ${a.validators} validators slashed. Immediately ${a.initial_penalty_eth_each} ETH each, ${a.total_initial_penalty_eth} ETH, then the correlation penalty takes ${corr >= 1 ? "their entire remaining stake, about " + Math.round(totalStake).toLocaleString() + " ETH" : (corr * 100).toFixed(0) + " percent of their stake"}.`;
    if (rewrite) {
      $("slash-total").textContent = `${penalty} ${share} is enough to finalize the forged history: Yuto's last heartbeat is gone from the chain, the window is back to ${a.rewrite.window_now}, and the will can be opened. On mainnet that is control of about 27 million ETH, and a loss of at least 13.6 million.`;
    } else {
      $("slash-total").textContent = `${penalty} ${share} is enough to be the overlap of two finalized histories, not enough to finalize one alone. She is slashed, and the will stays sealed. On mainnet that is 13.6 million ETH lost for nothing.`;
    }
    $("attack-out").classList.remove("hidden");
    status.textContent = "";
    if (rewrite) refresh();
  } catch (e) {
    status.textContent = e && e.message ? e.message : "attack failed, see backend log";
  }
  $("btn-attack").disabled = false; $("btn-attack-2").disabled = false;
}
$("btn-attack").onclick = () => runAttack(false);
$("btn-attack-2").onclick = () => runAttack(true);

document.querySelectorAll("[data-clock]").forEach((b) => {
  b.onclick = async () => {
    const k = b.dataset.clock;
    if (k === "epoch") await post("/clock", { blocks: epochBlocks });
    if (k === "silence") await post("/clock", { blocks: epochBlocks * (windowEpochs + 2) });
    if (k === "lock") await post("/clock", { seconds: lockSeconds + windowEpochs * epochBlocks * 12 + 5 });
    if (k === "reset") {
      const out = await post("/reset");
      if (out.detail) { alert(out.detail); return; }
      $("owner-log").textContent = "Nothing sealed yet.";
      $("trace").textContent = "–";
      $("opened").classList.add("hidden");
      $("attack-out").classList.add("hidden");
      $("attack-status").textContent = "";
    }
    refresh();
  };
});

init();
