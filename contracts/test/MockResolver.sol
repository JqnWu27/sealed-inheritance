// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ITextResolver} from "../src/interfaces/ITextResolver.sol";
import {Names} from "../src/Names.sol";

/// @notice Test double for an ENSv2 permissioned resolver. Setters take the
///         DNS-encoded name like the real one. The name owner may write any key.
///         Other writers need a per-key grant, mirroring the scoped setter role.
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

    function setText(bytes calldata name, string calldata key, string calldata value) external {
        bytes32 node = Names.namehash(name);
        bool ok = msg.sender == nameOwner[node] || canSet[node][keccak256(bytes(key))][msg.sender];
        if (!ok) revert Unauthorized(node, key, msg.sender);
        records[node][keccak256(bytes(key))] = value;
    }

    function text(bytes32 node, string calldata key) external view returns (string memory) {
        return records[node][keccak256(bytes(key))];
    }

    bytes4 private constant TEXT_SELECTOR = bytes4(keccak256("text(bytes32,string)"));

    /// @notice ENSIP-10 read, the only read path the real permissioned resolver
    ///         offers. The node inside `data` is ignored, the node comes from `name`.
    function resolve(bytes calldata name, bytes calldata data) external view returns (bytes memory) {
        require(bytes4(data[:4]) == TEXT_SELECTOR, "unsupported profile");
        (, string memory key) = abi.decode(data[4:], (bytes32, string));
        return abi.encode(records[Names.namehash(name)][keccak256(bytes(key))]);
    }
}
