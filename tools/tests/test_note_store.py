from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.meeting_server import note_store as note_store_module
from tools.meeting_server.note_store import (
    NoteValidationError,
    VersionConflictError,
    VersionedNoteStore,
)


def make_store(tmp_path: Path) -> VersionedNoteStore:
    return VersionedNoteStore(tmp_path / "notes.json")


def test_empty_store_has_canonical_default_snapshot(tmp_path):
    store = make_store(tmp_path)

    assert store.read() == {"version": 0, "notes": []}


def test_create_generates_stable_id_and_increments_version_once(tmp_path):
    store = make_store(tmp_path)

    created = store.create({"title": "Demo", "body": "Bring iPhone"})

    assert created["version"] == 1
    assert len(created["notes"]) == 1
    note = created["notes"][0]
    assert len(note["id"]) == 32
    assert all(character in "0123456789abcdef" for character in note["id"])
    assert note["title"] == "Demo"
    assert note["body"] == "Bring iPhone"
    assert note["completed"] is False
    assert note["remind_at"] is None
    assert note["order"] == 0
    assert note["updated_at"]
    assert store.read() == created


def test_patch_changes_only_once_and_normalizes_canonical_order(tmp_path):
    store = make_store(tmp_path)
    created = store.create({"title": "Demo"})
    note_id = created["notes"][0]["id"]

    patched = store.patch(note_id, {"body": "Bring iPhone", "completed": True})

    assert patched["version"] == 2
    assert patched["notes"][0]["body"] == "Bring iPhone"
    assert patched["notes"][0]["completed"] is True
    assert patched["notes"][0]["order"] == 0


def test_noop_patch_does_not_increment(tmp_path):
    store = make_store(tmp_path)
    created = store.create({"title": "Demo", "body": "Bring iPhone"})

    same = store.patch(created["notes"][0]["id"], {"title": "Demo"})

    assert same["version"] == created["version"]
    assert same == created


def test_mutation_results_report_changed_without_altering_snapshot_methods(tmp_path):
    store = make_store(tmp_path)

    created = store.create_with_result({"title": "Demo"})
    unchanged = store.patch_with_result(created.snapshot["notes"][0]["id"], {"title": "Demo"})

    assert created.changed is True
    assert store.create({"title": "Second"})["version"] == created.snapshot["version"] + 1
    assert unchanged.changed is False
    assert unchanged.snapshot == created.snapshot


def test_stale_base_version_raises_and_preserves_latest_snapshot(tmp_path):
    store = make_store(tmp_path)
    created = store.create({"title": "A"})
    note_id = created["notes"][0]["id"]
    latest = store.patch(note_id, {"title": "B"})

    with pytest.raises(VersionConflictError) as exc_info:
        store.patch(note_id, {"title": "C"}, base_version=created["version"])

    assert exc_info.value.snapshot == latest
    assert store.read() == latest


def test_malformed_reminder_is_rejected_without_persisting(tmp_path):
    store = make_store(tmp_path)
    created = store.create({"title": "A"})

    with pytest.raises(NoteValidationError):
        store.patch(created["notes"][0]["id"], {"remind_at": "tomorrow morning"})

    assert store.read() == created


def test_reorder_rejects_duplicate_ids_without_persisting(tmp_path):
    store = make_store(tmp_path)
    first = store.create({"title": "A"})
    second = store.create({"title": "B"})
    before = store.read()
    ids = [note["id"] for note in before["notes"]]

    with pytest.raises(NoteValidationError):
        store.reorder([ids[0], ids[0]])

    assert store.read() == before
    assert second["version"] == 2
    assert first["version"] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "x" * 49),
        ("body", "x" * 385),
        ("title", "中" * 17),
        ("body", "中" * 129),
    ],
)
def test_text_limits_are_utf8_byte_limits(tmp_path, field, value):
    store = make_store(tmp_path)

    with pytest.raises(NoteValidationError):
        store.create({field: value})


def test_twentieth_note_is_allowed_but_twenty_first_is_rejected(tmp_path):
    store = make_store(tmp_path)
    for index in range(20):
        store.create({"title": str(index)})
    before = store.read()

    with pytest.raises(NoteValidationError):
        store.create({"title": "too many"})

    assert store.read() == before
    assert len(before["notes"]) == 20
    assert [note["order"] for note in before["notes"]] == list(range(20))


def test_reorder_changes_order_once_and_delete_changes_once(tmp_path):
    store = make_store(tmp_path)
    store.create({"title": "A"})
    store.create({"title": "B"})
    before = store.read()
    ids = [note["id"] for note in before["notes"]]

    reordered = store.reorder(list(reversed(ids)))
    assert reordered["version"] == before["version"] + 1
    assert [note["id"] for note in reordered["notes"]] == [ids[1], ids[0]]
    assert [note["order"] for note in reordered["notes"]] == [0, 1]

    deleted = store.delete(ids[0])
    assert deleted["version"] == reordered["version"] + 1
    assert [note["id"] for note in deleted["notes"]] == [ids[1]]
    assert deleted["notes"][0]["order"] == 0


def test_atomic_file_replacement_writes_temp_file_then_replaces_target(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    replacements: list[tuple[Path, Path]] = []
    real_replace = note_store_module.os.replace

    def record_replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        return real_replace(source, destination)

    monkeypatch.setattr(note_store_module.os, "replace", record_replace)
    store.create({"title": "Atomic"})

    assert len(replacements) == 1
    source, destination = replacements[0]
    assert destination == store.path
    assert source != destination
    assert not source.exists()
    assert json.loads(store.path.read_text(encoding="utf-8"))["notes"][0]["title"] == "Atomic"


def test_rejected_mutation_preserves_file_bytes(tmp_path):
    store = make_store(tmp_path)
    store.create({"title": "A"})
    before = store.path.read_bytes()
    note_id = store.read()["notes"][0]["id"]

    with pytest.raises(NoteValidationError):
        store.patch(note_id, {"body": "x" * 385})

    assert store.path.read_bytes() == before
