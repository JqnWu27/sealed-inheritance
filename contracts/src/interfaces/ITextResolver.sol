// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice ENSv2 permissioned-resolver text interface.
///         Setters take the DNS-encoded name (bytes). Reads take the namehash.
///         setText requires ROLE_SET_TEXT on the key resource, granted with
///         grantSetterRoles(encodedSetterCall, account).
interface ITextResolver {
    function setText(bytes calldata name, string calldata key, string calldata value) external;
    function text(bytes32 node, string calldata key) external view returns (string memory);
}
