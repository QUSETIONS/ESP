from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "tools" / "meeting_server" / "meeting_server.py").read_text(encoding="utf-8")


def test_notes_view_has_compact_list_editor_and_empty_states():
    assert 'id="notesTab"' in SOURCE
    assert 'id="notesView"' in SOURCE
    assert 'id="notesList"' in SOURCE
    assert 'id="notesListEmpty"' in SOURCE
    assert 'id="noteEditorEmpty"' in SOURCE
    assert 'class="notesLayout"' in SOURCE

    for control_id in (
        "newNote",
        "noteTitle",
        "noteBody",
        "noteCompleted",
        "noteRemindAt",
        "saveNoteButton",
        "deleteNoteButton",
    ):
        assert f'id="{control_id}"' in SOURCE

    assert 'type="datetime-local"' in SOURCE
    assert '@media (max-width: 700px)' in SOURCE


def test_notes_view_exposes_crud_toggle_and_reorder_contract():
    for function_name in (
        "loadNotes",
        "selectNote",
        "saveNote",
        "toggleNote",
        "deleteNote",
        "moveNote",
        "renderNotes",
    ):
        assert f"function {function_name}" in SOURCE

    assert 'fetchJson("/notes"' in SOURCE
    assert 'method: selectedNoteId ? "PATCH" : "POST"' in SOURCE
    assert 'method: "DELETE"' in SOURCE
    assert 'fetchJson("/notes/reorder"' in SOURCE
    assert 'method: "PUT"' in SOURCE
    assert "window.confirm" in SOURCE
    assert 'title="上移"' in SOURCE
    assert 'title="下移"' in SOURCE
    assert 'title="删除"' in SOURCE


def test_note_form_validates_utf8_byte_limits_before_save():
    assert "new TextEncoder()" in SOURCE
    assert "MAX_NOTE_TITLE_BYTES = 48" in SOURCE
    assert "MAX_NOTE_BODY_BYTES = 384" in SOURCE
    assert 'id="noteTitleBytes"' in SOURCE
    assert 'id="noteBodyBytes"' in SOURCE
    assert "validateNoteForm" in SOURCE
    assert "UTF-8" in SOURCE


def test_stale_versions_offer_explicit_reload_without_discarding_dirty_fields():
    assert "error.status = response.status" in SOURCE
    assert "error.payload = payload" in SOURCE
    assert "error.status === 409" in SOURCE
    assert 'id="reloadStaleNote"' in SOURCE
    assert "reloadSelectedNote" in SOURCE
    assert "applyNotesSnapshot(error.payload.data, true)" in SOURCE
    assert "if (!preserveDirty || !noteFormDirty)" in SOURCE


def test_note_sse_refresh_preserves_a_dirty_form_and_errors_are_local():
    assert 'eventSource.addEventListener("notes"' in SOURCE
    assert "loadNotes({preserveDirty: true})" in SOURCE
    assert 'id="noteError"' in SOURCE
    assert "setNoteError(error.message)" in SOURCE
    assert "noteFormDirty = true" in SOURCE
