"""ENS name helpers. namehash follows ENSIP-1, labels hashed right to left."""
from __future__ import annotations

from eth_utils import keccak


def namehash(name: str) -> bytes:
    node = b"\x00" * 32
    if not name:
        return node
    for label in reversed(name.lower().split(".")):
        node = keccak(node + keccak(label.encode()))
    return node


def dns_encode(name: str) -> bytes:
    """DNS wire format, used by some ENSv2 write functions."""
    out = b""
    for label in name.lower().split("."):
        b = label.encode()
        out += bytes([len(b)]) + b
    return out + b"\x00"
