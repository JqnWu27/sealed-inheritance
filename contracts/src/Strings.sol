// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

library Strings {
    bytes16 private constant HEX = "0123456789abcdef";

    function toDecimal(uint256 v) internal pure returns (string memory) {
        if (v == 0) return "0";
        uint256 n = v;
        uint256 len;
        while (n != 0) {
            len++;
            n /= 10;
        }
        bytes memory out = new bytes(len);
        while (v != 0) {
            out[--len] = bytes1(uint8(48 + (v % 10)));
            v /= 10;
        }
        return string(out);
    }

    function toHex(bytes32 v) internal pure returns (string memory) {
        bytes memory out = new bytes(66);
        out[0] = "0";
        out[1] = "x";
        for (uint256 i = 0; i < 32; i++) {
            out[2 + 2 * i] = HEX[uint8(v[i] >> 4)];
            out[3 + 2 * i] = HEX[uint8(v[i] & 0x0f)];
        }
        return string(out);
    }

    function toHex(address a) internal pure returns (string memory) {
        bytes memory out = new bytes(42);
        out[0] = "0";
        out[1] = "x";
        bytes20 b = bytes20(a);
        for (uint256 i = 0; i < 20; i++) {
            out[2 + 2 * i] = HEX[uint8(b[i] >> 4)];
            out[3 + 2 * i] = HEX[uint8(b[i] & 0x0f)];
        }
        return string(out);
    }
}
