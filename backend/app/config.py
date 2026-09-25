"""Runtime configuration for the demo backend.

Everything is read from environment variables so the same code runs against an
Anvil fork and against Sepolia. Demo keys are generated on first run and stored
in backend/.demo-keys.json, which is git-ignored.
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYS_PATH = Path(os.environ.get("SEALED_KEYS_PATH", ROOT / "backend" / ".demo-keys.json"))
STATE_PATH = Path(os.environ.get("SEALED_STATE_PATH", ROOT / "backend" / ".demo-state.json"))


@dataclass
class Settings:
    rpc_url: str = os.environ.get("RPC_URL", "http://127.0.0.1:8545")
    chain_id: int = int(os.environ.get("CHAIN_ID", "11155111"))
    blocks_per_epoch: int = int(os.environ.get("BLOCKS_PER_EPOCH", "8"))
    window_epochs: int = int(os.environ.get("WINDOW_EPOCHS", "10"))       # N
    horizon_epochs: int = int(os.environ.get("HORIZON_EPOCHS", "60"))     # H
    lock_seconds: int = int(os.environ.get("LOCK_SECONDS", str(20 * 8 * 12)))  # 20 demo epochs of 12s blocks
    finality_lag_epochs: int = int(os.environ.get("FINALITY_LAG_EPOCHS", "1"))
    owner_name: str = os.environ.get("OWNER_NAME", "ken.eth")
    heir_name: str = os.environ.get("HEIR_NAME", "hana.eth")
    resolver: str = os.environ.get("RESOLVER", "")
    universal_resolver: str = os.environ.get("UNIVERSAL_RESOLVER", "")  # set on Sepolia, empty on Anvil
    studio: str = os.environ.get("STUDIO", "")
    opener: str = os.environ.get("OPENER", "")
    kem_backend: str = os.environ.get("KEM_BACKEND", "qap")  # qap | mock
    artifacts: Path = field(default_factory=lambda: ROOT / "contracts" / "out")


def _new_hex(n: int = 32) -> str:
    return "0x" + secrets.token_hex(n)


def load_keys() -> dict:
    """Demo key material. Owner and checker are secp256k1 (hex). Heir is X25519.
    Light-client signers are secp256k1 as well, four of them, threshold three."""
    if KEYS_PATH.exists():
        return json.loads(KEYS_PATH.read_text())
    from nacl.public import PrivateKey

    heir_sk = PrivateKey.generate()
    keys = {
        "owner": _new_hex(),
        "checker": _new_hex(),
        "watchtower": _new_hex(),
        "heir_eth": _new_hex(),
        "heir_x25519_sk": bytes(heir_sk).hex(),
        "heir_x25519_pk": bytes(heir_sk.public_key).hex(),
        "lightclient": [_new_hex() for _ in range(4)],
        "mock_kem_trapdoor": _new_hex(),
    }
    KEYS_PATH.write_text(json.dumps(keys, indent=2))
    return keys


settings = Settings()
