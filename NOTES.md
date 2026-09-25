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
