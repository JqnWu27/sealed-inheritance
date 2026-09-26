"""Relation checker: the four opening conditions over chain data.

1. finality      the certificate is valid and names a real block
2. binding       the heartbeat value is what the resolver held in that block, proven by a
                 storage proof against the state root the certificate signs
3. predicate     heartbeat_epoch + N <= epoch
4. horizon       anchor.epoch <= epoch <= anchor.epoch + H
5. consensus     on a real chain, the beacon chain's finalized checkpoint covers the block

The checker produces the witness values the KEM adapter consumes, and a
per-check trace for the UI.
"""
from __future__ import annotations

from . import beacon, stateproof
from .chain import Chain
from .config import settings
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
    detail2 = f"resolve({statement['owner_name']}, text(heartbeat)) at block {cert['block_number']} = {again!r}"
    if settings.state_proof != "off":
        # Prove the record against the state root the certificate signs, not just read it from the RPC.
        try:
            pf = stateproof.prove_text(chain.w3, statement["resolver"], node, statement["predicate"]["key"],
                                       int(cert["block_number"]), bytes.fromhex(cert["state_root"][2:]), expected=again)
            detail2 += (f"; storage proof ({pf['layout']}, {len(pf['slots'])} slot(s), {pf['account_nodes']} account + "
                        f"{pf['storage_nodes']} storage trie nodes) against state root {pf['state_root'][:12]}… gives {pf['value']!r}")
        except Exception as ex:
            ok2 = False
            detail2 += f"; storage proof FAILED, {str(ex)[:120]}"
    checks.append({"name": "binding", "ok": ok2, "detail": detail2})

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

    # 5. consensus layer, real chains only: the beacon chain's own finalized checkpoint must be at or
    #    beyond the certificate's block, and the execution chain must agree on that finalized block.
    if settings.beacon_api:
        try:
            cp = beacon.finalized_checkpoint([u.strip() for u in settings.beacon_api.split(",") if u.strip()])
            same_chain = chain.block(cp["exec_number"])["hash"].lower() == cp["exec_hash"]
            ok5 = int(cert["block_number"]) <= cp["exec_number"] and same_chain
            checks.append({"name": "consensus", "ok": ok5,
                           "detail": (f"beacon finalized epoch {cp['epoch']}, slot {cp['slot']}, execution block {cp['exec_number']} "
                                      f"{cp['exec_hash'][:12]}…, {cp['sources']} endpoint(s); certificate block {cert['block_number']} "
                                      f"{'is at or below it and on the same chain' if ok5 else 'is NOT covered by it'}")})
        except Exception as ex:
            checks.append({"name": "consensus", "ok": False, "detail": f"beacon API unavailable, {ex}"})

    return {"ok": all(c["ok"] for c in checks), "checks": checks}
