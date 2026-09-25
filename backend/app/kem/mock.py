"""Placeholder KEM for development.

INSECURE STAND-IN. The key is derived from a backend-held trapdoor and released
only when the witness satisfies the condition's arithmetic. It reproduces the
interface and the trace so the rest of the system can be built and demonstrated
before the real adapter is wired in.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from .base import WitnessKEM


def condition_holds(statement: dict, witness: dict) -> tuple[bool, str]:
    n = int(statement["predicate"]["window"])
    hb = max(int(witness["heartbeat_epoch"]), int(statement["predicate"].get("from_epoch", 0)))
    e = int(witness["epoch"])
    d = e - hb - n
    return d >= 0, f"epoch {e} - heartbeat {hb} - N {n} = {d} {'>= 0 ok' if d >= 0 else '< 0, condition false'}"


class MockKEM(WitnessKEM):
    name = "mock"

    def __init__(self, trapdoor: bytes):
        self._t = trapdoor
        self._trace: list[str] = []

    def _key(self, statement_id: bytes, r: bytes) -> bytes:
        return hmac.new(self._t, statement_id + r, hashlib.sha256).digest()

    def encap(self, statement: dict) -> tuple[bytes, bytes]:
        from ..crypto import statement_hash

        r = secrets.token_bytes(32)
        sid = statement_hash(statement)
        self._trace = ["mock encap: statement hash " + sid.hex()[:16] + ", no witness used"]
        return r, self._key(sid, r)

    def decap(self, statement: dict, kem_ct: bytes, witness: dict) -> bytes | None:
        from ..crypto import statement_hash

        ok, line = condition_holds(statement, witness)
        self._trace = ["mock decap: " + line]
        if not ok:
            self._trace.append("mock decap: no key")
            return None
        k = self._key(statement_hash(statement), kem_ct)
        self._trace.append("mock decap: key fingerprint " + hashlib.sha256(k).hexdigest()[:16])
        return k
