// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ITextResolver} from "./interfaces/ITextResolver.sol";
import {INameRegistry} from "./interfaces/INameRegistry.sol";
import {Strings} from "./Strings.sol";
import {Names} from "./Names.sol";

/// @title Opener
/// @notice Writes the `disclosure` record on a name once per window, after the
///         off-chain relation checker has accepted a witness and decrypted the
///         outer layer, and then hands a list of names to their heirs. A recorded
///         disclosure can never be changed or erased. The name owner grants this
///         contract the ENSv2 setter role scoped to the single key `disclosure`,
///         and approves it as an operator on every registry that holds a listed name.
///
///         Each planned handover stores the CANONICAL id of the name, the labelhash
///         uint256(keccak256(label)). In the ENSv2 PermissionedRegistry the token id
///         is regenerated every time a role is granted or revoked, so the live token
///         id is looked up with registry.getTokenId(id) right before the transfer.
///
///         The checker signature is a stand-in for on-chain witness
///         verification. The checker signs keccak256(node, window, innerHash).
contract Opener {
    using Strings for uint256;
    using Strings for bytes32;

    /// @notice One name that moves to `heir` at the first opening after it was planned.
    struct Handover {
        address registry; // ENSv2 registry holding the name token
        uint256 id;       // canonical id of the name, the labelhash; a token id works as well
        address heir;     // who receives the name
    }

    address public immutable checker;
    ITextResolver public immutable resolver;
    mapping(bytes32 => mapping(uint64 => bool)) public opened; // node => window
    mapping(bytes32 => Handover[]) internal _handovers;        // node => handover plan
    mapping(bytes32 => address) public planner;                // node => who set the plan, must still own the names

    event Opened(bytes32 indexed node, uint64 window, bytes32 innerHash);
    event HandoverConfigured(bytes32 indexed node, address registry, uint256 tokenId, address owner, address heir);
    event NameHandedOver(bytes32 indexed node, address registry, uint256 tokenId, address from, address to);
    event HandoverSkipped(bytes32 indexed node, string reason);

    error AlreadyOpened(bytes32 node, uint64 window);
    error BadCheckerSignature();
    error NotNameOwner();
    error NotPlanner();
    error InvalidHandover(uint256 index);

    constructor(address checker_, ITextResolver resolver_) {
        checker = checker_;
        resolver = resolver_;
    }

    function openingDigest(bytes32 node, uint64 window, bytes32 innerHash) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(node, window, innerHash));
    }

    /// @notice Plan a single handover. Kept for the Studio and the Sepolia scripts, it
    ///         sets a one-entry list. `tokenId` may be a live token id or the canonical id.
    function setHandover(bytes calldata dnsName, address registry, uint256 tokenId, address heir) external {
        Handover[] memory list = new Handover[](1);
        list[0] = Handover(registry, tokenId, heir);
        _setHandovers(Names.namehash(dnsName), list);
    }

    /// @notice Replace the handover plan of `dnsName` with `list`. The caller must be
    ///         the current owner of every listed name. On the first opening after this,
    ///         every listed name moves from the caller to its heir, provided the caller
    ///         approved this contract as an operator on that registry. An empty list
    ///         cancels the plan and is only accepted from the account that set it.
    function setHandovers(bytes calldata dnsName, Handover[] calldata list) external {
        _setHandovers(Names.namehash(dnsName), list);
    }

    function handoverCount(bytes32 node) external view returns (uint256) {
        return _handovers[node].length;
    }

    function handoverAt(bytes32 node, uint256 i) external view returns (Handover memory) {
        return _handovers[node][i];
    }

    /// @notice First entry of the plan, in the shape of the former single-handover getter.
    function handover(bytes32 node)
        external
        view
        returns (address registry, uint256 tokenId, address owner, address heir)
    {
        Handover[] storage list = _handovers[node];
        if (list.length == 0) return (address(0), 0, address(0), address(0));
        Handover storage h = list[0];
        return (h.registry, _liveTokenId(INameRegistry(h.registry), h.id), planner[node], h.heir);
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

    function _setHandovers(bytes32 node, Handover[] memory list) internal {
        for (uint256 i = 0; i < list.length; i++) {
            Handover memory h = list[i];
            if (h.registry == address(0) || h.heir == address(0)) revert InvalidHandover(i);
            INameRegistry reg = INameRegistry(h.registry);
            if (reg.ownerOf(_liveTokenId(reg, h.id)) != msg.sender) revert NotNameOwner();
        }
        if (list.length == 0 && planner[node] != msg.sender) revert NotPlanner();
        delete _handovers[node];
        planner[node] = msg.sender;
        for (uint256 i = 0; i < list.length; i++) {
            Handover memory h = list[i];
            _handovers[node].push(h);
            emit HandoverConfigured(
                node, h.registry, _liveTokenId(INameRegistry(h.registry), h.id), msg.sender, h.heir
            );
        }
    }

    /// @dev The handover never blocks the disclosure. Every reason an entry cannot move is
    ///      emitted and the loop continues with the next entry.
    function _handOver(bytes32 node) internal {
        Handover[] storage list = _handovers[node];
        uint256 n = list.length;
        if (n == 0) return;
        address from = planner[node];
        for (uint256 i = 0; i < n; i++) {
            Handover memory h = list[i];
            if (h.registry.code.length == 0) {
                emit HandoverSkipped(node, "registry has no code");
                continue;
            }
            INameRegistry reg = INameRegistry(h.registry);
            uint256 tokenId = _liveTokenId(reg, h.id);
            address current;
            try reg.ownerOf(tokenId) returns (address o) {
                current = o;
            } catch {
                emit HandoverSkipped(node, "ownerOf failed");
                continue;
            }
            if (current == h.heir) {
                emit HandoverSkipped(node, "heir already owns the name");
                continue;
            }
            if (current != from) {
                emit HandoverSkipped(node, "name no longer owned by the planner");
                continue;
            }
            bool approved;
            try reg.isApprovedForAll(from, address(this)) returns (bool a) {
                approved = a;
            } catch {
                emit HandoverSkipped(node, "isApprovedForAll failed");
                continue;
            }
            if (!approved) {
                emit HandoverSkipped(node, "opener not approved as operator");
                continue;
            }
            try reg.safeTransferFrom(from, h.heir, tokenId, 1, "") {
                emit NameHandedOver(node, h.registry, tokenId, from, h.heir);
            } catch {
                emit HandoverSkipped(node, "transfer reverted");
            }
        }
    }

    /// @dev Live token id for a canonical id. A registry without getTokenId (or without code)
    ///      is assumed to use stable ids, so the stored id is returned unchanged.
    function _liveTokenId(INameRegistry reg, uint256 id) internal view returns (uint256) {
        if (address(reg).code.length == 0) return id;
        try reg.getTokenId(id) returns (uint256 t) {
            return t;
        } catch {
            return id;
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
