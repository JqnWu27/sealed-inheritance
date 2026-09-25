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
