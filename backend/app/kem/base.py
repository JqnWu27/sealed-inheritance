from __future__ import annotations

from abc import ABC, abstractmethod


class WitnessKEM(ABC):
    name: str = "base"

    @abstractmethod
    def encap(self, statement: dict) -> tuple[bytes, bytes]:
        """Encapsulate to the public statement. Needs no witness."""

    @abstractmethod
    def decap(self, statement: dict, kem_ct: bytes, witness: dict) -> bytes | None:
        """Recover the key from the statement, the ciphertext and a witness.
        Returns None if the witness does not satisfy the condition."""

    def trace(self) -> list[str]:
        """Human-readable log of the last operation, for the UI trace panel."""
        return getattr(self, "_trace", [])
