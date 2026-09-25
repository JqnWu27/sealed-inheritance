// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice ENSIP-1 namehash computed from a DNS-encoded name.
library Names {
    function namehash(bytes memory name) internal pure returns (bytes32) {
        return _hash(name, 0);
    }

    function _hash(bytes memory name, uint256 offset) private pure returns (bytes32) {
        uint256 len = uint8(name[offset]);
        if (len == 0) return bytes32(0);
        bytes memory label = new bytes(len);
        for (uint256 i = 0; i < len; i++) {
            label[i] = name[offset + 1 + i];
        }
        return keccak256(abi.encodePacked(_hash(name, offset + 1 + len), keccak256(label)));
    }
}
