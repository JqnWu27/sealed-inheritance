// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Opener} from "../src/Opener.sol";
import {Names} from "../src/Names.sol";
import {ITextResolver} from "../src/interfaces/ITextResolver.sol";
import {MockResolver} from "./MockResolver.sol";

contract OpenerTest is Test {
    MockResolver resolver;
    Opener opener;

    uint256 checkerKey = 0xC4EC;
    address checker;
    address owner = address(0xA11CE);
    bytes KEN = hex"036b656e0365746800";
    bytes32 node;

    function setUp() public {
        checker = vm.addr(checkerKey);
        node = Names.namehash(KEN);
        resolver = new MockResolver();
        resolver.setOwner(node, owner);
        opener = new Opener(checker, ITextResolver(address(resolver)));
        vm.prank(owner);
        resolver.grantSetter(node, "disclosure", address(opener), true);
    }

    function _sig(uint256 key, bytes32 digest) internal pure returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, digest);
        return abi.encodePacked(r, s, v);
    }

    function test_opens_once_with_checker_signature() public {
        bytes32 inner = keccak256("inner");
        bytes memory sig = _sig(checkerKey, opener.openingDigest(node, 3, inner));
        opener.recordOpening(KEN, 3, inner, sig);
        assertTrue(opener.opened(node));
        string memory d = resolver.text(node, "disclosure");
        assertEq(bytes(d).length, bytes("window=3;inner=").length + 66);

        vm.expectRevert(abi.encodeWithSelector(Opener.AlreadyOpened.selector, node));
        opener.recordOpening(KEN, 4, inner, sig);
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
}
