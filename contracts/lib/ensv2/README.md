# Vendored ENSv2 registry sources

Minimal, unmodified copy of the ENSv2 contracts needed to compile
`PermissionedRegistry` and `LabelStore` inside this Foundry project, so the local
demo runs the real ENSv2 registry code instead of a mock.

Source: ENSv2 contracts repository (`contracts-v2`), commit
`48b3e2d39513b9dd32ef1850877a29009bc807b9`, folder `contracts/`.
Only the transitive import closure of the two entry points was copied:

- `src/registry/PermissionedRegistry.sol` and its interfaces and `RegistryRolesLib`
- `src/access-control/*` (EnhancedAccessControl, EACBaseRolesLib)
- `src/erc1155/ERC1155Singleton.sol`
- `src/utils/LabelStore.sol`, `LibLabel.sol`, `DelegatedContractNamer.sol`
- `src/reverse-registrar/interfaces/IContractNamer.sol`

Dependencies, copied from the pinned submodules of that commit, kept in their
original layout so relative imports keep working:

- `lib/openzeppelin-contracts` = OpenZeppelin Contracts 5.3.0, commit `e4f70216d759d8e6a64144a9e1f7bbeed78e7079` (MIT)
- `lib/ens-contracts` = ens-contracts 1.7.0, commit `3b1cc225ccdf64581d5fdc81db574f51ba5c8c09` (MIT)

Remappings live in `contracts/remappings.txt`:

```
ensv2/=lib/ensv2/src/
@openzeppelin/contracts/=lib/ensv2/lib/openzeppelin-contracts/contracts/
@ens/contracts/=lib/ensv2/lib/ens-contracts/contracts/
```

No file was edited. Note that the repository `.gitignore` excludes `contracts/lib/`;
add `!contracts/lib/ensv2/` there if this folder should be committed.

Role notes used by the demo (RegistryRolesLib, one nybble per role, admin = role << 128):

- root bitmap for a registry deployer: `EACBaseRolesLib.ALL_ROLES` = `0x1111...1` (64 nybbles)
- name token bitmap: `ROLE_SET_SUBREGISTRY | ROLE_SET_SUBREGISTRY_ADMIN | ROLE_SET_RESOLVER | ROLE_SET_RESOLVER_ADMIN | ROLE_CAN_TRANSFER_ADMIN`
  = `0x1110000000000000000000000000000001100000`
- token ids change on every grant or revoke; store the canonical id `uint256(keccak256(label))` and call `getTokenId(canonical)`
