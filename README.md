# Sealed Inheritance

Inheritance escrow on ENSv2 for ETHGlobal Tokyo 2026.

A will and pre-signed transfers are witness-encrypted to one on-chain condition, no heartbeat record on the owner's ENS name for N finalized epochs. No party holds a key. Anyone can open it once the condition is finalized, and forging the condition means slashable finality votes.

Ethereum decides when it opens. ENS decides where it lives and who may write about it. Validator stake decides what lying costs.

## Status

Started at ETHGlobal Tokyo 2026 kick-off. All application code in this repository is written during the event.

## What is new and what is reused

New, written during the event: everything under `contracts/`, `backend/`, `attack/`, `web/` and `scripts/`.

Reused public libraries and tools, listed with versions as they are added:

- (to be filled)

## Why ENSv2 is load-bearing

(to be filled)

## Progress log

| Time (JST) | Milestone | Result |
|---|---|---|
| Fri 25 Sep, late evening | repository created, skeleton | done |
| Sat 26 Sep, 00:20 | Studio and Opener contracts, 9 Foundry tests | pass |
