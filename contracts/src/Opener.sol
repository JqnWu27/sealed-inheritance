// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ITextResolver} from "./interfaces/ITextResolver.sol";
import {Strings} from "./Strings.sol";
import {Names} from "./Names.sol";

/// @title Opener
/// @notice Writes the `disclosure` record on a name exactly once, after the
///         off-chain relation checker has accepted a witness and decrypted the
///         outer layer. The name owner grants this contract the ENSv2 setter
///         role scoped to the single key `disclosure`.
///
///         The checker signature is a stand-in for on-chain witness
///         verification. The checker signs keccak256(node, window, innerHash).
contract Opener {
    using Strings for uint256;
    using Strings for bytes32;

    address public immutable checker;
    ITextResolver public immutable resolver;
    mapping(bytes32 => bool) public opened;

    event Opened(bytes32 indexed node, uint64 window, bytes32 innerHash);

    error AlreadyOpened(bytes32 node);
    error BadCheckerSignature();

    constructor(address checker_, ITextResolver resolver_) {
        checker = checker_;
        resolver = resolver_;
    }

    function openingDigest(bytes32 node, uint64 window, bytes32 innerHash) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(node, window, innerHash));
    }

    function recordOpening(bytes calldata dnsName, uint64 window, bytes32 innerHash, bytes calldata sig) external {
        bytes32 node = Names.namehash(dnsName);
        if (opened[node]) revert AlreadyOpened(node);
        if (_recover(openingDigest(node, window, innerHash), sig) != checker) revert BadCheckerSignature();
        opened[node] = true;
        resolver.setText(
            dnsName,
            "disclosure",
            string.concat("window=", uint256(window).toDecimal(), ";inner=", innerHash.toHex())
        );
        emit Opened(node, window, innerHash);
    }

    function _recover(bytes32 digest, bytes calldata sig) internal pure returns (address) {
        if (sig.length != 65) return address(0);
        bytes32 r = bytes32(sig[0:32]);
        bytes32 s = bytes32(sig[32:64]);
        uint8 v = uint8(sig[64]);
        if (v < 27) v += 27;
        if (v != 27 && v != 28) return address(0);
        return ecrecover(digest, v, r, s);
    }
}
