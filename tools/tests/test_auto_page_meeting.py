from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_board_has_no_automatic_meeting_page_refresh():
    board = read("main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc")

    assert "kAutoPageIntervalMs" not in board


def test_timed_task_keeps_manual_meeting_navigation_only():
    board = read("main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc")
    timed_task = board.split("void TimedMeetingTask()", 1)[1].split("bool IsNotesFetchInProgress()", 1)[0]

    assert "last_auto_page_ms" not in timed_task
    assert "MeetingAssistantNextPage()" not in timed_task
    assert "RequestUrgentRefresh()" not in timed_task


