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
