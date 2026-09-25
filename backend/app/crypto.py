"""Envelope layers.

inner  = SealedBox(heir_pk).encrypt(cbor(bundle))          only the heir can read
outer  = SecretBox(K').encrypt(inner)                       K' = H(K || H(statement))
ct     = {statement, kem_ct, outer}                         stored in Studio, hash on ENS

K comes from the witness KEM adapter. Binding K' to the statement hash means a
ciphertext cannot be re-targeted to a different condition.
"""
from __future__ import annotations

import hashlib
import json

import cbor2
from nacl.public import PrivateKey, PublicKey, SealedBox
from nacl.secret import SecretBox


def statement_hash(statement: dict) -> bytes:
    canon = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canon).digest()


def derive_outer_key(kem_key: bytes, statement: dict) -> bytes:
    return hashlib.sha256(kem_key + statement_hash(statement)).digest()


def seal_inner(heir_pk_hex: str, bundle: dict) -> bytes:
    box = SealedBox(PublicKey(bytes.fromhex(heir_pk_hex)))
    return box.encrypt(cbor2.dumps(bundle))


def open_inner(heir_sk_hex: str, inner: bytes) -> dict:
    box = SealedBox(PrivateKey(bytes.fromhex(heir_sk_hex)))
    return cbor2.loads(box.decrypt(inner))


def seal_outer(kem_key: bytes, statement: dict, inner: bytes) -> bytes:
    return SecretBox(derive_outer_key(kem_key, statement)).encrypt(inner)


def open_outer(kem_key: bytes, statement: dict, outer: bytes) -> bytes | None:
    try:
        return SecretBox(derive_outer_key(kem_key, statement)).decrypt(outer)
    except Exception:
        return None


def pack_ciphertext(statement: dict, kem_ct: bytes, outer: bytes) -> bytes:
    return cbor2.dumps({"v": 1, "statement": statement, "kem_ct": kem_ct, "outer": outer})


def unpack_ciphertext(ct: bytes) -> dict:
    return cbor2.loads(ct)
