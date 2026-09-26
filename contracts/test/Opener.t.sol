// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Opener} from "../src/Opener.sol";
import {Names} from "../src/Names.sol";
import {ITextResolver} from "../src/interfaces/ITextResolver.sol";
import {MockResolver} from "./MockResolver.sol";
import {MockRegistry} from "./MockRegistry.sol";

contract OpenerTest is Test {
    MockResolver resolver;
    MockRegistry registry;
    Opener opener;

    uint256 checkerKey = 0xC4EC;
    address checker;
    address owner = address(0xA11CE);
    address hana = address(0xBEEF);
    bytes KEN = hex"036b656e0365746800";
    bytes32 node;
    uint256 tokenId = uint256(keccak256("ken"));

    function setUp() public {
        checker = vm.addr(checkerKey);
        node = Names.namehash(KEN);
        resolver = new MockResolver();
        resolver.setOwner(node, owner);
        registry = new MockRegistry();
        registry.mint(owner, tokenId);
        opener = new Opener(checker, ITextResolver(address(resolver)));
        vm.startPrank(owner);
        resolver.grantSetter(node, "disclosure", address(opener), true);
        registry.setApprovalForAll(address(opener), true);
        opener.setHandover(KEN, address(registry), tokenId, hana);
        vm.stopPrank();
    }

    function _sig(uint256 key, bytes32 digest) internal pure returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, digest);
        return abi.encodePacked(r, s, v);
    }

    function _open(uint64 window, bytes32 inner) internal {
        opener.recordOpening(KEN, window, inner, _sig(checkerKey, opener.openingDigest(node, window, inner)));
    }

    function test_opens_once_with_checker_signature() public {
        bytes32 inner = keccak256("inner");
        _open(3, inner);
        assertTrue(opener.opened(node, 3));
        string memory d = resolver.text(node, "disclosure");
        assertEq(bytes(d).length, bytes("window=3;inner=").length + 66);

        // the same window can never be written again, even with a valid signature
        bytes memory sig = _sig(checkerKey, opener.openingDigest(node, 3, inner));
        vm.expectRevert(abi.encodeWithSelector(Opener.AlreadyOpened.selector, node, uint64(3)));
        opener.recordOpening(KEN, 3, inner, sig);
    }

    function test_later_window_can_be_disclosed_too() public {
        _open(3, keccak256("inner3"));
        _open(4, keccak256("inner4"));
        assertTrue(opener.opened(node, 3));
        assertTrue(opener.opened(node, 4));
        bytes memory sigFor3 = _sig(checkerKey, opener.openingDigest(node, 3, keccak256("inner3")));
        vm.expectRevert(Opener.BadCheckerSignature.selector);
        opener.recordOpening(KEN, 5, keccak256("inner3"), sigFor3);
    }

    function test_rejects_non_checker() public {
        bytes32 inner = keccak256("inner");
        bytes memory sig = _sig(0xBAD, opener.openingDigest(node, 3, inner));
        vm.expectRevert(Opener.BadCheckerSignature.selector);
        opener.recordOpening(KEN, 3, inner, sig);
    }

    function test_opener_cannot_write_other_keys() public {
        vm.prank(address(opener));
        vm.expectRevert(abi.encodeWithSelector(MockResolver.Unauthorized.selector, node, "heartbeat", address(opener)));
        resolver.setText(KEN, "heartbeat", "1");
    }

    function test_opening_hands_the_name_to_the_heir() public {
        assertEq(registry.ownerOf(tokenId), owner);
        _open(1, keccak256("inner"));
        assertEq(registry.ownerOf(tokenId), hana);
        // a second opening finds the heir already owning the name and leaves it alone
        _open(2, keccak256("inner2"));
        assertEq(registry.ownerOf(tokenId), hana);
    }

    function test_without_approval_disclosure_is_written_and_name_stays() public {
        vm.prank(owner);
        registry.setApprovalForAll(address(opener), false);
        _open(1, keccak256("inner"));
        assertTrue(opener.opened(node, 1));
        assertEq(registry.ownerOf(tokenId), owner);
    }

    function test_only_the_name_owner_can_plan_a_handover() public {
        vm.prank(hana);
        vm.expectRevert(Opener.NotNameOwner.selector);
        opener.setHandover(KEN, address(registry), tokenId, hana);
    }

    function test_opener_never_moves_the_name_before_an_opening() public {
        // approved and configured, but no opening yet: the name stays with the owner,
        // and the opener has no function that moves it outside recordOpening
        assertEq(registry.ownerOf(tokenId), owner);
    }
}
