from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "ble_meeting_sync" / "ble_frame_tool.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("ble_frame_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_single_frame_sets_first_and_last():
    tool = load_tool()

    frames = tool.encode_meeting_frames(b"{}", max_frame_bytes=20)

    assert frames == [bytes([0, tool.FLAG_FIRST | tool.FLAG_LAST, 2]) + b"{}"]


def test_multi_frame_sequence_and_lengths():
    tool = load_tool()

    frames = tool.encode_meeting_frames(b"abcdef", max_frame_bytes=6)

    assert frames[0] == bytes([0, tool.FLAG_FIRST, 3]) + b"abc"
    assert frames[1] == bytes([1, tool.FLAG_LAST, 3]) + b"def"


def test_empty_payload_is_valid_first_last_zero_length_frame():
    tool = load_tool()

    assert tool.encode_meeting_frames(b"") == [bytes([0, tool.FLAG_FIRST | tool.FLAG_LAST, 0])]


def test_sequence_wraps_at_255():
    tool = load_tool()

    frames = tool.encode_meeting_frames(b"x" * 258, max_frame_bytes=4)

    assert frames[0][0] == 0
    assert frames[255][0] == 255
    assert frames[256][0] == 0
    assert frames[-1][1] & tool.FLAG_LAST


def test_rejects_frame_size_that_cannot_carry_payload():
    tool = load_tool()

    try:
        tool.encode_meeting_frames(b"{}", max_frame_bytes=3)
    except ValueError as exc:
        assert "max_frame_bytes" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_encode_provision_payload_normalizes_wifi_json():
    tool = load_tool()

    payload = tool.encode_provision_payload(
        ssid="Demo24G",
        password="12345678",
        meeting_url="http://172.20.10.10:8787/meeting/current",
    )

    assert payload == (
        b'{"ssid":"Demo24G","password":"12345678",'
        b'"meeting_url":"http://172.20.10.10:8787/meeting/current"}'
    )
    assert len(payload) <= tool.MAX_PROVISION_JSON_BYTES


def test_encode_provision_payload_rejects_invalid_bounds():
    tool = load_tool()

    try:
        tool.encode_provision_payload(ssid="", password="")
    except ValueError as exc:
        assert "ssid" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")

    try:
        tool.encode_provision_payload(ssid="Demo", password="x" * 65)
    except ValueError as exc:
        assert "password" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")
