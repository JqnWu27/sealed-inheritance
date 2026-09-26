"""Slot derivation and string decoding for the storage proof, no network needed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.names import namehash  # noqa: E402
from app.stateproof import (  # noqa: E402
    decode_solidity_string,
    ens_beta_record_id_slot,
    ens_beta_text_slot,
    long_string_data_slots,
    mock_text_slot,
)

NODE = namehash("yutotanaka.eth")

# Slots observed by tracing resolve(yutotanaka.eth, text(heartbeat)) on an Anvil fork of Sepolia,
# resolver 0xaa1825716cb9d4c8518BA378734D783bAabd5f80, implementation 0x14f09fd0..cf243.
TRACED_RECORD_ID_SLOT = 0x770250b695c42832dad462ba16a8c0c19a9b7f688b3dd487ef58084fbf1eb941
TRACED_HEARTBEAT_SLOT = 0x8da16641951489f53dc45a72f3c9e47e56108077cef58c28885b45be6a7e776d


def test_ens_beta_layout_reproduces_the_traced_slots():
    assert ens_beta_record_id_slot(NODE) == TRACED_RECORD_ID_SLOT
    assert ens_beta_text_slot(1, "heartbeat") == TRACED_HEARTBEAT_SLOT


def test_different_keys_and_records_land_on_different_slots():
    assert ens_beta_text_slot(1, "heartbeat") != ens_beta_text_slot(1, "sealed")
    assert ens_beta_text_slot(1, "heartbeat") != ens_beta_text_slot(2, "heartbeat")
    assert mock_text_slot(NODE, "heartbeat") != mock_text_slot(NODE, "sealed")


def test_short_and_long_string_decoding():
    short = int.from_bytes(b"368213".ljust(31, b"\0") + bytes([12]), "big")
    assert decode_solidity_string(short) == ("368213", None)
    assert decode_solidity_string(0) == ("", None)
    text = b"studio=0x56caf0c5;window=2;" * 3  # 81 bytes, long string
    main = 2 * len(text) + 1
    value, length = decode_solidity_string(main)
    assert value is None and length == len(text)
    words = [int.from_bytes(text[i:i + 32].ljust(32, b"\0"), "big") for i in range(0, len(text), 32)]
    assert decode_solidity_string(main, words) == (text.decode(), len(text))
    assert len(long_string_data_slots(TRACED_HEARTBEAT_SLOT, len(text))) == 3
