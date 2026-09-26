// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {INameRegistry} from "../src/interfaces/INameRegistry.sol";

/// @notice Test double for the ERC-1155 shaped ENSv2 registry: one owner per name
///         token, operator approval, transfer by the owner or an approved operator.
contract MockRegistry is INameRegistry {
    mapping(uint256 => address) public ownerOf;
    mapping(address => mapping(address => bool)) public isApprovedForAll;

    function mint(address to, uint256 id) external {
        ownerOf[id] = to;
    }

    function setApprovalForAll(address operator, bool approved) external {
        isApprovedForAll[msg.sender][operator] = approved;
    }

    function safeTransferFrom(address from, address to, uint256 id, uint256, bytes calldata) external {
        require(ownerOf[id] == from, "not owner");
        require(msg.sender == from || isApprovedForAll[from][msg.sender], "not approved");
        ownerOf[id] = to;
    }
}
