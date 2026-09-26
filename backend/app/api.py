"""Demo backend for Sealed Inheritance.

Owner side   POST /seal       first envelope, sets up will and transfers
             POST /heartbeat  roll: rotate counter, reseal to a fresh anchor
Public side  GET  /records    the four ENS records plus clock
             GET  /witness    build and check a witness for the live window
             POST /decrypt    open the outer layer if the chain says so, record disclosure
             POST /attack     forged-silence attack against the consensus spec
Heir side    POST /heir/open  open the inner box with the heir's key
             POST /heir/execute submit a slip to the vault
Demo clock   POST /clock      advance blocks or time on Anvil
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from eth_account import Account
from eth_utils import keccak
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web3 import Web3
from web3.logs import DISCARD

from . import crypto, kem
from .chain import Chain
from .checker import build_witness, check
from .config import ROOT, STATE_PATH, load_keys, settings
from .lightclient import MockLightClient
from .names import dns_encode, namehash

app = FastAPI(title="Sealed Inheritance backend")


@app.middleware("http")
async def no_store_headers(request, call_next):
    """The demo UI is edited live; never let a browser reuse a stale page or script."""
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    return resp
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

KEYS = load_keys()
chain = Chain(settings.rpc_url, settings.artifacts)
lc = MockLightClient(chain, KEYS["lightclient"], settings.blocks_per_epoch, settings.finality_lag_epochs)
KEM = kem.load(settings.kem_backend, KEYS["mock_kem_trapdoor"])

OWNER = Account.from_key(KEYS["owner"])
CHECKER = Account.from_key(KEYS["checker"])
WATCHTOWER = Account.from_key(KEYS["watchtower"])
HEIR_ETH = Account.from_key(KEYS.get("heir_eth", KEYS["watchtower"]))
NODE = namehash(settings.owner_name)
DNS = dns_encode(settings.owner_name)
HEIR_NODE = namehash(settings.heir_name)
HEIR_DNS = dns_encode(settings.heir_name)

RECORD_KEYS = ["heir", "vault", "heartbeat", "sealed", "disclosure"]


def studio():
    return chain.contract("Studio", settings.studio)


def opener():
    return chain.contract("Opener", settings.opener)


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"will": "", "transfers": [], "windows": {}, "opened": None}


def save_state(s: dict):
    STATE_PATH.write_text(json.dumps(s, indent=2))


# ------------------------------------------------------------------ helpers

def heir_pubkey_hex() -> str:
    """Hana's X25519 public key, read from her ENS name."""
    if settings.universal_resolver:
        rec, _ = chain.text_via_universal(settings.universal_resolver, HEIR_DNS, HEIR_NODE, "pubkey.x25519")
    else:
        rec = chain.text_at(settings.resolver, HEIR_DNS, HEIR_NODE, "pubkey.x25519", "latest")
    if not rec:
        raise HTTPException(400, f"{settings.heir_name} has no pubkey.x25519 record")
    return rec[2:] if rec.startswith("0x") else rec


def sign_slip(to: str, amount_wei: int, not_before: int, nonce: int) -> dict:
    domain = {"name": "SealedInheritance", "version": "1", "chainId": chain.chain_id,
              "verifyingContract": Web3.to_checksum_address(settings.studio)}
    types = {"Slip": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"},
                      {"name": "notBefore", "type": "uint64"}, {"name": "nonce", "type": "uint64"}]}
    msg = {"to": Web3.to_checksum_address(to), "amount": amount_wei, "notBefore": not_before, "nonce": nonce}
    signed = Account.sign_typed_data(KEYS["owner"], domain, types, msg)
    return {**msg, "signature": Web3.to_hex(signed.signature)}


def make_statement(anchor: dict, from_epoch: int) -> dict:
    """`from_epoch` is the epoch of the heartbeat that creates this window.
    Silence is counted from max(heartbeat in the finalized state, from_epoch),
    so a window can never open on a heartbeat older than the one that sealed it."""
    return {
        "v": 1,
        "owner_name": settings.owner_name,
        "node": "0x" + NODE.hex(),
        "resolver": Web3.to_checksum_address(settings.resolver),
        "predicate": {"key": "heartbeat", "window": settings.window_epochs, "from_epoch": from_epoch},
        "anchor": {"epoch": anchor["epoch"], "block_hash": anchor["block_hash"]},
        "horizon": settings.horizon_epochs,
        "relation": "hb-silence-v1",
    }


def condition_string(st: dict) -> str:
    return (f"anchor={st['anchor']['epoch']}:{st['anchor']['block_hash'][:10]}"
            f";from={st['predicate']['from_epoch']};N={st['predicate']['window']};H={st['horizon']};rel={st['relation']}")


def roll(state: dict, log: list[str]) -> dict:
    """Shared by /seal and /heartbeat: build the next envelope and call Studio.heartbeat."""
    s = studio()
    next_nonce = int(s.functions.nonce().call()) + 1
    anchor = lc.finalized()
    st = make_statement(anchor, lc.current_epoch())
    log.append(f"anchor = finalized epoch {anchor['epoch']}, block {anchor['block_hash'][:12]}…, silence counted from epoch {st['predicate']['from_epoch']}")

    now = chain.block("latest")["timestamp"]
    not_before = now + settings.window_epochs * settings.blocks_per_epoch * 12 + settings.lock_seconds
    slips = [sign_slip(t["to"], int(t["amount_wei"]), not_before, next_nonce) for t in state["transfers"]]
    log.append(f"signed {len(slips)} slip(s) for counter {next_nonce}, valid after {not_before}")

    bundle = {"v": 1, "window": next_nonce, "will": state["will"], "slips": slips}
    inner = crypto.seal_inner(heir_pubkey_hex(), bundle)
    log.append(f"inner box sealed to {settings.heir_name} pubkey.x25519, {len(inner)} bytes")

    kem_ct, key = KEM.encap(st)
    log.extend(KEM.trace())
    outer = crypto.seal_outer(key, st, inner)
    ct = crypto.pack_ciphertext(st, kem_ct, outer)
    cond = condition_string(st)
    log.append(f"outer sealed to condition, ct {len(ct)} bytes, hash {Web3.to_hex(keccak(ct))[:14]}…")

    rcpt = chain.send(s.functions.heartbeat(ct, cond), KEYS["owner"])
    log.append(f"Studio.heartbeat tx {Web3.to_hex(rcpt['transactionHash'])[:14]}… window {next_nonce}")

    state["windows"][str(next_nonce)] = {"statement": st, "ct_hash": Web3.to_hex(keccak(ct)), "condition": cond}
    if chain.is_anvil():
        # remember the chain right after this window, so the two-thirds attack can rewrite history back to it
        state.setdefault("snapshots", {})[str(next_nonce)] = chain.rpc("evm_snapshot", [])["result"]
    save_state(state)
    return {"window": next_nonce, "statement": st, "condition": cond, "tx": Web3.to_hex(rcpt["transactionHash"])}


# ---------------------------------------------------------------- endpoints

class SealIn(BaseModel):
    will: str
    transfers: list[dict]  # [{"to": "0x..", "amount_wei": "6000000000000000000"}]


@app.get("/health")
def health():
    return {"rpc": settings.rpc_url, "chain_id": chain.chain_id, "block": chain.block_number(), "anvil": chain.is_anvil(),
            "owner_name": settings.owner_name, "heir_name": settings.heir_name,
            "kem": KEM.name, "owner": OWNER.address, "checker": CHECKER.address, "watchtower": WATCHTOWER.address,
            "heir_eth": HEIR_ETH.address,
            "studio": settings.studio, "opener": settings.opener, "resolver": settings.resolver}


@app.post("/seal")
def seal(body: SealIn):
    state = load_state()
    state["will"] = body.will
    state["transfers"] = body.transfers
    state["opened"] = None
    log: list[str] = []
    out = roll(state, log)
    return {**out, "log": log}


@app.post("/heartbeat")
def heartbeat():
    state = load_state()
    if not state["windows"]:
        raise HTTPException(400, "seal first")
    log: list[str] = []
    out = roll(state, log)
    return {**out, "log": log}


@app.get("/config")
def config():
    return {"blocks_per_epoch": settings.blocks_per_epoch, "window_epochs": settings.window_epochs,
            "horizon_epochs": settings.horizon_epochs, "lock_seconds": settings.lock_seconds,
            "owner_name": settings.owner_name, "heir_name": settings.heir_name}


REGISTRY_ABI = [{"type": "function", "name": "ownerOf", "stateMutability": "view",
                 "inputs": [{"name": "tokenId", "type": "uint256"}], "outputs": [{"name": "", "type": "address"}]}]


def name_owner() -> dict:
    """Who holds the owner's name token in the registry: 'owner', 'heir', an address, or None."""
    if not settings.registry or not settings.name_token_id:
        return {"name_owner": None, "name_owner_label": None, "name_owner_is_heir": None}
    reg = chain.w3.eth.contract(address=Web3.to_checksum_address(settings.registry), abi=REGISTRY_ABI)
    tid = int(settings.name_token_id, 16) if settings.name_token_id.startswith("0x") else int(settings.name_token_id)
    try:
        who = reg.functions.ownerOf(tid).call()
    except Exception as e:
        return {"name_owner": None, "name_owner_label": f"unavailable, {str(e)[:40]}", "name_owner_is_heir": None}
    label = "owner" if who.lower() == OWNER.address.lower() else ("heir" if who.lower() == HEIR_ETH.address.lower() else who)
    return {"name_owner": who, "name_owner_label": label, "name_owner_is_heir": who.lower() == HEIR_ETH.address.lower()}


@app.get("/records")
def records():
    recs = {k: chain.text_at(settings.resolver, DNS, NODE, k, "latest") for k in RECORD_KEYS}
    s = studio()
    return {
        "name": settings.owner_name,
        "records": recs,
        **name_owner(),
        "window": int(s.functions.nonce().call()),
        "epoch": lc.current_epoch(),
        "finalized_epoch": lc.finalized()["epoch"],
        "vault_balance_eth": float(Web3.from_wei(chain.w3.eth.get_balance(Web3.to_checksum_address(settings.studio)), "ether")),
        "heir_balance_eth": float(Web3.from_wei(chain.w3.eth.get_balance(HEIR_ETH.address), "ether")),
        "block": chain.block_number(),
    }


def live_statement(state: dict):
    w = int(studio().functions.nonce().call())
    entry = state["windows"].get(str(w))
    if not entry:
        raise HTTPException(400, f"no envelope for window {w}")
    return w, entry["statement"]


@app.get("/witness")
def witness(stale_epochs: int = 0):
    state = load_state()
    w, st = live_statement(state)
    at = None if stale_epochs <= 0 else max(lc.finalized()["epoch"] - stale_epochs, 0)
    wit = build_witness(st, lc, chain, at_epoch=at)
    res = check(st, wit, lc, chain)
    return {"window": w, "witness": wit, **res}


@app.post("/decrypt")
def decrypt(stale_epochs: int = 0, force: bool = False):
    """Open the live window if the four checks pass. `force` runs the KEM even
    when the checks fail, to show on screen that the key does not come out."""
    state = load_state()
    w, st = live_statement(state)
    at = None if stale_epochs <= 0 else max(lc.finalized()["epoch"] - stale_epochs, 0)
    wit = build_witness(st, lc, chain, at_epoch=at)
    res = check(st, wit, lc, chain)
    trace = [f"[{'ok' if c['ok'] else 'FAIL'}] {c['name']}: {c['detail']}" for c in res["checks"]]
    if not res["ok"] and not force:
        return {"window": w, "status": "sealed", "checks": res["checks"], "trace": trace}

    ct = bytes(studio().functions.sealedEnvelope(w).call())
    packed = crypto.unpack_ciphertext(ct)
    key = KEM.decap(packed["statement"], packed["kem_ct"], wit)
    trace.extend(KEM.trace())
    if key is None:
        return {"window": w, "status": "sealed", "checks": res["checks"], "trace": trace + ["no key, outer layer stays closed"]}
    inner = crypto.open_outer(key, packed["statement"], packed["outer"])
    if inner is None:
        return {"window": w, "status": "sealed", "checks": res["checks"], "trace": trace + ["authenticated decryption failed, outer layer stays closed"]}
    trace.append(f"outer layer opened, inner box {len(inner)} bytes, hash {Web3.to_hex(keccak(inner))[:14]}…")

    inner_hash = keccak(inner)
    digest = keccak(NODE + w.to_bytes(8, "big") + inner_hash)
    sig = CHECKER.unsafe_sign_hash(digest).signature
    o = opener()
    if not o.functions.opened(NODE, w).call():
        rcpt = chain.send(o.functions.recordOpening(DNS, w, inner_hash, bytes(sig)), KEYS["watchtower"])
        trace.append(f"Opener.recordOpening tx {Web3.to_hex(rcpt['transactionHash'])[:14]}…, disclosure record written")
        for ev in o.events.NameHandedOver().process_receipt(rcpt, errors=DISCARD):
            trace.append(f"{settings.owner_name} handed over: the name token moved from {ev['args']['from'][:10]}… to the heir {ev['args']['to'][:10]}…")
        for ev in o.events.HandoverSkipped().process_receipt(rcpt, errors=DISCARD):
            trace.append(f"name handover skipped, {ev['args']['reason']}")
    else:
        trace.append(f"disclosure for window {w} already recorded")
    state["opened"] = {"window": w, "inner": Web3.to_hex(inner), "at": int(time.time())}
    save_state(state)
    return {"window": w, "status": "opened", "checks": res["checks"], "trace": trace, "inner": Web3.to_hex(inner)}


class HeirOpenIn(BaseModel):
    inner: str | None = None


@app.post("/heir/open")
def heir_open(body: HeirOpenIn):
    state = load_state()
    inner_hex = body.inner or (state.get("opened") or {}).get("inner")
    if not inner_hex:
        raise HTTPException(400, "nothing has been opened yet")
    bundle = crypto.open_inner(KEYS["heir_x25519_sk"], bytes.fromhex(inner_hex[2:]))
    return {"bundle": bundle}


class SlipIn(BaseModel):
    to: str
    amount: int
    notBefore: int
    nonce: int
    signature: str


VAULT_ERRORS = {
    Web3.to_hex(keccak(text=sig))[:10]: name for sig, name in [
        ("TooEarly(uint64,uint256)", "TooEarly: the slip's valid-after time has not passed"),
        ("StaleNonce(uint64,uint64)", "StaleNonce: the vault counter has moved on, this slip is void"),
        ("BadSignature()", "BadSignature: not signed by the owner"),
        ("TransferFailed()", "TransferFailed"),
    ]
}


def decode_revert(err: Exception) -> str:
    text = str(err)
    for sel, name in VAULT_ERRORS.items():
        if sel in text:
            return name
    return text[:200]


@app.post("/heir/execute")
def heir_execute(slip: SlipIn):
    s = studio()
    try:
        rcpt = chain.send(
            s.functions.execute((Web3.to_checksum_address(slip.to), slip.amount, slip.notBefore, slip.nonce),
                                bytes.fromhex(slip.signature[2:])),
            KEYS["watchtower"],
        )
    except Exception as e:
        return {"status": "rejected", "reason": decode_revert(e)}
    return {"status": "paid", "tx": Web3.to_hex(rcpt["transactionHash"])}


class ClockIn(BaseModel):
    blocks: int = 0
    seconds: int = 0


@app.post("/clock")
def clock(body: ClockIn):
    if not chain.is_anvil():
        raise HTTPException(400, "clock control only on Anvil")
    if body.seconds:
        chain.increase_time(body.seconds)
    if body.blocks:
        chain.mine(body.blocks)
    return {"block": chain.block_number(), "epoch": lc.current_epoch(), "timestamp": chain.block("latest")["timestamp"]}


@app.post("/attack")
def attack(forgers: int = 22):
    py = os.environ.get("SPEC_PYTHON", os.path.expanduser("~/eth-tokyo/specvenv/bin/python"))
    script = ROOT / "attack" / "slashing.py"
    proc = subprocess.run([py, str(script), "--forgers", str(forgers), "--json"], capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise HTTPException(500, proc.stderr[-2000:])
    return json.loads(proc.stdout)


@app.post("/attack/rewrite")
def attack_rewrite(forgers: int = 44):
    """Two thirds of the validators can finalize a forged history. On Anvil we do exactly that:
    revert the chain to the snapshot taken right after the previous window, so the owner's last
    heartbeat never happened, then let the silence pass. The slashing experiment runs as well."""
    if not chain.is_anvil():
        raise HTTPException(400, "rewriting history is only possible on Anvil, nobody can rewrite Sepolia")
    state = load_state()
    w = int(studio().functions.nonce().call())
    snaps = state.get("snapshots", {})
    if w < 2 or str(w - 1) not in snaps:
        raise HTTPException(400, "seal and heartbeat first, so there is a heartbeat to erase")
    result = attack(forgers)
    ok = chain.rpc("evm_revert", [snaps[str(w - 1)]]).get("result")
    if not ok:
        raise HTTPException(500, "evm_revert failed")
    for k in [k for k in snaps if int(k) >= w]:
        snaps.pop(k)
    snaps[str(w - 1)] = chain.rpc("evm_snapshot", [])["result"]
    state["snapshots"] = snaps
    save_state(state)
    chain.mine(settings.blocks_per_epoch * (settings.window_epochs + 2))
    result["rewrite"] = {"erased_window": w, "window_now": w - 1, "heartbeat_epoch_now": chain.text_at(settings.resolver, DNS, NODE, "heartbeat", "latest")}
    return result


# The static UI is served last so API routes take precedence.
from fastapi.staticfiles import StaticFiles  # noqa: E402

WEB_DIR = ROOT / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
