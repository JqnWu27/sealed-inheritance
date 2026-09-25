// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Minimal ENS text-record interface. ENSv2 permissioned resolvers keep
///         the classic setText/text signatures and gate setText by scoped roles.
interface ITextResolver {
    function setText(bytes32 node, string calldata key, string calldata value) external;
    function text(bytes32 node, string calldata key) external view returns (string memory);
}
