// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ITextResolver} from "./interfaces/ITextResolver.sol";
import {Strings} from "./Strings.sol";
import {Names} from "./Names.sol";

/// @title Studio
/// @notice One contract per owner name. It is the vault, the rotation counter,
///         the sealed-envelope store and the heartbeat writer.
///
///  - Slips are EIP-712 authorizations signed by the owner. A slip pays only if
///    its `nonce` equals the current counter and `notBefore` has passed.
///  - `heartbeat` turns the counter, stores the new sealed envelope for the new
///    window, and writes the `heartbeat` and `sealed` text records on the
///    owner's ENS name. The name owner grants this contract the ENSv2 setter
///    role scoped to exactly those two keys.
contract Studio {
    using Strings for uint256;
    using Strings for bytes32;
    using Strings for address;

    struct Slip {
        address to;
        uint256 amount;
        uint64 notBefore;
        uint64 nonce;
    }

    bytes32 public constant SLIP_TYPEHASH =
        keccak256("Slip(address to,uint256 amount,uint64 notBefore,uint64 nonce)");
    bytes32 private constant DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");

    address public immutable owner;
    bytes32 public immutable node; // namehash of the owner's ENS name
    bytes public dnsName; // DNS-encoded owner name, used by ENSv2 setters
    ITextResolver public immutable resolver;
    uint256 public immutable blocksPerEpoch;

    uint64 public nonce; // rotation counter, also the current window number
    mapping(uint64 => bytes) public sealedEnvelope; // window => ciphertext

    event Heartbeat(uint64 indexed window, uint256 epoch, bytes32 ciphertextHash);
    event Executed(address indexed to, uint256 amount, uint64 nonce);
    event Deposited(address indexed from, uint256 amount);

    error NotOwner();
    error TooEarly(uint64 notBefore, uint256 nowTs);
    error StaleNonce(uint64 slipNonce, uint64 current);
    error BadSignature();
    error TransferFailed();

    constructor(address owner_, bytes memory dnsName_, ITextResolver resolver_, uint256 blocksPerEpoch_) {
        owner = owner_;
        dnsName = dnsName_;
        node = Names.namehash(dnsName_);
        resolver = resolver_;
        blocksPerEpoch = blocksPerEpoch_ == 0 ? 1 : blocksPerEpoch_;
    }

    receive() external payable {
        emit Deposited(msg.sender, msg.value);
    }

    /// @notice Demo epoch clock derived from block numbers.
    function currentEpoch() public view returns (uint256) {
        return block.number / blocksPerEpoch;
    }

    /// @notice Roll to the next window. `ciphertext` is the new sealed envelope,
    ///         `condition` is the public condition string for the `sealed` record.
    function heartbeat(bytes calldata ciphertext, string calldata condition) external {
        if (msg.sender != owner) revert NotOwner();
        nonce += 1;
        sealedEnvelope[nonce] = ciphertext;
        bytes32 h = keccak256(ciphertext);
        uint256 epoch = currentEpoch();

        resolver.setText(dnsName, "heartbeat", epoch.toDecimal());
        resolver.setText(
            dnsName,
            "sealed",
            string.concat(
                "studio=", address(this).toHex(),
                ";window=", uint256(nonce).toDecimal(),
                ";ct=", h.toHex(),
                ";", condition
            )
        );
        emit Heartbeat(nonce, epoch, h);
    }

    /// @notice Cancel all outstanding slips without sealing a new envelope.
    function bump() external {
        if (msg.sender != owner) revert NotOwner();
        nonce += 1;
    }

    function domainSeparator() public view returns (bytes32) {
        return keccak256(
            abi.encode(
                DOMAIN_TYPEHASH,
                keccak256("SealedInheritance"),
                keccak256("1"),
                block.chainid,
                address(this)
            )
        );
    }

    function slipDigest(Slip calldata s) public view returns (bytes32) {
        bytes32 structHash = keccak256(abi.encode(SLIP_TYPEHASH, s.to, s.amount, s.notBefore, s.nonce));
        return keccak256(abi.encodePacked("\x19\x01", domainSeparator(), structHash));
    }

    /// @notice Anyone may submit a slip. It pays only if signed by the owner,
    ///         carrying the current counter, after its valid-after time.
    function execute(Slip calldata s, bytes calldata sig) external {
        if (block.timestamp < s.notBefore) revert TooEarly(s.notBefore, block.timestamp);
        if (s.nonce != nonce) revert StaleNonce(s.nonce, nonce);
        if (_recover(slipDigest(s), sig) != owner) revert BadSignature();
        (bool ok,) = s.to.call{value: s.amount}("");
        if (!ok) revert TransferFailed();
        emit Executed(s.to, s.amount, s.nonce);
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
