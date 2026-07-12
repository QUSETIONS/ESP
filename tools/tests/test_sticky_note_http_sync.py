from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOARD = (ROOT / "main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc").read_text(
    encoding="utf-8"
)


def section_after(marker: str) -> str:
    return BOARD.split(marker, 1)[1]


def test_notes_version_is_polled_every_five_seconds_without_changing_meeting_polling():
    assert "kNotesVersionCheckIntervalMs = 5000" in BOARD
    assert "StartNotesFetchTask();" in section_after("void TimedMeetingTask()")
    assert "StartMeetingFetchTask();" in section_after("void TimedMeetingTask()")
    assert "StartNotesFetchTask();" in section_after("case WifiEvent::Connected:")


def test_notes_fetches_snapshot_only_when_the_http_version_is_newer():
    task = section_after("void NotesFetchTask()")
    assert "FetchNotesVersionOnce(remote_version)" in task
    assert "remote_version <= note_repository_.snapshot().version" in task
    assert "FetchNotesDataOnce()" in task
    assert task.index("remote_version <= note_repository_.snapshot().version") < task.index(
        "FetchNotesDataOnce()"
    )
    assert '"/notes/version"' in BOARD
    assert '"/notes"' in BOARD


def test_notes_snapshot_is_bounded_validated_and_replaced_before_any_display_handoff():
    fetch = section_after("bool FetchNotesDataOnce()")
    assert "cJSON_ParseWithLength" in fetch
    assert "cJSON_IsArray(notes)" in fetch
    assert "count > gotim::kMaxNotes" in fetch
    assert "cJSON_IsString(title)" in fetch
    assert "cJSON_IsString(body)" in fetch
    assert "gotim::SetNoteText" in fetch
    assert "note_repository_.ReplaceIfNewer(snapshot)" in fetch
    assert "display_->" not in fetch.split("void InitializeButtons()", 1)[0]
