// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Studio} from "../src/Studio.sol";
import {Names} from "../src/Names.sol";
import {ITextResolver} from "../src/interfaces/ITextResolver.sol";
import {MockResolver} from "./MockResolver.sol";

contract StudioTest is Test {
    MockResolver resolver;
    Studio studio;

    uint256 ownerKey = 0xA11CE;
    address owner;
    address hana = address(0xBEEF);
    bytes KEN = hex"036b656e0365746800"; // \x03ken\x03eth\x00
    bytes32 node;

    function setUp() public {
        owner = vm.addr(ownerKey);
        node = Names.namehash(KEN);
        resolver = new MockResolver();
        resolver.setOwner(node, owner);
        studio = new Studio(owner, KEN, ITextResolver(address(resolver)), 8);
        vm.startPrank(owner);
        resolver.grantSetter(node, "heartbeat", address(studio), true);
        resolver.grantSetter(node, "sealed", address(studio), true);
        vm.stopPrank();
        vm.deal(address(studio), 10 ether);
        vm.warp(1_000_000);
        vm.roll(800); // epoch 100
    }

    function _sign(Studio.Slip memory s) internal view returns (bytes memory) {
        bytes32 structHash = keccak256(abi.encode(studio.SLIP_TYPEHASH(), s.to, s.amount, s.notBefore, s.nonce));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", studio.domainSeparator(), structHash));
        (uint8 v, bytes32 r, bytes32 sVal) = vm.sign(ownerKey, digest);
        return abi.encodePacked(r, sVal, v);
    }

    function test_namehash_matches_ensip1() public view {
        // namehash("ken.eth") computed independently
        bytes32 eth = keccak256(abi.encodePacked(bytes32(0), keccak256("eth")));
        bytes32 expected = keccak256(abi.encodePacked(eth, keccak256("ken")));
        assertEq(node, expected);
        assertEq(studio.node(), expected);
    }

    function test_heartbeat_writes_records_and_bumps() public {
        vm.prank(owner);
        studio.heartbeat(hex"c0ffee", "anchor=100:0x9a4e;N=10;H=60");
        assertEq(studio.nonce(), 1);
        assertEq(resolver.text(node, "heartbeat"), "100");
        string memory sealedRec = resolver.text(node, "sealed");
        assertTrue(bytes(sealedRec).length > 60);
        assertEq(studio.sealedEnvelope(1), hex"c0ffee");
    }

    function test_heartbeat_only_owner() public {
        vm.prank(hana);
        vm.expectRevert(Studio.NotOwner.selector);
        studio.heartbeat(hex"00", "x");
    }

    function test_slip_pays_after_lock_with_current_nonce() public {
        vm.prank(owner);
        studio.heartbeat(hex"01", "c"); // nonce 1
        Studio.Slip memory s = Studio.Slip({to: hana, amount: 6 ether, notBefore: uint64(block.timestamp + 100), nonce: 1});
        bytes memory sig = _sign(s);

        vm.expectRevert(abi.encodeWithSelector(Studio.TooEarly.selector, s.notBefore, block.timestamp));
        studio.execute(s, sig);

        vm.warp(block.timestamp + 100);
        uint256 before = hana.balance;
        studio.execute(s, sig);
        assertEq(hana.balance - before, 6 ether);
    }

    function test_slip_void_after_bump() public {
        vm.prank(owner);
        studio.heartbeat(hex"01", "c"); // nonce 1
        Studio.Slip memory s = Studio.Slip({to: hana, amount: 6 ether, notBefore: uint64(block.timestamp), nonce: 1});
        bytes memory sig = _sign(s);

        vm.prank(owner);
        studio.bump(); // nonce 2
        vm.expectRevert(abi.encodeWithSelector(Studio.StaleNonce.selector, uint64(1), uint64(2)));
        studio.execute(s, sig);
    }

    function test_slip_rejects_wrong_signer() public {
        vm.prank(owner);
        studio.heartbeat(hex"01", "c");
        Studio.Slip memory s = Studio.Slip({to: hana, amount: 1 ether, notBefore: uint64(block.timestamp), nonce: 1});
        bytes32 structHash = keccak256(abi.encode(studio.SLIP_TYPEHASH(), s.to, s.amount, s.notBefore, s.nonce));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", studio.domainSeparator(), structHash));
        (uint8 v, bytes32 r, bytes32 sVal) = vm.sign(0xBAD, digest);
        vm.expectRevert(Studio.BadSignature.selector);
        studio.execute(s, abi.encodePacked(r, sVal, v));
    }

    function test_studio_cannot_write_disclosure() public {
        // The scoped grant covers heartbeat and sealed only.
        vm.prank(address(studio));
        vm.expectRevert(abi.encodeWithSelector(MockResolver.Unauthorized.selector, node, "disclosure", address(studio)));
        resolver.setText(KEN, "disclosure", "x");
    }

    function test_resolve_reads_like_ens_clients() public {
        vm.prank(owner);
        studio.heartbeat(hex"c0ffee", "anchor=100:0x9a4e;N=10;H=60");
        // ENSIP-10: resolve(name, text(node, key)). The node in the call is ignored, the name decides.
        bytes memory data = abi.encodeWithSelector(ITextResolver.text.selector, bytes32(0), "heartbeat");
        bytes memory out = resolver.resolve(KEN, data);
        assertEq(abi.decode(out, (string)), "100");
        assertEq(abi.decode(out, (string)), resolver.text(node, "heartbeat"));
    }
}
