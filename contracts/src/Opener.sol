// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ITextResolver} from "./interfaces/ITextResolver.sol";
import {INameRegistry} from "./interfaces/INameRegistry.sol";
import {Strings} from "./Strings.sol";
import {Names} from "./Names.sol";

/// @title Opener
/// @notice Writes the `disclosure` record on a name once per window, after the
///         off-chain relation checker has accepted a witness and decrypted the
///         outer layer, and then hands the name itself to the heir. A recorded
///         disclosure can never be changed or erased. The name owner grants this
///         contract the ENSv2 setter role scoped to the single key `disclosure`,
///         and approves it as an operator on the registry for the handover.
///
///         The checker signature is a stand-in for on-chain witness
///         verification. The checker signs keccak256(node, window, innerHash).
contract Opener {
    using Strings for uint256;
    using Strings for bytes32;

    struct Handover {
        address registry; // ENSv2 registry holding the name token
        uint256 tokenId;  // the name's token id in that registry
        address owner;    // who configured it, must still own the token at opening
        address heir;     // who receives the name
    }

    address public immutable checker;
    ITextResolver public immutable resolver;
    mapping(bytes32 => mapping(uint64 => bool)) public opened; // node => window
    mapping(bytes32 => Handover) public handover;              // node => handover plan

    event Opened(bytes32 indexed node, uint64 window, bytes32 innerHash);
    event HandoverConfigured(bytes32 indexed node, address registry, uint256 tokenId, address owner, address heir);
    event NameHandedOver(bytes32 indexed node, address registry, uint256 tokenId, address from, address to);
    event HandoverSkipped(bytes32 indexed node, string reason);

    error AlreadyOpened(bytes32 node, uint64 window);
    error BadCheckerSignature();
    error NotNameOwner();

    constructor(address checker_, ITextResolver resolver_) {
        checker = checker_;
        resolver = resolver_;
    }

    function openingDigest(bytes32 node, uint64 window, bytes32 innerHash) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(node, window, innerHash));
    }

    /// @notice The name owner plans the handover: on the first opening after this,
    ///         the name token moves from the owner to the heir, provided the owner
    ///         has approved this contract as an operator on the registry.
    function setHandover(bytes calldata dnsName, address registry, uint256 tokenId, address heir) external {
        bytes32 node = Names.namehash(dnsName);
        if (INameRegistry(registry).ownerOf(tokenId) != msg.sender) revert NotNameOwner();
        handover[node] = Handover(registry, tokenId, msg.sender, heir);
        emit HandoverConfigured(node, registry, tokenId, msg.sender, heir);
    }

    function recordOpening(bytes calldata dnsName, uint64 window, bytes32 innerHash, bytes calldata sig) external {
        bytes32 node = Names.namehash(dnsName);
        if (opened[node][window]) revert AlreadyOpened(node, window);
        if (_recover(openingDigest(node, window, innerHash), sig) != checker) revert BadCheckerSignature();
        opened[node][window] = true;
        resolver.setText(
            dnsName,
            "disclosure",
            string.concat("window=", uint256(window).toDecimal(), ";inner=", innerHash.toHex())
        );
        emit Opened(node, window, innerHash);
        _handOver(node);
    }

    /// @dev The handover never blocks the disclosure. Every reason it cannot happen is emitted.
    function _handOver(bytes32 node) internal {
        Handover memory h = handover[node];
        if (h.registry == address(0)) return;
        INameRegistry reg = INameRegistry(h.registry);
        address current;
        try reg.ownerOf(h.tokenId) returns (address o) {
            current = o;
        } catch {
            emit HandoverSkipped(node, "ownerOf failed");
            return;
        }
        if (current == h.heir) {
            emit HandoverSkipped(node, "heir already owns the name");
            return;
        }
        if (current != h.owner) {
            emit HandoverSkipped(node, "name no longer owned by the planner");
            return;
        }
        if (!reg.isApprovedForAll(h.owner, address(this))) {
            emit HandoverSkipped(node, "opener not approved as operator");
            return;
        }
        try reg.safeTransferFrom(h.owner, h.heir, h.tokenId, 1, "") {
            emit NameHandedOver(node, h.registry, h.tokenId, h.owner, h.heir);
        } catch {
            emit HandoverSkipped(node, "transfer reverted");
        }
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
