// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ITextResolver} from "../src/interfaces/ITextResolver.sol";

/// @notice Test double for an ENSv2 permissioned resolver. The name owner may
///         write any key. Other writers need a per-key grant, mirroring the
///         scoped setter role used on Sepolia.
contract MockResolver is ITextResolver {
    mapping(bytes32 => address) public nameOwner;
    mapping(bytes32 => mapping(bytes32 => mapping(address => bool))) public canSet; // node => keyHash => writer
    mapping(bytes32 => mapping(bytes32 => string)) private records;

    error Unauthorized(bytes32 node, string key, address writer);

    function setOwner(bytes32 node, address owner) external {
        nameOwner[node] = owner;
    }

    function grantSetter(bytes32 node, string calldata key, address writer, bool allowed) external {
        require(msg.sender == nameOwner[node], "not name owner");
        canSet[node][keccak256(bytes(key))][writer] = allowed;
    }

    function setText(bytes32 node, string calldata key, string calldata value) external {
        bool ok = msg.sender == nameOwner[node] || canSet[node][keccak256(bytes(key))][msg.sender];
        if (!ok) revert Unauthorized(node, key, msg.sender);
        records[node][keccak256(bytes(key))] = value;
    }

    function text(bytes32 node, string calldata key) external view returns (string memory) {
        return records[node][keccak256(bytes(key))];
    }
}
