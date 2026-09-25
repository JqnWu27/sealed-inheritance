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

## The witness-encryption layer and what it follows

The sealed envelope has two layers. The inner box is sealed to the heir's X25519 public key, read from the heir's ENS name, so only the heir can read the contents after opening. The outer layer is a witness KEM plus authenticated encryption, encapsulated to the public condition and opened by anyone holding a witness. The witness is a finality certificate for a block in which the owner's `heartbeat` record has been silent for N epochs, checked by the four conditions in `backend/app/checker.py`.

The KEM adapter in `backend/app/kem/qap.py` implements the witness KEM for quadratic arithmetic programs of Chang, Wu, Liu, Hsu, Tso and Mambo, "A Witness Encryption for Quadratic Arithmetic Programs", ICISC 2025, LNCS 16487, applied to the ten-constraint silence relation `epoch - heartbeat - N = d >= 0`. Encapsulation uses only the public statement, decapsulation uses a satisfying assignment, and no key is stored anywhere. It is a prototype adapter and we make no security claim of our own for it. The demo's safety does not rest on it. Funds are protected by the slip lock and the weekly rotation counter, and the opening condition is enforced by the checker against Ethereum's finalized state. A witness KEM for the full finality relation, where the certificate itself is the witness, is the open problem this project points at.

The `qap` adapter is the default. `backend/app/kem/mock.py` provides the same interface with a backend-held secret for development, is labelled as such, and is selected with `KEM_BACKEND=mock`. `backend/tests/test_qap.py` checks that a satisfying witness recovers the encapsulated key, that a non-satisfying one yields a different key and leaves the outer layer closed, and that silence is counted from the sealing heartbeat.

Related work the design draws on. Witness encryption, Garg, Gentry, Sahai and Waters, STOC 2013. Extractable witness encryption for KZG commitments, Fleischhacker, Hall-Andersen and Simkin, ASIACRYPT 2024. A framework for witness encryption from linearly verifiable SNARKs, Garg, Hajiabadi, Kolonelos, Kothapalli and Policharla, 2025. The public zkenc tool for QAP witness encryption was evaluated in `spike/zkenc/` and not used, see its RESULT.md.

## Progress log

| Time (JST) | Milestone | Result |
|---|---|---|
| Fri 25 Sep, late evening | repository created, skeleton | done |
| Fri 25 Sep, 23:33 | Studio and Opener contracts, 9 Foundry tests | pass |
| Fri 25 Sep, 23:50 | setters switched to DNS-encoded names for ENSv2, namehash library, 10 tests | pass |
| Sat 26 Sep, 00:10 | backend end to end on Anvil, seal, heartbeat, silence, wrong witness sealed, open, heir reads, slip pays after lock | pass |
| Sat 26 Sep, 00:20 | forged-silence attack on the Electra minimal spec, 44 of 64 validators slashed | pass |
| Sat 26 Sep, 00:25 | static UI served by the API, three panels and live records | renders |
| Sat 26 Sep, 00:35 | zkenc spike, fresh clone does not build, circuit and witnesses fine, tool not used | recorded |
| Sat 26 Sep, 01:00 | QAP witness KEM adapter on the silence relation, 4 tests, made the default | pass |
| Sat 26 Sep, 01:05 | standalone watchtower process, opens the envelope from a second terminal | runs |
| Sat 26 Sep, 01:15 | reads switched to resolve(name, data) after checking the deployed Sepolia resolver bytecode, 11 tests | pass |
