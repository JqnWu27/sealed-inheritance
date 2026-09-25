"""Forged-silence attack against Ethereum's executable consensus spec.

Story: the forger's validators finalize a private history in which the owner's
heartbeat never happened. To keep the real chain finalizing, the same validators
also vote on the real history. For one target epoch they therefore sign two
attestations with different target roots. Those are double votes, and Ethereum
slashes them.

This script builds that pair with the spec's own functions, Electra minimal
preset, 64 validators, and runs process_attester_slashing. It uses no test
helpers beyond genesis state creation and the deterministic test keys.

Run with the spec venv:
    python attack/slashing.py --forgers 44 --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys

from eth_consensus_specs.electra import minimal as spec
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import privkeys

GWEI = 10**9


def root_of(label: str) -> spec.Root:
    return spec.Root(hashlib.sha256(label.encode()).digest())


def sign_attestation(state, data, indices):
    domain = spec.get_domain(state, spec.DOMAIN_BEACON_ATTESTER, data.target.epoch)
    signing_root = spec.compute_signing_root(data, domain)
    sigs = [spec.bls.Sign(privkeys[i], signing_root) for i in indices]
    return spec.bls.Aggregate(sigs)


def indexed(state, data, indices):
    return spec.IndexedAttestation(
        attesting_indices=sorted(indices),
        data=data,
        signature=sign_attestation(state, data, indices),
    )


def run(n_validators: int, n_forgers: int) -> dict:
    balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    state = create_genesis_state(spec, [balance] * n_validators, balance)

    # Move into epoch 2 so a target at epoch 1 is in the past and slashable now.
    target_epoch = spec.Epoch(1)
    spec.process_slots(state, spec.Slot(spec.SLOTS_PER_EPOCH * 2))
    slot = spec.Slot(spec.SLOTS_PER_EPOCH * 1 + 3)
    source = spec.Checkpoint(epoch=spec.Epoch(0), root=spec.hash_tree_root(state.latest_block_header))

    canonical_target = root_of("canonical block: contains ken.eth heartbeat at epoch 110")
    forged_target = root_of("forged block: heartbeat omitted")

    data_canonical = spec.AttestationData(
        slot=slot, index=0, beacon_block_root=canonical_target, source=source,
        target=spec.Checkpoint(epoch=target_epoch, root=canonical_target),
    )
    data_forged = spec.AttestationData(
        slot=slot, index=0, beacon_block_root=forged_target, source=source,
        target=spec.Checkpoint(epoch=target_epoch, root=forged_target),
    )
    assert spec.is_slashable_attestation_data(data_canonical, data_forged)

    forgers = list(range(n_forgers))
    att_1 = indexed(state, data_canonical, forgers)
    att_2 = indexed(state, data_forged, forgers)
    assert spec.is_valid_indexed_attestation(state, att_1)
    assert spec.is_valid_indexed_attestation(state, att_2)

    before = [(int(state.balances[i]), bool(state.validators[i].slashed)) for i in forgers]
    slashing = spec.AttesterSlashing(attestation_1=att_1, attestation_2=att_2)
    spec.process_attester_slashing(state, slashing)
    after = [(int(state.balances[i]), bool(state.validators[i].slashed), int(state.validators[i].withdrawable_epoch)) for i in forgers]

    penalty_each = int(balance) // int(spec.MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA)
    proposer = int(spec.get_beacon_proposer_index(state))
    rows = []
    for i, (b0, _), (b1, slashed, we) in zip(forgers, before, after):
        rows.append({
            "validator": i,
            "slashed": slashed,
            "balance_before_eth": b0 / GWEI,
            "balance_after_eth": b1 / GWEI,
            "withdrawable_epoch": we,
            "is_proposer": i == proposer,
        })
    total_penalty = penalty_each * len(forgers)
    proposer_reward = sum((b1 - b0 + penalty_each) for (b0, _), (b1, _, _) in zip(before, after) if True) if proposer in forgers else 0
    return {
        "preset": "electra/minimal",
        "validators": n_validators,
        "forgers": n_forgers,
        "target_epoch": int(target_epoch),
        "attestation_canonical": {
            "slot": int(slot), "target_root": "0x" + bytes(canonical_target).hex(),
            "note": "real history, includes the heartbeat",
        },
        "attestation_forged": {
            "slot": int(slot), "target_root": "0x" + bytes(forged_target).hex(),
            "note": "private history, heartbeat omitted",
        },
        "slashable": True,
        "initial_penalty_eth_each": penalty_each / GWEI,
        "total_initial_penalty_eth": total_penalty / GWEI,
        "proposer_index": proposer,
        "proposer_whistleblower_reward_eth": proposer_reward / GWEI,
        "note_rewards": "whistleblower rewards go to the block proposer of the slashing block; on this 64-validator network the proposer is one of the forgers, so its balance rises while the others fall",
        "note_correlation": "the correlation penalty is assessed later at the midpoint of the withdrawability delay and scales with the total stake slashed in the window",
        "rows": rows,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--validators", type=int, default=64)
    ap.add_argument("--forgers", type=int, default=44)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    out = run(a.validators, a.forgers)
    if a.json:
        json.dump(out, sys.stdout, indent=2)
    else:
        print(f"{out['preset']}: {out['forgers']} of {out['validators']} validators signed two targets for epoch {out['target_epoch']}")
        print(f"canonical target {out['attestation_canonical']['target_root'][:18]}…  forged target {out['attestation_forged']['target_root'][:18]}…")
        for r in out["rows"][:5]:
            tag = " (proposer, collects whistleblower rewards)" if r["is_proposer"] else ""
            print(f"validator {r['validator']:3d} slashed={r['slashed']} {r['balance_before_eth']:.2f} -> {r['balance_after_eth']:.2f} ETH  withdrawable {r['withdrawable_epoch']}{tag}")
        print(f"... {len(out['rows'])} validators slashed, initial penalty {out['initial_penalty_eth_each']:.2f} ETH each, {out['total_initial_penalty_eth']:.1f} ETH total")
