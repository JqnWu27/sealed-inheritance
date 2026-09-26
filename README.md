# Conditional Name Inheritance

Repository name: Sealed Inheritance.

The heirs inherit an ENS name, its subnames, and the will sealed on it, when the owner goes silent. No person and no server holds a key. Anyone can open it once the condition is finalized on Ethereum. Forging the condition means forging Ethereum finality, which costs validator stake.

Ethereum decides when it opens. ENS decides where it lives, who may write about it, and who inherits it. Validator stake decides what lying costs.

Built solo at ETHGlobal Tokyo 2026, 25 to 27 September. Everything under `contracts/src`, `contracts/test`, `backend/`, `attack/`, `web/`, `docs/`, `scripts/` and `spike/` was written during the event. `contracts/lib/ensv2` is ENS's own registry code, vendored unmodified.

## Live demo

- Live view of the sealed name on the ENSv2 Sepolia beta: https://jqnwu27.github.io/sealed-inheritance/ . A static page, it reads the chain in your browser through UniversalResolverV2. Nothing on it is served by us.
- Owner yutotanaka.eth and heir hana.eth on https://app.ens.dev , each with its own permissioned resolver. The app now shows Hana as the owner of yutotanaka.eth, because the name was handed over on chain.
- Studio, the vault: [0x56cAf0c53118De955377BBD9C043985abd7BF53E](https://sepolia.etherscan.io/address/0x56cAf0c53118De955377BBD9C043985abd7BF53E). Opener with name handover: [0xbA8Aa8ADa3C4112AE129643539C5FF610C0048e7](https://sepolia.etherscan.io/address/0xbA8Aa8ADa3C4112AE129643539C5FF610C0048e7).
- Three lifecycles on the real chain. Sealed 26 Sep 04:20 JST, opened by the watchtower at 04:43 after three finalized epochs of silence, [tx 0xaf7eb900](https://sepolia.etherscan.io/tx/0xaf7eb9004b3e7080a8123d542b511695b17a90354b4897175b1964b1866f3816). Window 2 opened at 13:09 with the storage proof. Window 3 opened at 20:09 and handed the name to Hana in the same transaction, [tx 0xd51b514f](https://sepolia.etherscan.io/tx/0xd51b514f1c8c7a4ec68d755949e2f45e7b885dbeff6ef8e96d1cc2d1a5c653cf), events Opened and NameHandedOver.
- Video: (link)
- The interactive demo, Seal, Heartbeat, Try to open, the two attack sizes and the name tree, runs locally against Anvil with one command, see Setup. It is the flow in the video, because on Sepolia one epoch takes 6.4 minutes.

## The story

Yuto owns yutotanaka.eth. His two subsidiaries are subnames under it, yuto.yutotanaka.eth and tanaka.yutotanaka.eth, in a registry of his own. His heirs are Hana, who gets the company name, and Taka and Yuta, who get one subsidiary each.

Yuto writes a will and seals it. The will is encrypted for Hana's key, read from hana.eth, and then encrypted to one public condition: no `heartbeat` record on yutotanaka.eth for N finalized epochs. Every week Yuto checks in by pressing Heartbeat, which writes the current epoch to the heartbeat record on his name, seals a fresh envelope and opens a new window. The demo page shows a countdown, how many epochs he has left before the will can open.

When he stops checking in, anyone can assemble the witness from the finalized chain and open the envelope. The Opener contract then does three things in one transaction: it writes a `disclosure` record on the name, it hands yutotanaka.eth to Hana, and it hands the two subnames to Taka and Yuta. Hana reads the will with her own key. Nobody paid anything.

Before he goes silent, Yuto locks the tree: he revokes from himself the roles that could add, remove or replace a subname. Roles travel with the name, so Hana inherits the parent without them and cannot touch the subsidiaries.

Suppose Hana is impatient and runs validators. She cannot steal a key, because there is none. To open early she must present a finalized history without the heartbeat, which means her validators sign two conflicting finality votes for one epoch. The attack panel runs that on Ethereum's own executable specification, in two sizes. With a third of the validators, 22 of 64, all of them are slashed and the will stays sealed, because a third cannot finalize anything alone. With two thirds, 44 of 64, they can finalize the forged history, and on the local chain the demo does exactly that: it rewinds the chain to before Yuto's last check-in, the silence passes, the will opens and the names move, and her validators are slashed all the same. On mainnet that second case means controlling about 28.9 million of the 43.4 million ETH staked, and losing at least 14.5 million of it. That is the price of opening early.

The demo page has a Start over button that rewinds the local chain to the moment after deployment, so the honest case and the attack cases can be shown one after the other.

The vault contract can also hold ETH and pay pre-signed transfer slips after a lock. That part is complete and tested but hidden in the demo, add `?money` to the demo URL to see it.

## Why ENSv2 is load-bearing

Everything the protocol needs to remember lives on the owner's name, and the resolver enforces who may write each record.

| Record | Written by | Meaning |
|---|---|---|
| `heir` | owner | the heir's name, whose `pubkey.x25519` record wraps the envelope |
| `vault` | owner | the Studio contract that holds the window counter and the sealed envelopes |
| `heartbeat` | Studio, scoped role | epoch of the last check-in, the liveness signal the condition reads |
| `sealed` | Studio, scoped role | hash of the current envelope and the public condition it is encrypted to |
| `disclosure` | Opener, scoped role, once per window | pointer to the opened envelope, written only after the chain says the condition holds |

Five ENSv2 functions carry the demo. Four run on the Sepolia beta, the fifth on ENSv2's own registry code on the local chain.

1. A role for one record key. The owner grants `ROLE_SET_TEXT` scoped to a single key with `grantSetterRoles`. Studio may write `heartbeat` and `sealed` and nothing else, the Opener may write `disclosure` and nothing else. Both grants were made on Sepolia and verified with `hasRoles`.
2. The owner's own resolver. The resolver is a proxy deployed for him through the VerifiableFactory when he registered, so the roles are his to give and to take back, and the permission structure is shared with nobody.
3. The name as a token. yutotanaka.eth is a token in the ETHRegistry. The owner approved the Opener as operator, and at the opening the Opener calls `safeTransferFrom` to move the name to the heir, in the same transaction that writes the disclosure.
4. UniversalResolverV2. Every read, in the backend, the watchtower and the live page, goes through `findResolver` and `resolve(name, data)`, so the heir needs only the name.
5. A subname with its own control. The subsidiaries are subnames registered in a `PermissionedRegistry` that Yuto deployed and set as the subregistry of yutotanaka.eth with `setSubregistry`. Yuto revokes the registrar and unregister roles on that registry and the set-subregistry role on the parent token with `revokeRoles` and `revokeRootRoles`. Because granting a role needs its admin bit and both bits are revoked, no future owner can recreate them. The Opener holds only operator approval and hands the subnames to their heirs at the opening.

None of this exists in ENSv1. An approved operator could rewrite every record, including the heir, and a subname could only be locked by burning a fuse, one way. The registry tree runs on the local chain with ENS's own `PermissionedRegistry` and `LabelStore` code, vendored under `contracts/lib/ensv2` from ensdomains/contracts-v2 at commit 48b3e2d, the same contract that owns yutotanaka.eth on Sepolia. On Sepolia the single name moved; the tree is not deployed there yet.

ENS does not keep the secret and does not price the cheating. Witness encryption keeps the secret. Validator stake prices the cheating. ENS decides where the secret lives, who may write about it, who inherits the name, and how the heir finds it.

## The open condition

The envelope opens for anyone who presents a finality certificate for an epoch E such that the name showed no heartbeat for N epochs at that finalized block, within the statement's horizon. The checker in `backend/app/checker.py` enforces it as five checks, the fifth on real chains only.

1. Finality. The certificate names the epoch's boundary block, hash and state root, signed by the light-client quorum, and the block exists.
2. Binding. Reading `heartbeat` on the name through its resolver at that block returns h, and an eth_getProof storage proof of the record, verified locally against the state root inside the certificate, gives the same h.
3. Predicate. max(h, from) + N is at most E, where `from` is the epoch of the heartbeat that sealed this window.
4. Horizon. anchor is at most E and E is at most anchor + H.
5. Consensus. The beacon chain's finalized checkpoint, fetched from two independent public beacon nodes, covers the certificate's block, and the execution chain agrees on that block.

The public statement, carried in the `sealed` record and inside the ciphertext, pins the chain, the name, the resolver, N, `from`, the anchor block hash, H and the relation id, so an envelope cannot be replayed on another chain, name or resolver.

## The witness-encryption layer and what it follows

The sealed envelope has two layers. The inner box is sealed to the heir's X25519 public key, read from the heir's ENS name, so only the heir can read the contents after opening. The outer layer is a witness KEM plus authenticated encryption, encapsulated to the public condition and opened by anyone holding a witness. The witness is a finality certificate for a block in which the owner's `heartbeat` record has been silent for N epochs, checked by the conditions in `backend/app/checker.py`, four on Anvil and five on a real chain, where the record is also proven against the state root and the beacon chain's finalized checkpoint is consulted.

The KEM adapter in `backend/app/kem/qap.py` implements the witness KEM for quadratic arithmetic programs of Chang, Wu, Liu, Hsu, Tso and Mambo, "A Witness Encryption for Quadratic Arithmetic Programs", ICISC 2025, LNCS 16487, applied to the ten-constraint silence relation `epoch - heartbeat - N = d >= 0`. Encapsulation uses only the public statement, decapsulation uses a satisfying assignment, and no key is stored anywhere. It is a prototype adapter and we make no security claim of our own for it. The demo's safety does not rest on it. Funds are protected by the slip lock and the weekly window rotation, the vault counter that every heartbeat advances, and the opening condition is enforced by the checker against Ethereum's finalized state. A witness KEM for the full finality relation, where the certificate itself is the witness, is the open problem this project points at.

The `qap` adapter is the default. `backend/app/kem/mock.py` provides the same interface with a backend-held secret for development, is labelled as such, and is selected with `KEM_BACKEND=mock`. `backend/tests/test_qap.py` checks that a satisfying witness recovers the encapsulated key, that a non-satisfying one yields a different key and leaves the outer layer closed, and that silence is counted from the sealing heartbeat.

Related work the design draws on. Witness encryption, Garg, Gentry, Sahai and Waters, STOC 2013. Extractable witness encryption for KZG commitments, Fleischhacker, Hall-Andersen and Simkin, ASIACRYPT 2024. A framework for witness encryption from linearly verifiable SNARKs, Garg, Hajiabadi, Kolonelos, Kothapalli and Policharla, 2025. The public zkenc tool for QAP witness encryption was evaluated in `spike/zkenc/` and not used, see its RESULT.md.

## What is real and what is emulated

| Piece | In the demo | Real or emulated |
|---|---|---|
| ENSv2 names, resolvers, roles, records | Sepolia beta, ENS Labs contracts as deployed | real |
| ENSv2 registry tree, subnames, lock | ENS's own PermissionedRegistry code, on Anvil | real code, local chain |
| Studio and Opener | deployed on Sepolia, 25 Foundry tests in total, 9 of them against the real registry | real |
| Which block is final | the beacon chain's finalized checkpoint, two endpoints | real, trusted endpoints |
| Who vouches for finality | a certificate signed by four demo light-client keys | emulated |
| The heartbeat value | read through the resolver at the finalized block and proven by a Merkle storage proof against the state root the certificate signs | real, verified locally |
| Witness KEM | prototype adapter on the silence arithmetic | prototype, no security claim |
| Slashing | `process_attester_slashing` on the consensus spec's minimal preset, 64 validators | real protocol code, separate toy validator set |
| Rewriting history for the two-thirds case | Anvil snapshot and revert | local chain only |

The design ties early opening to slashable evidence. In the full design, with extractable witness encryption for this relation, an early decryption is itself a forged finality certificate, and two finalized histories for one epoch mean at least one third of the validators signed both. The demo shows the mechanism end to end and states exactly where the emulation is. Verifying the sync committee's signature locally is the one upgrade left that makes the finality evidence itself cryptographic rather than trusted.

## The watchtower, an agent anyone can run

`backend/watchtower.py` is a monitoring agent with no privilege. It watches the finalized chain, evaluates a fixed policy, the five checks, and when the policy holds it acts on chain by opening the envelope and writing the disclosure through the Opener contract, paying the gas from its own account. It cannot act early, because early there is no witness and therefore no key. It cannot be bribed to stay silent, because anyone else can run the same agent. It opened the three Sepolia envelopes, and the third opening handed the name to Hana. MultiBaas was not used in this build.

## Setup

Requirements: WSL or Linux, Foundry, Python 3.12.

```
git clone https://github.com/JqnWu27/sealed-inheritance && cd sealed-inheritance
cd contracts && forge install foundry-rs/forge-std && forge test && cd ..
python -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt
VENV=$PWD/.venv bash scripts/e2e-local.sh
```

The last line starts Anvil, deploys the resolver, two ENSv2 registries with the name tree, Studio and Opener, locks the tree, and runs seal, heartbeat, silence, wrong witness, open with the three handovers, heir reads, transfer rejected, transfer paid, the forged-silence attack, and hands the names back. Then open http://localhost:8000/ for the UI, press Start over for a clean chain, and run `python backend/watchtower.py` in a second terminal as the opener anyone can run. The local silence window is 25 epochs, 200 seconds at one block a second; the +silence window button mines all of it.

The attack needs the consensus reference implementation in its own venv: `pip install -e <ethereum/consensus-specs>` and `SPEC_PYTHON=<that venv>/bin/python`.

Against Sepolia, once two names exist: `RPC_URL=… RESOLVER=… bash scripts/sepolia-all.sh` for the contracts, records and roles, `scripts/sepolia_handover.py all` for the Opener with handover, then `set -a; source backend/.env.sepolia; set +a` and `uvicorn app.api:app` from `backend/`. `scripts/rebuild_state.py` rebuilds the local state from the on-chain envelopes at any time.

## Next steps

- The tree on Sepolia: deploy the registry, point the name at it, register the subnames, deploy the Opener with the handover list, lock, seal, open. Everything is written, it needs the transactions and the waiting.
- A sealed assignment list. Today the handover list is set on chain in advance and is public. In the next version the list lives inside the envelope, the checker signs it with the opening, and the Opener executes the signed list, so nobody learns who inherits what before the opening.
- Local verification of the sync committee signature, so the finality evidence is cryptographic rather than trusted.

## What is new and what is reused

New, written during the event: everything under `contracts/src`, `contracts/test`, `backend/`, `attack/`, `web/`, `docs/`, `scripts/` and `spike/`.

Reused public libraries and tools, with the versions used:

- Foundry 1.3.2, forge for the contract tests and anvil for the local chain
- forge-std 1.16.2, test harness only, installed under contracts/lib and not committed
- ENSv2 Sepolia beta contracts by ENS Labs, registry, permissioned resolver, UniversalResolverV2, VerifiableFactory, used as deployed, addresses in NOTES.md
- ensdomains/contracts-v2 at commit 48b3e2d, `PermissionedRegistry`, `LabelStore` and the files they import, vendored unmodified under contracts/lib/ensv2 with the OpenZeppelin 5.3.0 and ens-contracts 1.7.0 files they depend on
- web3.py 8.0.0 and eth-account 0.14.0, RPC and EIP-712 signing
- py_ecc 8.0.0, BN128 pairings for the QAP witness KEM adapter
- PyNaCl 1.6.2, X25519 sealed box and XSalsa20-Poly1305 secret box
- py-trie and rlp, Merkle storage proofs
- cbor2 6.1.4, envelope encoding
- FastAPI 0.141.1 and uvicorn 0.54.0, the demo API that also serves web/
- httpx 0.28.1 and pytest 9.1.1, watchtower and beacon client, tests
- viem 2 from esm.sh, in the static live page only
- ethereum/consensus-specs at commit 8c12cae, Electra minimal preset, for `process_attester_slashing` and its genesis and key helpers
- circom 2.2.2 and snarkjs 0.7.5, only in spike/zkenc to compile the silence circuit
- zkenc by flyinglimao, evaluated at commit 2977641 in spike/zkenc, not used, see spike/zkenc/RESULT.md

## Team

Yihsuan Wu, PhD student at Waseda University, cryptography and DeFi, GitHub JqnWu27. Built solo with Claude Code as the assistant, see AI_USAGE.md.

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
