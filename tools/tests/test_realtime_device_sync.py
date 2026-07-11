from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOARD = (ROOT / "main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc").read_text(encoding="utf-8")
DATA_H = (ROOT / "main/meeting/meeting_data.h").read_text(encoding="utf-8")
DATA_CC = (ROOT / "main/meeting/meeting_data.cc").read_text(encoding="utf-8")


def test_device_checks_version_every_five_seconds():
    assert "kMeetingVersionCheckIntervalMs = 5000" in BOARD
    assert "kMeetingTaskTickMs = 1000" in BOARD
    assert "FetchMeetingVersionOnce" in BOARD
    assert '"/meeting/version"' in BOARD


def test_unchanged_version_skips_full_fetch_and_refresh():
    assert "remote_version <= last_applied_meeting_version_" in BOARD
    assert "meeting version unchanged" in BOARD
    assert "FetchMeetingDataOnce()" in BOARD
    assert "IsMeetingAssistantPageActive()" in BOARD


def test_meeting_json_parses_and_applies_monotonic_version():
    assert "uint64_t version = 0;" in DATA_H
    assert 'JsonUInt64(payload, "version"' in DATA_CC
    assert "last_applied_meeting_version_ = data.version" in BOARD
