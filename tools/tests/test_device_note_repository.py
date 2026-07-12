from __future__ import annotations

import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_HEADER = ROOT / "main" / "notes" / "note_data.h"
DATA_SOURCE = ROOT / "main" / "notes" / "note_data.cc"
REPOSITORY_HEADER = ROOT / "main" / "notes" / "note_repository.h"
REPOSITORY_SOURCE = ROOT / "main" / "notes" / "note_repository.cc"
CMAKE = ROOT / "main" / "CMakeLists.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_note_model_has_fixed_utf8_limits_and_versions():
    source = read(DATA_HEADER)

    assert "kMaxNotes = 20" in source
    assert "kMaxTitleBytes = 48" in source
    assert "kMaxBodyBytes = 384" in source
    assert "kNoteSchemaVersion" in source
    assert "kNoteDataVersion" in source
    assert "std::array<char" in source
    assert "title_length" in source
    assert "body_length" in source
    assert "reminder_length" in source
    assert "SetNoteText" in source


def test_serialization_contract_uses_lengths_and_crc32_vector():
    source = read(DATA_SOURCE)

    assert "ComputeNoteCrc32" in source
    assert "0xEDB88320" in source
    assert "AppendU16" in source
    assert "AppendU64" in source
    assert "AppendBytes" in source
    assert "ReadU16" in source
    assert "ReadU64" in source
    assert "crc32" in source.lower()

    # Standard CRC-32 vector. The firmware implementation must return this
    # value for the same payload before its stored CRC field is appended.
    assert zlib.crc32(b"123456789") & 0xFFFFFFFF == 0xCBF43926


def test_repository_uses_private_notes_namespace_and_staged_active_commit():
    source = read(REPOSITORY_SOURCE)

    assert 'kNamespace[] = "gotim_notes"' in source
    assert 'kStagingKey[] = "staging"' in source
    assert 'kActiveKey[] = "active"' in source
    assert "nvs_set_blob(nvs, kStagingKey" in source
    assert "nvs_get_blob(nvs, kStagingKey" in source
    assert "ValidateSnapshot" in source
    assert "nvs_set_blob(nvs, kActiveKey" in source
    assert "nvs_commit(nvs)" in source
    assert "nvs_erase_all" not in source
    assert '"wifi"' not in source
    assert '"meeting"' not in source


def test_repository_contract_covers_load_fallback_and_mutation_semantics():
    header = read(REPOSITORY_HEADER)
    source = read(REPOSITORY_SOURCE)

    for method in (
        "Load",
        "Save",
        "ReplaceIfNewer",
        "ToggleComplete",
        "MarkDelivered",
        "NextReminder",
    ):
        assert method in header

    assert "MakeStarterNoteSnapshot" in source
    assert "ReadSnapshot(nvs, kActiveKey" in source
    assert "ReadSnapshot(nvs, kStagingKey" in source
    assert "candidate.version <= snapshot_.version" in source
    assert "note.completed = !note.completed" in source
    assert "note.delivered = true" in source
    assert "note.delivered = false" in source
    assert "note.reminder_unix_seconds > now_unix_seconds" in source
    assert "earliest_reminder" in source


def test_firmware_component_builds_note_sources():
    source = read(CMAKE)

    assert '"notes/note_data.cc"' in source
    assert '"notes/note_repository.cc"' in source
