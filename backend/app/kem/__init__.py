"""Witness KEM adapters.

Interface
    encap(statement) -> (kem_ct: bytes, key: bytes)
    decap(statement, kem_ct, witness) -> key: bytes | None

The relation checker runs before decap and supplies the witness values. The
adapter is responsible for the arithmetic of the condition on those values.
"""
from __future__ import annotations

from .base import WitnessKEM
from .mock import MockKEM


def load(name: str, trapdoor_hex: str) -> WitnessKEM:
    if name == "qap":
        from .qap import QapKEM

        return QapKEM()
    return MockKEM(bytes.fromhex(trapdoor_hex[2:] if trapdoor_hex.startswith("0x") else trapdoor_hex))
