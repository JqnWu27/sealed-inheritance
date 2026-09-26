// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";

import {PermissionedRegistry} from "ensv2/registry/PermissionedRegistry.sol";
import {IRegistry} from "ensv2/registry/interfaces/IRegistry.sol";
import {RegistryRolesLib} from "ensv2/registry/libraries/RegistryRolesLib.sol";
import {EACBaseRolesLib} from "ensv2/access-control/libraries/EACBaseRolesLib.sol";
import {IEnhancedAccessControl} from "ensv2/access-control/interfaces/IEnhancedAccessControl.sol";
import {LabelStore} from "ensv2/utils/LabelStore.sol";
import {ILabelStore} from "ensv2/utils/interfaces/ILabelStore.sol";
import {IContractNamer} from "ensv2/reverse-registrar/interfaces/IContractNamer.sol";

import {Opener} from "../src/Opener.sol";
import {Names} from "../src/Names.sol";
import {ITextResolver} from "../src/interfaces/ITextResolver.sol";
import {MockResolver} from "./MockResolver.sol";

/// @notice The demo name tree on the real ENSv2 PermissionedRegistry.
///
///   P (parent registry, root = testAdmin)
///   +-- "yutotanaka" owned by yuto, subregistry = Y
///         Y (the registry of yuto, root = yuto)
///         +-- "yuto"   owned by yuto
///         +-- "tanaka" owned by yuto
///
///   THE LOCK, done by yuto before the handover:
///     - Y root: revoke ROLE_REGISTRAR, ROLE_UNREGISTER and both admin bits from himself,
///       so nobody can ever add or remove a name in Y again.
///     - P token "yutotanaka": revoke ROLE_SET_SUBREGISTRY and its admin bit from himself,
///       so whoever inherits the parent cannot swap Y for another registry.
///   Then the operator (the Opener) moves yutotanaka to hana, yuto to taka, tanaka to yuta.
contract EnsV2TreeTest is Test {
    uint256 constant ALL_ROLES = EACBaseRolesLib.ALL_ROLES;

    /// @dev Roles a name token carries in the demo: point its resolver and subregistry, be transferred.
    uint256 constant TOKEN_ROLES = RegistryRolesLib.ROLE_SET_SUBREGISTRY | RegistryRolesLib.ROLE_SET_SUBREGISTRY_ADMIN
        | RegistryRolesLib.ROLE_SET_RESOLVER | RegistryRolesLib.ROLE_SET_RESOLVER_ADMIN
        | RegistryRolesLib.ROLE_CAN_TRANSFER_ADMIN;

    uint256 constant Y_ROOT_LOCK = RegistryRolesLib.ROLE_REGISTRAR | RegistryRolesLib.ROLE_REGISTRAR_ADMIN
        | RegistryRolesLib.ROLE_UNREGISTER | RegistryRolesLib.ROLE_UNREGISTER_ADMIN;
    uint256 constant P_TOKEN_LOCK = RegistryRolesLib.ROLE_SET_SUBREGISTRY | RegistryRolesLib.ROLE_SET_SUBREGISTRY_ADMIN;

    uint256 constant cParent = uint256(keccak256("yutotanaka"));
    uint256 constant cYuto = uint256(keccak256("yuto"));
    uint256 constant cTanaka = uint256(keccak256("tanaka"));

    address testAdmin;
    address yuto;
    address hana;
    address taka;
    address yuta;
    address childResolver;

    LabelStore store;
    PermissionedRegistry P;
    PermissionedRegistry Y;
    MockResolver textResolver;
    Opener opener;
    uint256 checkerKey = 0xC4EC;

    bytes NAME; // \x0ayutotanaka\x03eth\x00, the name whose disclosure record the Opener writes
    bytes32 node;

    function setUp() public {
        testAdmin = makeAddr("testAdmin");
        yuto = makeAddr("yuto");
        hana = makeAddr("hana");
        taka = makeAddr("taka");
        yuta = makeAddr("yuta");
        childResolver = makeAddr("childResolver");
        vm.warp(1_700_000_000);
        uint64 farFuture = uint64(block.timestamp + 100 * 365 days);

        NAME = abi.encodePacked(bytes1(0x0a), "yutotanaka", bytes1(0x03), "eth", bytes1(0x00));
        node = Names.namehash(NAME);
        textResolver = new MockResolver();
        textResolver.setOwner(node, yuto);
        opener = new Opener(vm.addr(checkerKey), ITextResolver(address(textResolver)));

        store = new LabelStore(IContractNamer(address(0)));
        P = new PermissionedRegistry(ILabelStore(address(store)), testAdmin, ALL_ROLES);
        vm.prank(testAdmin);
        P.register("yutotanaka", yuto, IRegistry(address(0)), address(0), TOKEN_ROLES, farFuture);

        vm.startPrank(yuto);
        Y = new PermissionedRegistry(ILabelStore(address(store)), yuto, ALL_ROLES);
        P.setSubregistry(cParent, IRegistry(address(Y)));
        Y.register("yuto", yuto, IRegistry(address(0)), childResolver, TOKEN_ROLES, type(uint64).max);
        Y.register("tanaka", yuto, IRegistry(address(0)), childResolver, TOKEN_ROLES, type(uint64).max);
        P.setApprovalForAll(address(opener), true);
        Y.setApprovalForAll(address(opener), true);
        textResolver.grantSetter(node, "disclosure", address(opener), true);
        vm.stopPrank();
    }

    function _lock() internal {
        vm.startPrank(yuto);
        Y.revokeRootRoles(Y_ROOT_LOCK, yuto); // revokeRoles(0, ...) reverts with EACRootResourceNotAllowed
        P.revokeRoles(cParent, P_TOKEN_LOCK, yuto);
        vm.stopPrank();
    }

    function _transferAll(address operator) internal {
        vm.startPrank(operator);
        P.safeTransferFrom(yuto, hana, P.getTokenId(cParent), 1, "");
        Y.safeTransferFrom(yuto, taka, Y.getTokenId(cYuto), 1, "");
        Y.safeTransferFrom(yuto, yuta, Y.getTokenId(cTanaka), 1, "");
        vm.stopPrank();
    }

    function _open(uint64 window, bytes32 inner) internal {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(checkerKey, opener.openingDigest(node, window, inner));
        opener.recordOpening(NAME, window, inner, abi.encodePacked(r, s, v));
    }

    /// @dev vm.expectRevert(bytes4) matches the exact revert data, so the full error is encoded.
    ///      Call these BEFORE vm.prank: the getResource view call would otherwise consume the prank.
    function _expectUnauthorized(PermissionedRegistry r, uint256 anyId, uint256 role, address who) internal {
        vm.expectRevert(
            abi.encodeWithSelector(
                IEnhancedAccessControl.EACUnauthorizedAccountRoles.selector, r.getResource(anyId), role, who
            )
        );
    }

    function _expectCannotGrant(PermissionedRegistry r, uint256 anyId, uint256 role, address who) internal {
        vm.expectRevert(
            abi.encodeWithSelector(IEnhancedAccessControl.EACCannotGrantRoles.selector, r.getResource(anyId), role, who)
        );
    }

    // ------------------------------------------------------------------ tree

    function test_tree_is_wired() public view {
        assertEq(address(P.getSubregistry("yutotanaka")), address(Y));
        assertEq(Y.getResolver("yuto"), childResolver);
        assertEq(Y.getResolver("tanaka"), childResolver);
        assertEq(P.getOwner(cParent), yuto);
        assertEq(Y.getOwner(cYuto), yuto);
        assertEq(Y.getOwner(cTanaka), yuto);
        assertEq(P.findTokenId("yutotanaka"), P.getTokenId(cParent));
        assertEq(P.ownerOf(P.getTokenId(cParent)), yuto);
        assertTrue(P.hasRoles(cParent, TOKEN_ROLES, yuto));
        assertTrue(Y.hasRootRoles(ALL_ROLES, yuto));
    }

    // ------------------------------------------------------------------ the lock

    function test_lock_self_revokes_admin_bits_and_regenerates_the_parent_token() public {
        uint256 parentBefore = P.getTokenId(cParent);
        uint256 childBefore = Y.getTokenId(cYuto);
        assertTrue(P.hasRoles(cParent, P_TOKEN_LOCK, yuto));
        assertTrue(Y.hasRootRoles(Y_ROOT_LOCK, yuto));

        _lock();

        // regular AND admin bits are gone, on the token resource and on the root resource
        assertFalse(P.hasRoles(cParent, RegistryRolesLib.ROLE_SET_SUBREGISTRY, yuto));
        assertFalse(P.hasRoles(cParent, RegistryRolesLib.ROLE_SET_SUBREGISTRY_ADMIN, yuto));
        assertFalse(Y.hasRootRoles(RegistryRolesLib.ROLE_REGISTRAR, yuto));
        assertFalse(Y.hasRootRoles(RegistryRolesLib.ROLE_REGISTRAR_ADMIN, yuto));
        assertFalse(Y.hasRootRoles(RegistryRolesLib.ROLE_UNREGISTER, yuto));
        assertFalse(Y.hasRootRoles(RegistryRolesLib.ROLE_UNREGISTER_ADMIN, yuto));
        // nobody holds them, so nobody can grant them back
        assertFalse(P.hasAssignees(cParent, P_TOKEN_LOCK));
        assertFalse(Y.hasAssignees(Y.ROOT_RESOURCE(), Y_ROOT_LOCK));
        _expectCannotGrant(Y, 0, RegistryRolesLib.ROLE_REGISTRAR, yuto);
        vm.prank(yuto);
        Y.grantRootRoles(RegistryRolesLib.ROLE_REGISTRAR, yuto);
        _expectCannotGrant(P, cParent, RegistryRolesLib.ROLE_SET_SUBREGISTRY, yuto);
        vm.prank(yuto);
        P.grantRoles(cParent, RegistryRolesLib.ROLE_SET_SUBREGISTRY, yuto);
        // what yuto kept
        assertTrue(
            P.hasRoles(cParent, RegistryRolesLib.ROLE_SET_RESOLVER | RegistryRolesLib.ROLE_CAN_TRANSFER_ADMIN, yuto)
        );

        // the token revoke regenerated the parent token, the root revoke regenerated nothing
        assertTrue(P.getTokenId(cParent) != parentBefore);
        assertEq(Y.getTokenId(cYuto), childBefore);
        assertEq(P.ownerOf(parentBefore), address(0)); // the stale id has no owner any more
        assertEq(P.ownerOf(P.getTokenId(cParent)), yuto);
        assertEq(P.getOwner(cParent), yuto); // the canonical id keeps working

        // the stale id cannot be moved, only the live one can
        vm.prank(address(opener));
        vm.expectRevert();
        P.safeTransferFrom(yuto, hana, parentBefore, 1, "");
    }

    function test_operator_hands_over_the_tree_after_the_lock() public {
        _lock();
        _transferAll(address(opener));

        assertEq(P.getOwner(cParent), hana);
        assertEq(P.ownerOf(P.getTokenId(cParent)), hana);
        assertEq(P.findOwner("yutotanaka"), hana);
        assertEq(Y.getOwner(cYuto), taka);
        assertEq(Y.getOwner(cTanaka), yuta);
        assertEq(address(P.getSubregistry("yutotanaka")), address(Y));
        assertEq(Y.getResolver("yuto"), childResolver);
        assertEq(Y.getResolver("tanaka"), childResolver);

        // hana holds the parent but cannot swap the subregistry
        _expectUnauthorized(P, cParent, RegistryRolesLib.ROLE_SET_SUBREGISTRY, hana);
        vm.prank(hana);
        P.setSubregistry(cParent, IRegistry(address(0xDEAD)));
        // nobody can add or remove names in Y: not hana, not yuto
        _expectUnauthorized(Y, 0, RegistryRolesLib.ROLE_REGISTRAR, hana);
        vm.prank(hana);
        Y.register("hana", hana, IRegistry(address(0)), address(0), TOKEN_ROLES, type(uint64).max);
        _expectUnauthorized(Y, cYuto, RegistryRolesLib.ROLE_UNREGISTER, hana);
        vm.prank(hana);
        Y.unregister(cYuto);
        _expectUnauthorized(Y, 0, RegistryRolesLib.ROLE_REGISTRAR, yuto);
        vm.prank(yuto);
        Y.register("intruder", yuto, IRegistry(address(0)), address(0), TOKEN_ROLES, type(uint64).max);
        _expectUnauthorized(Y, cTanaka, RegistryRolesLib.ROLE_UNREGISTER, yuto);
        vm.prank(yuto);
        Y.unregister(cTanaka);

        // roles travelled with the tokens
        assertEq(P.roles(cParent, yuto), 0);
        assertTrue(
            P.hasRoles(cParent, RegistryRolesLib.ROLE_SET_RESOLVER | RegistryRolesLib.ROLE_CAN_TRANSFER_ADMIN, hana)
        );
        assertTrue(Y.hasRoles(cYuto, TOKEN_ROLES, taka));
        // hana may point the resolver of the parent, taka that of his child, yuta cannot touch the child of taka
        vm.prank(hana);
        P.setResolver(cParent, address(0xBEEF));
        assertEq(P.getResolver("yutotanaka"), address(0xBEEF));
        address takaResolver = makeAddr("takaResolver");
        vm.prank(taka);
        Y.setResolver(cYuto, takaResolver);
        assertEq(Y.getResolver("yuto"), takaResolver);
        _expectUnauthorized(Y, cYuto, RegistryRolesLib.ROLE_SET_RESOLVER, yuta);
        vm.prank(yuta);
        Y.setResolver(cYuto, address(0xBAD));

        // residual, documented: the remaining root roles of yuto on Y (set resolver, set subregistry,
        // renew) still reach the children through the root fallback. Revoke them too for a complete lock.
        assertTrue(Y.hasRootRoles(RegistryRolesLib.ROLE_SET_RESOLVER, yuto));
    }

    function test_negative_control_without_the_lock_the_tree_can_be_broken() public {
        _transferAll(address(opener));
        assertEq(P.getOwner(cParent), hana);
        assertEq(Y.getOwner(cTanaka), yuta);

        // ROLE_SET_SUBREGISTRY moved to hana with the token, she swaps Y away
        PermissionedRegistry evil = new PermissionedRegistry(ILabelStore(address(store)), hana, ALL_ROLES);
        vm.prank(hana);
        P.setSubregistry(cParent, IRegistry(address(evil)));
        assertEq(address(P.getSubregistry("yutotanaka")), address(evil));

        // and yuto, still root of Y, deletes the name of yuta
        vm.prank(yuto);
        Y.unregister(cTanaka);
        assertEq(Y.getOwner(cTanaka), address(0));
    }

    // ------------------------------------------------------------------ the Opener on the real registry

    function test_opening_hands_over_the_whole_list() public {
        Opener.Handover[] memory list = new Opener.Handover[](3);
        list[0] = Opener.Handover(address(P), cParent, hana);
        list[1] = Opener.Handover(address(Y), cYuto, taka);
        list[2] = Opener.Handover(address(Y), cTanaka, yuta);
        vm.prank(yuto);
        opener.setHandovers(NAME, list);
        assertEq(opener.handoverCount(node), 3);
        assertEq(opener.handoverAt(node, 1).heir, taka);
        assertEq(opener.planner(node), yuto);
        (address reg0, uint256 tok0, address owner0, address heir0) = opener.handover(node);
        assertEq(reg0, address(P));
        assertEq(tok0, P.getTokenId(cParent));
        assertEq(owner0, yuto);
        assertEq(heir0, hana);

        // the lock comes after planning and changes the parent token id, the plan survives it
        _lock();

        vm.expectEmit(true, true, true, true);
        emit Opener.NameHandedOver(node, address(P), P.getTokenId(cParent), yuto, hana);
        vm.expectEmit(true, true, true, true);
        emit Opener.NameHandedOver(node, address(Y), Y.getTokenId(cYuto), yuto, taka);
        vm.expectEmit(true, true, true, true);
        emit Opener.NameHandedOver(node, address(Y), Y.getTokenId(cTanaka), yuto, yuta);
        _open(1, keccak256("inner"));

        assertTrue(opener.opened(node, 1));
        assertEq(P.getOwner(cParent), hana);
        assertEq(Y.getOwner(cYuto), taka);
        assertEq(Y.getOwner(cTanaka), yuta);
        assertEq(address(P.getSubregistry("yutotanaka")), address(Y));

        // a second opening writes the disclosure and leaves the names where they are
        vm.expectEmit(true, false, false, true);
        emit Opener.HandoverSkipped(node, "heir already owns the name");
        _open(2, keccak256("inner2"));
        assertEq(P.getOwner(cParent), hana);
        assertEq(Y.getOwner(cYuto), taka);
        assertEq(Y.getOwner(cTanaka), yuta);
    }

    function test_opening_skips_a_name_the_planner_no_longer_owns_and_moves_the_rest() public {
        Opener.Handover[] memory list = new Opener.Handover[](2);
        list[0] = Opener.Handover(address(P), cParent, hana);
        list[1] = Opener.Handover(address(Y), cYuto, taka);
        vm.prank(yuto);
        opener.setHandovers(NAME, list);
        // yuto gives "yuto" away himself before the opening
        uint256 yutoToken = Y.getTokenId(cYuto); // read first, a view call would consume the prank
        vm.prank(yuto);
        Y.safeTransferFrom(yuto, yuta, yutoToken, 1, "");

        vm.expectEmit(true, false, false, true);
        emit Opener.HandoverSkipped(node, "name no longer owned by the planner");
        _open(1, keccak256("inner"));
        assertEq(P.getOwner(cParent), hana);
        assertEq(Y.getOwner(cYuto), yuta);
    }

    function test_old_setHandover_with_a_live_token_id_survives_a_regeneration() public {
        uint256 tokenAtPlanning = P.getTokenId(cParent);
        vm.prank(yuto);
        opener.setHandover(NAME, address(P), tokenAtPlanning, hana);
        _lock(); // the parent token id changes
        assertTrue(P.getTokenId(cParent) != tokenAtPlanning);
        _open(1, keccak256("inner"));
        assertEq(P.getOwner(cParent), hana); // getTokenId(oldTokenId) resolved to the live id
    }

    function test_setHandovers_requires_owning_every_listed_name() public {
        Opener.Handover[] memory list = new Opener.Handover[](2);
        list[0] = Opener.Handover(address(P), cParent, hana);
        list[1] = Opener.Handover(address(Y), cYuto, taka);
        vm.prank(hana);
        vm.expectRevert(Opener.NotNameOwner.selector);
        opener.setHandovers(NAME, list);

        vm.prank(yuto);
        opener.setHandovers(NAME, list);
        // only the planner may cancel
        Opener.Handover[] memory none = new Opener.Handover[](0);
        vm.prank(hana);
        vm.expectRevert(Opener.NotPlanner.selector);
        opener.setHandovers(NAME, none);
        vm.prank(yuto);
        opener.setHandovers(NAME, none);
        assertEq(opener.handoverCount(node), 0);
    }

    function test_opener_moves_nothing_without_approval() public {
        Opener.Handover[] memory list = new Opener.Handover[](1);
        list[0] = Opener.Handover(address(Y), cYuto, taka);
        vm.startPrank(yuto);
        opener.setHandovers(NAME, list);
        Y.setApprovalForAll(address(opener), false);
        vm.stopPrank();
        vm.expectEmit(true, false, false, true);
        emit Opener.HandoverSkipped(node, "opener not approved as operator");
        _open(1, keccak256("inner"));
        assertTrue(opener.opened(node, 1));
        assertEq(Y.getOwner(cYuto), yuto);
    }
}
