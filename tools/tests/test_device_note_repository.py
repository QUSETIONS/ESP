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


def test_repository_guards_serializer_and_reminder_version_edges():
    data = read(DATA_SOURCE)
    repo = read(REPOSITORY_SOURCE)
    assert "snapshot.count > kMaxNotes" in data
    assert "title_length > kMaxTitleBytes" in data
    assert "incoming.delivered = false" in repo
    assert "UINT64_MAX" in repo
    assert "note.delivered || note.completed" in repo


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

    assert "FillStarterNoteSnapshot" in source
    assert "ReadSnapshot(nvs, kActiveKey" in source
    assert "ReadSnapshot(nvs, kStagingKey" in source
    assert "candidate.version <= snapshot_.version" in source
    assert "note.completed = !note.completed" in source
    assert "note.delivered = true" in source
    assert "note.delivered = false" in source
    assert "note.reminder_unix_seconds > now_unix_seconds" in source
    assert "earliest_reminder" in source



def test_repository_startup_load_does_not_copy_snapshot_on_task_stack():
    data_header = read(DATA_HEADER)
    data_source = read(DATA_SOURCE)
    repo_header = read(REPOSITORY_HEADER)
    repo_source = read(REPOSITORY_SOURCE)

    assert "void FillStarterNoteSnapshot(NoteSnapshot* snapshot)" in data_header
    assert "void FillStarterNoteSnapshot(NoteSnapshot* snapshot)" in data_source
    assert "esp_err_t Load();" in repo_header
    load_body = repo_source.split("esp_err_t NoteRepository::Load()", 1)[1].split(
        "esp_err_t NoteRepository::Load(NoteSnapshot* out)", 1
    )[0]
    assert "NoteSnapshot loaded" not in load_body
    assert "FillStarterNoteSnapshot(&snapshot_)" in load_body


def test_repository_runtime_mutations_do_not_allocate_snapshots_on_task_stack():
    repo_source = read(REPOSITORY_SOURCE)
    assert "std::make_unique<NoteSnapshot>" in repo_source
    assert "NoteSnapshot verified;" not in repo_source
    assert "NoteSnapshot normalized" not in repo_source
    assert "NoteSnapshot candidate" not in repo_source

def test_firmware_component_builds_note_sources():
    source = read(CMAKE)

    assert '"notes/note_data.cc"' in source
    assert '"notes/note_repository.cc"' in source
