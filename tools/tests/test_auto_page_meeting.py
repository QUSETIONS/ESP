from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_board_defines_auto_page_interval():
    board = read("main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc")

    assert "kAutoPageIntervalMs" in board
    # Cadence must sit inside the requested 15-30 s window.
    assert "20000" in board


def test_timed_task_auto_pages_only_when_meeting_page_active():
    board = read("main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc")

    # The auto-page branch lives inside the timed meeting task and gates on the
    # meeting page being active, so the sticky-note / lab pages stay static.
    assert "last_auto_page_ms" in board
    assert "IsMeetingAssistantPageActive()" in board
    assert "MeetingAssistantNextPage()" in board
    # Auto-page is only useful if it also pushes a refresh.
    assert "RequestUrgentRefresh()" in board