// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice The slice of the ENSv2 registry the Opener needs to hand a name over.
///         The registry is ERC-1155 shaped: the name is a token, the owner may approve
///         an operator, and an approved operator may transfer it. Token ids in the
///         ENSv2 PermissionedRegistry change whenever roles are granted or revoked, so
///         the live id is looked up from the canonical id (labelhash) with getTokenId.
interface INameRegistry {
    function ownerOf(uint256 tokenId) external view returns (address);
    function isApprovedForAll(address owner, address operator) external view returns (bool);
    function safeTransferFrom(address from, address to, uint256 id, uint256 amount, bytes calldata data) external;
    function getTokenId(uint256 anyId) external view returns (uint256);
}
