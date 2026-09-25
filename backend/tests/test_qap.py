import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.kem.qap import QapKEM, SilenceQAP, P  # noqa: E402
from app import crypto  # noqa: E402

STATEMENT = {"predicate": {"key": "heartbeat", "window": 10, "from_epoch": 2}, "anchor": {"epoch": 1}, "horizon": 60}


def kem():
    tmp = Path(tempfile.mkdtemp()) / "crs.json"
    return QapKEM(crs_path=tmp)


def test_qap_satisfied_and_quotient_exact():
    q = SilenceQAP()
    a = q.assignment(10, 13, 2)  # d = 1
    assert q.satisfied(a)
    h, exact = q.quotient(a)
    assert exact and len(h) == q.n - 1
    bad = q.assignment(10, 5, 2)  # d = -7
    assert not q.satisfied(bad)
    _, exact_bad = q.quotient(bad)
    assert not exact_bad


def test_roundtrip_key_matches_for_satisfying_witness():
    k = kem()
    ct, key = k.encap(STATEMENT)
    key2 = k.decap(STATEMENT, ct, {"epoch": 13, "heartbeat_epoch": 2})
    assert key2 == key


def test_key_differs_for_non_satisfying_witness():
    k = kem()
    ct, key = k.encap(STATEMENT)
    key2 = k.decap(STATEMENT, ct, {"epoch": 5, "heartbeat_epoch": 2})
    assert key2 != key
    # and the outer authenticated layer stays closed
    inner = b"inner box bytes"
    outer = crypto.seal_outer(key, STATEMENT, inner)
    assert crypto.open_outer(key2, STATEMENT, outer) is None
    assert crypto.open_outer(key, STATEMENT, outer) == inner


def test_from_epoch_counts_silence_from_sealing_heartbeat():
    k = kem()
    ct, key = k.encap(STATEMENT)
    # heartbeat record is stale (0) but the window was sealed at epoch 2: silence counted from 2
    assert k.decap(STATEMENT, ct, {"epoch": 11, "heartbeat_epoch": 0}) != key  # 11 - 2 = 9 < 10
    assert k.decap(STATEMENT, ct, {"epoch": 12, "heartbeat_epoch": 0}) == key  # 12 - 2 = 10
