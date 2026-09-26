"""Deploy the demo to a local Anvil node with the MockResolver standing in for
the ENSv2 permissioned resolver and two real ENSv2 PermissionedRegistry contracts
holding the name tree, then write backend/.env.local.

Usage (from repo root, backend venv):
    python scripts/deploy_local.py [--rpc http://127.0.0.1:8545]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from eth_account import Account  # noqa: E402
from eth_utils import keccak  # noqa: E402
from web3 import Web3  # noqa: E402

from app.chain import Chain  # noqa: E402
from app.config import load_keys, settings  # noqa: E402
from app.names import dns_encode, namehash  # noqa: E402

ETH = 10**18
ZERO = "0x0000000000000000000000000000000000000000"
FOREVER = 2**64 - 1

# ENSv2 RegistryRolesLib (contracts/lib/ensv2/src/registry/libraries/RegistryRolesLib.sol):
# one nybble per role, the admin counterpart of a role sits 128 bits higher.
ROLE_REGISTRAR = 1 << 0
ROLE_REGISTER_RESERVED = 1 << 4
ROLE_SET_PARENT = 1 << 8
ROLE_UNREGISTER = 1 << 12
ROLE_RENEW = 1 << 16
ROLE_SET_SUBREGISTRY = 1 << 20
ROLE_SET_RESOLVER = 1 << 24
ROLE_CAN_TRANSFER_ADMIN = (1 << 28) << 128
ROLE_SET_URI = 1 << 36


def with_admin(roles: int) -> int:
    return roles | (roles << 128)


# a registry's root account: every role with its admin bit, plus the right to transfer
ALL_ROLES = with_admin(ROLE_REGISTRAR | ROLE_REGISTER_RESERVED | ROLE_SET_PARENT | ROLE_UNREGISTER | ROLE_RENEW
                       | ROLE_SET_SUBREGISTRY | ROLE_SET_RESOLVER | ROLE_SET_URI) | ROLE_CAN_TRANSFER_ADMIN
# a name owner: may point the name at a subregistry and a resolver, and may transfer it
OWNER_ROLES = with_admin(ROLE_SET_SUBREGISTRY | ROLE_SET_RESOLVER) | ROLE_CAN_TRANSFER_ADMIN

# Taka and Yuta, the apprentices who inherit the child names: Anvil's default accounts 8 and 9
TAKA = "0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f"
YUTA = "0xa0Ee7A142d267C1f36714E4a8F75612F20a79720"
CHILDREN = [("yuto", TAKA, "Taka", "Yuto Design"), ("tanaka", YUTA, "Yuta", "Tanaka Works")]  # label, heir, heir label, company record


def canonical(label: str) -> int:
    """uint256(keccak256(label)). The registry keeps a version in the low 32 bits of the live token id,
    and that version moves whenever roles change, so every stored id is canonical and getTokenId maps it."""
    return int.from_bytes(keccak(text=label), "big")


def deploy_label_store(chain: Chain, key: str) -> str:
    """The shared label database. The demo build has a bare constructor, the upstream one takes a contract namer."""
    ctor = [e for e in chain.abi("LabelStore") if e["type"] == "constructor"]
    args = [ZERO] * len(ctor[0]["inputs"]) if ctor else []
    return chain.deploy("LabelStore", key, *args)


def revoke(chain: Chain, key: str, reg, any_id: int | None, roles: int, owner: str, what: str) -> None:
    """One step of the lock. Root roles go through revokeRootRoles, the registry refuses revokeRoles(0, ...).
    A revert is reported and never fails the deploy."""
    try:
        fn = reg.functions.revokeRootRoles(roles, owner) if any_id is None else reg.functions.revokeRoles(any_id, roles, owner)
        chain.send(fn, key)
        print(f"lock      revoked {what}")
    except Exception as e:
        print(f"WARNING   lock not applied, {what}: {str(e)[:140]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", default=settings.rpc_url)
    a = ap.parse_args()

    keys = load_keys()
    chain = Chain(a.rpc, ROOT / "contracts" / "out")
    if not chain.is_anvil():
        sys.exit(f"deploy_local.py only runs against Anvil, refusing {a.rpc}. For Sepolia use scripts/sepolia-all.sh.")
    owner = Account.from_key(keys["owner"])
    checker = Account.from_key(keys["checker"])
    watchtower = Account.from_key(keys["watchtower"])
    for acct in (owner, watchtower):
        chain.set_balance(acct.address, 100 * ETH)

    owner_dns = dns_encode(settings.owner_name)
    owner_node = namehash(settings.owner_name)
    heir_node = namehash(settings.heir_name)

    resolver = chain.deploy("MockResolver", keys["owner"])
    R = chain.contract("MockResolver", resolver)
    chain.send(R.functions.setOwner(owner_node, owner.address), keys["owner"])
    chain.send(R.functions.setOwner(heir_node, owner.address), keys["owner"])  # demo: owner manages both names locally

    studio = chain.deploy("Studio", keys["owner"], owner.address, owner_dns, resolver, settings.blocks_per_epoch)
    opener = chain.deploy("Opener", keys["owner"], checker.address, resolver)

    # scoped grants, mirroring grantSetterRoles on ENSv2
    for key in ("heartbeat", "sealed"):
        chain.send(R.functions.grantSetter(owner_node, key, studio, True), keys["owner"])
    chain.send(R.functions.grantSetter(owner_node, "disclosure", opener, True), keys["owner"])

    # owner-written records
    chain.send(R.functions.setText(owner_dns, "heir", settings.heir_name), keys["owner"])
    chain.send(R.functions.setText(owner_dns, "vault", studio), keys["owner"])
    chain.send(R.functions.setText(dns_encode(settings.heir_name), "pubkey.x25519", "0x" + keys["heir_x25519_pk"]), keys["owner"])

    chain.set_balance(studio, 10 * ETH)

    # the name tree on the real ENSv2 PermissionedRegistry: P stands in for the .eth registry and holds
    # yutotanaka, Y is Yuto's own registry, set as the subregistry of yutotanaka, and holds the two child
    # names. The owner approves the Opener as operator on both and plans the three handovers, exactly
    # the ENSv2 flow on Sepolia.
    label = settings.owner_name.split(".")[0]
    parent_id = canonical(label)
    heir = Account.from_key(keys["heir_eth"]).address
    label_store = deploy_label_store(chain, keys["owner"])
    registry = chain.deploy("PermissionedRegistry", keys["owner"], label_store, owner.address, ALL_ROLES)
    P = chain.contract("PermissionedRegistry", registry)
    chain.send(P.functions.register(label, owner.address, ZERO, resolver, OWNER_ROLES, FOREVER), keys["owner"])
    subregistry = chain.deploy("PermissionedRegistry", keys["owner"], label_store, owner.address, ALL_ROLES)
    Y = chain.contract("PermissionedRegistry", subregistry)
    chain.send(P.functions.setSubregistry(parent_id, subregistry), keys["owner"])
    for child, _heir, _who, company in CHILDREN:
        child_name = f"{child}.{settings.owner_name}"
        chain.send(Y.functions.register(child, owner.address, ZERO, resolver, OWNER_ROLES, FOREVER), keys["owner"])
        chain.send(R.functions.setOwner(namehash(child_name), owner.address), keys["owner"])
        chain.send(R.functions.setText(dns_encode(child_name), "company", company), keys["owner"])

    O = chain.contract("Opener", opener)
    chain.send(P.functions.setApprovalForAll(opener, True), keys["owner"])
    chain.send(Y.functions.setApprovalForAll(opener, True), keys["owner"])
    plan = [(registry, parent_id, heir)] + [(subregistry, canonical(child), h) for child, h, _, _ in CHILDREN]
    chain.send(O.functions.setHandovers(owner_dns, plan), keys["owner"])

    # the lock: from here nobody can add or remove a child under Yuto's registry, and Yuto cannot point
    # yutotanaka at another registry. The owner is also P's root account and root roles apply to every
    # token, so the set-subregistry right is revoked at P's root as well. Revoking regenerates the token
    # id, which is why every stored id is canonical.
    revoke(chain, keys["owner"], Y, None, with_admin(ROLE_REGISTRAR | ROLE_UNREGISTER), owner.address,
           "register and unregister on Yuto's registry root")
    revoke(chain, keys["owner"], P, parent_id, with_admin(ROLE_SET_SUBREGISTRY), owner.address,
           f"set subregistry on the {label} token")
    revoke(chain, keys["owner"], P, None, with_admin(ROLE_SET_SUBREGISTRY), owner.address,
           "set subregistry on the parent registry root")
    can_register = Y.functions.hasRoles(0, ROLE_REGISTRAR, owner.address).call()
    can_unregister = any(Y.functions.hasRoles(canonical(c), ROLE_UNREGISTER, owner.address).call() for c, _, _, _ in CHILDREN)
    can_repoint = P.functions.hasRoles(parent_id, ROLE_SET_SUBREGISTRY, owner.address).call()
    print(f"lock      owner can register children: {can_register}, unregister them: {can_unregister}, move the subregistry: {can_repoint}"
          + ("" if not (can_register or can_unregister or can_repoint) else "   WARNING: the tree is not fully locked"))

    tree = ",".join(f"{child}:{hex(canonical(child))}:{h}:{who}" for child, h, who, _ in CHILDREN)
    env = ROOT / "backend" / ".env.local"
    env.write_text(
        f"RPC_URL={a.rpc}\nCHAIN_ID={chain.chain_id}\nRESOLVER={resolver}\nSTUDIO={studio}\nOPENER={opener}\n"
        f"BLOCKS_PER_EPOCH={settings.blocks_per_epoch}\nWINDOW_EPOCHS={settings.window_epochs}\n"
        f"HORIZON_EPOCHS={settings.horizon_epochs}\nLOCK_SECONDS={settings.lock_seconds}\n"
        f"REGISTRY={registry}\nNAME_TOKEN_ID={hex(parent_id)}\nNAME_CANONICAL_ID={hex(parent_id)}\n"
        f"SUBREGISTRY={subregistry}\nTREE={tree}\n"
    )
    live = P.functions.getTokenId(parent_id).call()
    print(f"resolver  {resolver}\nstudio    {studio}\nopener    {opener}\nlabels    {label_store}")
    print(f"registry  {registry}  {settings.owner_name} id {hex(parent_id)[:12]}… (live token {hex(live)[:12]}…) owned by owner, handover planned to Hana {heir}")
    print(f"subregistry {subregistry}  " + ", ".join(f"{child}.{settings.owner_name} -> {who} {h}" for child, h, who, _ in CHILDREN))
    print(f"owner     {owner.address}\nchecker   {checker.address}\nwatchtower {watchtower.address}")
    print(f"vault balance {Web3.from_wei(chain.w3.eth.get_balance(Web3.to_checksum_address(studio)), 'ether')} ETH")
    print(f"wrote {env}")


if __name__ == "__main__":
    main()
