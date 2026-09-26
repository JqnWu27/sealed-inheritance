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

The sealed envelope has two layers. The inner box is sealed to the heir's X25519 public key, read from the heir's ENS name, so only the heir can read the contents after opening. The outer layer is a witness KEM plus authenticated encryption, encapsulated to the public condition and opened by anyone holding a witness. The witness is a finality certificate for a block in which the owner's `heartbeat` record has been silent for N epochs, checked by the conditions in `backend/app/checker.py`, four on Anvil and five on a real chain, where the record is also proven against the state root and the beacon chain's finalized checkpoint is consulted.

The KEM adapter in `backend/app/kem/qap.py` implements the witness KEM for quadratic arithmetic programs of Chang, Wu, Liu, Hsu, Tso and Mambo, "A Witness Encryption for Quadratic Arithmetic Programs", ICISC 2025, LNCS 16487, applied to the ten-constraint silence relation `epoch - heartbeat - N = d >= 0`. Encapsulation uses only the public statement, decapsulation uses a satisfying assignment, and no key is stored anywhere. It is a prototype adapter and we make no security claim of our own for it. The demo's safety does not rest on it. Funds are protected by the slip lock and the weekly window rotation, the vault counter that every heartbeat advances, and the opening condition is enforced by the checker against Ethereum's finalized state. A witness KEM for the full finality relation, where the certificate itself is the witness, is the open problem this project points at.

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
| Sat 26 Sep, 01:45 | Opener records one disclosure per window, 12 tests | pass |
| Sat 26 Sep, 02:00 | static live page reading the name on Sepolia through UniversalResolverV2, GitHub Pages | live |
| Sat 26 Sep, 21:00 | attack in two sizes: a third of the validators is slashed and the will stays sealed, two thirds rewrites the Anvil chain to before the last heartbeat and the will opens | pass |
| Sun 27 Sep, 03:30 | name tree on ENSv2's real PermissionedRegistry: yutotanaka.eth with two subnames in Yuto's own registry, the tree locked by role revocation, one opening hands the three names to Hana, Taka and Yuta, 25 Foundry tests | pass |
| Sun 27 Sep, 02:40 | name tree on ENSv2's real PermissionedRegistry: two subnames in Yuto's own registry, the tree locked by revoking his own roles, one opening hands three names to three heirs, 25 Foundry tests | pass |
| Sat 26 Sep, 02:50 | yutotanaka.eth and hana.eth registered on the ENSv2 Sepolia beta, each with its own permissioned resolver | done |
| Sat 26 Sep, 03:25 | Studio and Opener on Sepolia, heir, vault and key records, scoped setter roles granted and verified | done |
| Sat 26 Sep, 04:20 | first envelope sealed on Sepolia, N = 3 epochs | on chain |
| Sat 26 Sep, 04:43 | watchtower opened it after three finalized epochs of silence, disclosure record written | on chain |
| Sat 26 Sep, 05:00 | a local run reached Sepolia from a shell with Sepolia variables, local scripts now force Anvil, state rebuilt from chain | fixed |
| Sat 26 Sep, 05:50 | fifth check on real chains, the beacon chain finalized checkpoint from two endpoints covers the certificate | pass |
| Sat 26 Sep, 09:00 | full test pass, 12 Foundry, 4 KEM, 14 local steps, five checks on Sepolia | pass |
