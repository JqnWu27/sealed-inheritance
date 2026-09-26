# Notes

Addresses, ABIs, transaction hashes and anything a judge could verify. Append as you go, with the time.

## ENSv2 on Sepolia (from docs.ens.domains/learn/deployments, "Sepolia (ENSv2 Beta)", read Sat 26 Sep 00:40 JST)

- ETHRegistry, Permissioned Registry for .eth: `0x657ea849311d3d5823348dded7c2aaafb3ede09e`
- UserRegistryImpl: `0xa80338aaa8d23831cea25e858d1774534abb0263`
- WrapperRegistryImpl: `0x2741543c3b14640b97bc70a233318032f7e35bac`
- UniversalResolverV2: `0x5d25c1d6acbb71b7a28aa7899618a3412a8303e3`
- PublicResolverV2: `0xd7e590ad0e92a6ac1d81f4483a9b951d3585a50f`
- VerifiableFactory (deploys per-account permissioned resolvers): `0x9e726eb570beb6bceb495ab8cda7df517d4e841c`
- ETHRegistrar: `0xabe76f6c8dfced81aa5a2bb8034202a7136b94ca`
- BatchRegistrar: `0xbe68ff9afc7d5a1864ffef5c82de0a1c13e6b529`
- RootBatchRegistrar: `0xcf5d485a531863856ed9d8a10d61707de7f06c21`

Permissioned resolver facts that shape our contracts:

- Setters take the DNS-encoded name as `bytes`, reads take the `bytes32` namehash.
- `setText(bytes name, string key, string value)` needs `ROLE_SET_TEXT = 1 << 4` on the key resource `keccak256(bytes(key))` or on the root.
- `grantSetterRoles(bytes setterCalldata, address account)` grants the argument-scoped role encoded in a setter call, for example `abi.encodeCall(setText, ("", "heartbeat", ""))`. Only selector and key argument matter.
- Admin role for a role is `role << 128`. Revoke with `revokeRoles(resource, roleBitmap, account)`.
- Each account deploys its own resolver proxy via the VerifiableFactory, `initialize(grants, calls)`.
- Sources: github.com/ensdomains/contracts-v2, npm `@ensdomains/contracts-v2`.

## Our names

- Owner name:
- Heir name:

## Our contracts

- Studio (Sepolia):
- Opener (Sepolia):

## Accounts

- Owner:
- Heir:
- Deployer / watchtower:

## ENSv2 beta facts verified against Sepolia bytecode, Sat 26 Sep 01:10

- PermissionedResolverImpl 0x14f09fd05d4585759e54844dc9b00147131cf243, RootRegistry 0x9703dbd26dab89504490994138cf2c575251a9ce. Deployment commit in the ENS docs table 71a3b7339dbc55ab47667abdfe8303bac4f4c24e.
- The deployed implementation has setText(bytes name, string key, string value), grantSetterRoles(bytes setter, address), revokeRoles(uint256 resource, uint256 roleBitmap, address), resolve(bytes name, bytes data), getRecordId(bytes32), decodeSetter(bytes), initialize((address,uint256)[] grants, bytes[] calls). Studio and Opener match it.
- It has no bare text(bytes32,string) getter. Reads go through resolve(name, abi.encode(text(node,key))) and return abi encoded string. The backend reads this way and falls back to text() for older resolvers. MockResolver implements resolve the same way.
- PublicResolverV2 0xd7e5… is the ENSv1 style resolver with setText(bytes32,…) and owner or operator checks, no scoped roles. Not used for Ken. Fine for Hana's pubkey.x25519 record.
- The contracts-v2 main branch has moved on, its PermissionedResolver takes bytes32 node and uses authorizeTextRoles. Its Sepolia artifacts point at newer addresses (impl 0x7e4b2d59…). We target the docs table, which is what the beta app uses.
- Text key resource id = uint256(keccak256(bytes(key))). ROLE_SET_TEXT = 1<<4, admin = role<<128.
- ETHRegistry 0x657e… has setResolver(uint256 anyId, address), getResolver(string label), ownerOf(uint256). VerifiableFactory 0x9e72… deployProxy(address impl, uint256 salt, bytes initData) returns address and emits ProxyDeployed(sender, proxyAddress, salt, implementation).
- Deploying Ken's own resolver: deployProxy(impl, salt, initialize([(owner, ALL_ROLES)], [])) then registry.setResolver(tokenId of label, proxy). The beta app may offer this in its UI, which is the simpler route.

## Names registered on the Sepolia beta, Sat 26 Sep 03:05

- yutotanaka.eth registered from the ENS beta app by the demo owner 0xf5AA5FedB76149ECD6dEcCC7F97581db3e1B3871, one year, paid in the beta's test USDC. Registry tokenId 0x3a973f4104237b379cc55e469e6f768658777ac585de44694033269800000000, ownerOf = the demo owner.
- The app deployed Yuto's own permissioned resolver at 0xaa1825716cb9d4c8518BA378734D783bAabd5f80, a proxy to PermissionedResolverImpl 0x14f09fd0…cf243. The demo owner holds every root role on it (roles bitmap 0x1111…1111), so it can write heir and vault and grant the scoped setter roles itself. No resolver deployment or setResolver needed. Run the Sepolia script with RESOLVER=0xaa1825716cb9d4c8518BA378734D783bAabd5f80.
- The app registers through a smart account with sponsored gas, so the owner's transaction count stays 0 until our own scripts run.
- hana.eth registered from the beta app by the demo heir 0x5df2F94dFC4491BB90Fa98C9a817e43d32FFAf32, one year, premium four-character price paid in test USDC. ownerOf = the demo heir. The app deployed Hana's own permissioned resolver at 0x4499D90fDEAD0453f1d123B3109f9b0912Abc14f, same implementation, and the heir holds every root role on it, so the pubkey.x25519 record is written with the DNS-name setText from the heir key.

## Sepolia deployment, Sat 26 Sep 03:25, scripts/sepolia-all.sh

- Studio (vault) 0x56cAf0c53118De955377BBD9C043985abd7BF53E, deployed by the demo owner, name yutotanaka.eth, resolver 0xaa1825716cb9d4c8518BA378734D783bAabd5f80, 32 blocks per epoch.
- Opener 0xB5f977177045f674c1672Ef52CDaAC6101E40C10, checker 0x57aF4D507b504baF5CD5FF08c685C8EB3b9e07A6.
- Records on yutotanaka.eth: heir = hana.eth (tx 0x927dd046…), vault = Studio (tx 0x8f0f5609…). hana.eth pubkey.x25519 = 0x1a5144db…4127 (tx 0x839f9bac…).
- Scoped roles on Yuto's resolver: setText[heartbeat] and setText[sealed] to Studio (tx 0xc5cdfa9c…, 0x6b2fc5f9…), setText[disclosure] to Opener (tx 0x4f9d9233…), each confirmed with hasRoles.
- Live page https://jqnwu27.github.io/sealed-inheritance/ reads these through UniversalResolverV2.
- Sepolia parameters: N = 3 epochs, lock 1200 s, H set in backend/.env.sepolia (never committed).
- First seal on Sepolia, Sat 26 Sep 04:20: window 1, Studio.heartbeat tx 0x8b1a12570172…, anchor epoch 368162, silence counted from 368163, heartbeat record 368164, N = 3, H = 600, envelope 7684 bytes, transfer slip 0.01 ETH to hana.eth. The condition holds from finalized epoch 368167.
- 04:55, a local demo run from a shell that still held the Sepolia variables deployed a throwaway MockResolver 0xa92441Dd…, Studio 0x033C86D3… and Opener 0x5DC2d888… on Sepolia and sealed twice against them, about 0.018 ETH. They are unused. The local scripts now force Anvil and deploy_local.py refuses any other chain. The Sepolia state file was rebuilt from the on-chain envelope with scripts/rebuild_state.py, all four checks pass for window 1 of Studio 0x56cAf0c5….
- 05:50, fifth check added for real chains, "consensus": the beacon chain's finalized checkpoint, fetched from two public Sepolia beacon endpoints (publicnode, ChainSafe Lodestar), must cover the certificate's block and the execution chain must agree on that finalized block. Verified read-only against window 1: five checks ok. Configured by BEACON_API in .env.sepolia, absent on Anvil so the local trace keeps four checks. Still trusts the endpoints, a local sync-committee verification is the next step.
- Sepolia envelope opened, Sat 26 Sep 04:43 JST, by the watchtower loop started at 04:23: Opener.recordOpening tx 0xaf7eb9004b3e7080a8123d542b511695b17a90354b4897175b1964b1866f3816, block 11781377, sender the watchtower 0x52146f13…BA3a, disclosure record window=1;inner=0x2d29174db2af28…. Full lifecycle on the real chain: seal 04:20, silence, open 04:43, all visible on the live page. With the consensus check added later, /witness shows five ok checks for the same window.

## State binding upgrade, Sat 26 Sep 12:20, storage proofs against the signed state root

- Slot discovery: forked Sepolia into Anvil (port 8546) and traced resolve(yutotanaka.eth, text(heartbeat)) with debug_traceCall. Four SLOADs: the EIP-1967 implementation slot (proxy), the record id slot 0x770250b6…eb941 (value 1), and the text slot 0x8da16641…e776d (value "368213" as a short string). Brute force over plain storage slots gives the formula: _recordIds at slot 259, _records at slot 260, Record.texts at struct offset 3, so texts[key] = keccak(bytes(key) . (keccak(recordId . 260) + 3)). Cross-checked on chain: "heir" decodes to hana.eth, "sealed" is a long string of 193 bytes. Struct order from AbstractRecordResolver.sol at commit 71a3b73: contenthash, name, addresses, texts, datas, abis, interfaces.
- MockResolver layout: records at slot 2, records[node][keccak(key)] = keccak(keccak(key) . keccak(node . 2)). Anvil serves eth_getProof.
- Public RPC history: publicnode serves eth_getProof and eth_getStorageAt for about the last 128 to 140 blocks only. The light client on real chains now certifies the finalized block itself (age about 65 to 95 blocks) instead of the epoch boundary (up to 126 blocks), so proofs stay inside the window. No other public Sepolia RPC tested serves historical proofs (drpc, 1rpc, tenderly, blockpi).
- backend/app/stateproof.py verifies the account proof against the certificate's state root with py-trie, checks the storage root, proves the record id slot and the text slot (and the data words of long strings), decodes the Solidity string, and accepts a layout only if the proven value equals the resolve() value. The binding check fails if the proof fails. STATE_PROOF=off restores the plain read.
- Verified: Sepolia window 2, five checks ok with "storage proof (ens-beta, 2 slots, 8 account + 6 storage trie nodes)", 2.3 s. Anvil e2e 14 steps ok with the mock layout. Tests: 3 new unit tests for slot derivation and string decoding, 7 backend tests total.
- A second window was sealed on Sepolia at about 09:50 (heartbeat epoch 368213, window 2) from the UI while the Sepolia backend was up. Owner balance 0.0158 ETH afterwards. Window 2's condition holds and it can be opened by the watchtower to show the new check live.
- Window 2 opened on Sepolia, Sat 26 Sep 13:09 JST, by the watchtower with all five checks including the storage proof (ens-beta, 2 slots, 8 account + 6 storage trie nodes against state root 0x024bd2871d…), certificate block 11783683, Opener.recordOpening tx 0xd2fc55e5e558…, disclosure record now window=2. The watchtower previously stopped at any disclosure record, it now compares the disclosed window with the live window.

## Name handover, Sat 26 Sep 18:40

- Opener.setHandover(dnsName, registry, tokenId, heir), callable only by the current owner of the token. recordOpening now also calls registry.safeTransferFrom(owner, heir, tokenId, 1, "") if the owner approved the Opener as operator, emitting NameHandedOver, otherwise HandoverSkipped with the reason. The handover never blocks the disclosure. 16 Foundry tests.
- Anvil: deploy_local.py deploys MockRegistry, mints the name token (id = keccak(label)) to the owner, approves the Opener, plans the handover to the heir. e2e step 8b prints the owner after the opening (heir), step 16 hands the name back for the manual demo. The UI shows "owner of the name" as a sixth record tile and "yutotanaka.eth is now owned by Hana" under the will. Money controls (transfer, Submit, +lock) are hidden unless the page URL has ?money.
- Sepolia: ETHRegistry has safeTransferFrom(address,address,uint256,uint256,bytes), setApprovalForAll, isApprovedForAll, ownerOf, getTokenId. yutotanaka.eth token id 0x3a973f41…0000, owned by the demo owner. scripts/sepolia_handover.py deploys a new Opener, regrants the disclosure role, approves it and plans the handover. Irreversible once opened: the name moves to the heir's key.
- Sepolia handover wired, Sat 26 Sep 19:45: new Opener 0xbA8Aa8ADa3C4112AE129643539C5FF610C0048e7 (tx 0x2c67db98…), disclosure setter role granted (tx 0x83bbf7a4…, hasRoles True), owner approved it as operator on ETHRegistry (tx 0xdfbafd11…), setHandover to the heir 0x5df2…AF32 (tx 0x8b451c98…). The old Opener 0xB5f9…0C10 keeps its disclosure role, unused. The name moves at the next opening.
- Sepolia handover done, Sat 26 Sep 20:09 JST: the watchtower opened window 3 through the new Opener, tx 0xd51b514f1c8c7a4ec68d755949e2f45e7b885dbeff6ef8e96d1cc2d1a5c653cf, block 11785850. Events in that one transaction: Opened(window 3) and NameHandedOver(from 0xf5AA…3871 to 0x5df2…AF32). ETHRegistry.ownerOf now returns the heir. From here the demo owner no longer owns yutotanaka.eth, its resolver and roles are unchanged, and later Sepolia openings report "heir already owns the name".

## Two attack buttons, Sat 26 Sep 21:10

- The attacker panel is Malicious Hana, an impatient heir who runs validators. Two buttons. "Forge silence, one third" runs attack/slashing.py with 22 of 64 forgers: they sign two finality votes for one epoch, are slashed by the spec, and Try to open stays sealed, because a third cannot finalize on its own. "Forge silence, two thirds: rewrite history" runs it with 44 of 64 and, on Anvil only, does what two thirds can do: evm_revert to the snapshot taken right after the previous window, so the owner's last heartbeat never happened, then mines the silence. Try to open then opens the previous window and hands the name to Hana.
- Snapshots: api.roll() takes evm_snapshot after each window on Anvil and stores it in the state file under snapshots[window]; /attack/rewrite reverts to snapshots[window-1], re-snapshots, mines blocks_per_epoch*(window_epochs+2) blocks. Refused on any chain that is not Anvil. Tested: seal (window 5), heartbeat (6), one third slashed and sealed with predicate:no, rewrite to window 5 with heartbeat epoch 129, open, NameHandedOver, owner = heir.
- Mainnet numbers for the script: about 40.7 million ETH staked (Sep 2026), two thirds is about 27 million ETH to control, a third is about 13.6 million ETH, which is the minimum that gets slashed when two finalized histories conflict.

## Name tree on ENSv2's real registry, Sun 27 Sep 02:40, Anvil

- The local demo no longer uses MockRegistry. It runs ENSv2's own PermissionedRegistry and LabelStore, vendored unmodified from github.com/ensdomains/contracts-v2 at commit 48b3e2d (contracts/lib/ensv2, with the OpenZeppelin and ens-contracts files they import, remappings in contracts/remappings.txt). Compiled with solc 0.8.30, runtime 23,457 bytes.
- Tree: a parent registry stands in for the .eth registry and holds yutotanaka.eth. Yuto's own registry is set as its subregistry and holds yuto.yutotanaka.eth and tanaka.yutotanaka.eth, each with the mock resolver and a "company" record. Heirs: Hana gets the parent, Taka (Anvil account 8) and Yuta (account 9) get the children. Opener.setHandovers(name, list) plans all three; recordOpening transfers them after writing the disclosure, one NameHandedOver per name.
- The lock, done at deploy: Yuto revokes register and unregister (and their admin bits) on his registry's root, and set-subregistry (and admin) on the yutotanaka token and on the parent registry's root. EnhancedAccessControl lets an admin-bit holder revoke from himself, and the admin bits cannot be granted again after registration, so nobody can add, remove or re-point a child afterwards. Verified in EnsV2Tree.t.sol, negative control included: without the lock Hana can swap the subregistry and Yuto can unregister a child.
- Token ids regenerate when token roles change, so only canonical ids (keccak of the label) are stored and getTokenId is called before ownerOf or a transfer. Roles travel with the token on transfer.
- Tests: 25 Foundry tests (8 Opener, 8 Studio, 9 EnsV2Tree), 7 backend tests. e2e 17 steps, step 7 opens and hands over three names, step 16 hands them back by impersonating the heirs.
- Sepolia is unchanged: one name, the old handover, no subregistry. The UI shows the tree block only when the backend has a SUBREGISTRY.

## Start over, heartbeat due, Sun 27 Sep 05:10

- Start over button (Anvil only): when the backend starts on a fresh Anvil with nothing sealed it takes a genesis evm_snapshot and stores it in the state file; POST /reset reverts to it, forgets the windows and re-snapshots. The chain goes back to the moment after the deployment: window 0, nothing sealed, every name with Yuto, vault full. Reloading the page never does this. Sepolia cannot be reset. Verified: reset, honest opening (three handovers), reset, seal, heartbeat, two-thirds rewrite, opening (three handovers), reset, all owners back to Yuto each time.
- The clock shows "heartbeat due in X epochs" and the heartbeat tile says before which finalized epoch Yuto must check in again, from the sealed record (from, N) and the finalized epoch; it turns red once the silence is complete and reads "opened" after the disclosure.
- A heartbeat sent right after a seal sometimes reverted (e2e step 4, and reproduced on demand): cast run shows ReentrancySentryOOG, the transaction ran out of gas at the heartbeat SSTORE. The gas estimate is taken one block before mining; when an epoch boundary falls in between, the record changes from a same-value write to a new-value write and the exact estimate is short. chain.send now adds 25 percent plus 60k gas to every estimate. Verified three seal-then-immediate-heartbeat pairs after the fix. The initializer also advances one epoch before its heartbeat step (3b).
- Local N is 25 epochs (200 s at one block a second, 8 blocks an epoch) so the honest silence cannot pass by itself while the attack is narrated; H is 90. +silence window mines the whole window.
