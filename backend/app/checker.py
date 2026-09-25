"""Relation checker: the four opening conditions over chain data.

1. finality      the certificate is valid and names a real block
2. binding       the heartbeat value is what the resolver held in that block
3. predicate     heartbeat_epoch + N <= epoch
4. horizon       anchor.epoch <= epoch <= anchor.epoch + H

The checker produces the witness values the KEM adapter consumes, and a
per-check trace for the UI.
"""
from __future__ import annotations

from .chain import Chain
from .lightclient import MockLightClient
from .names import dns_encode


def build_witness(statement: dict, lc: MockLightClient, chain: Chain, at_epoch: int | None = None) -> dict:
    cert = lc.finalized(at_epoch=at_epoch)
    node = bytes.fromhex(statement["node"][2:])
    dns = dns_encode(statement["owner_name"])
    raw = chain.text_at(statement["resolver"], dns, node, statement["predicate"]["key"], cert["block_hash"])
    hb = int(raw) if raw.strip().isdigit() else -1
    return {
        "finalized": cert,
        "epoch": cert["epoch"],
        "heartbeat_epoch": hb,
        "heartbeat_raw": raw,
    }


def check(statement: dict, witness: dict, lc: MockLightClient, chain: Chain) -> dict:
    checks = []
    cert = witness["finalized"]

    ok1, d1 = lc.verify(cert)
    checks.append({"name": "finality", "ok": ok1, "detail": f"epoch {cert['epoch']}, block {cert['block_hash'][:12]}…, {d1}"})

    node = bytes.fromhex(statement["node"][2:])
    dns = dns_encode(statement["owner_name"])
    try:
        again = chain.text_at(statement["resolver"], dns, node, statement["predicate"]["key"], cert["block_hash"])
    except Exception as e:  # pragma: no cover
        again = f"error {e}"
    ok2 = again == witness["heartbeat_raw"] and witness["heartbeat_epoch"] >= 0
    checks.append({"name": "binding", "ok": ok2, "detail": f"resolver.resolve({statement['owner_name']}, text(heartbeat)) at that block = {again!r}"})

    n = int(statement["predicate"]["window"])
    from_epoch = int(statement["predicate"].get("from_epoch", 0))
    e, hb = int(witness["epoch"]), int(witness["heartbeat_epoch"])
    eff = max(hb, from_epoch)
    ok3 = hb >= 0 and eff + n <= e
    checks.append({"name": "predicate", "ok": ok3,
                   "detail": f"last heartbeat max({hb}, sealed at {from_epoch}) = {eff}, + N {n} {'<=' if ok3 else '>'} epoch {e}"})

    a = int(statement["anchor"]["epoch"])
    h = int(statement["horizon"])
    ok4 = a <= e <= a + h
    checks.append({"name": "horizon", "ok": ok4, "detail": f"anchor {a} <= epoch {e} <= anchor + H {a + h}"})

    return {"ok": all(c["ok"] for c in checks), "checks": checks}
