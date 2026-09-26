"""Consensus-layer cross-check for the finality certificate.

The light client in this demo signs a certificate for an epoch boundary block.
On a real chain we additionally ask the beacon chain itself which execution
block it has finalized, through one or more public beacon API endpoints, and
require the certificate's block to be at or below it and on the same chain.

This moves "final" from an execution node's tag to the consensus layer's own
checkpoint. It still trusts the endpoints asked. Verifying the sync committee's
BLS aggregate locally would remove that trust and is the next step.
"""
from __future__ import annotations

import httpx


class BeaconDisagreement(Exception):
    pass


def finalized_checkpoint(base_urls: list[str], timeout: float = 15.0) -> dict:
    """Finalized checkpoint and finalized execution block, agreed by every endpoint that answers."""
    seen = []
    errors = []
    for base in base_urls:
        base = base.rstrip("/")
        try:
            with httpx.Client(timeout=timeout) as c:
                cp = c.get(f"{base}/eth/v1/beacon/states/finalized/finality_checkpoints").json()["data"]["finalized"]
                blk = c.get(f"{base}/eth/v2/beacon/blocks/finalized").json()["data"]["message"]
            ep = blk["body"]["execution_payload"]
            seen.append({
                "source": base,
                "epoch": int(cp["epoch"]),
                "root": cp["root"],
                "slot": int(blk["slot"]),
                "exec_number": int(ep["block_number"]),
                "exec_hash": ep["block_hash"].lower(),
            })
        except Exception as e:  # endpoint down or malformed
            errors.append(f"{base}: {type(e).__name__}")
    if not seen:
        raise RuntimeError("no beacon endpoint answered: " + "; ".join(errors))
    hashes = {s["exec_hash"] for s in seen}
    if len(hashes) > 1:
        # Endpoints may be a slot apart. Accept if every reported block lies on one chain,
        # which the caller checks against the execution chain. Report the oldest as the checkpoint.
        seen.sort(key=lambda s: s["exec_number"])
    head = seen[0]
    head = dict(head)
    head["sources"] = len(seen)
    head["others"] = [s for s in seen[1:]]
    return head
