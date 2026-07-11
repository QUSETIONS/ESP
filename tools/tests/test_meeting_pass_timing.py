from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_meeting_data_tracks_active_reminder_for_timed_highlight():
    header = read("main/meeting/meeting_data.h")
    ui = read("main/display/pages/meeting_assistant_page_adapter.cc")

    assert "int active_reminder_index = -1;" in header
    assert "active_reminder_index" in ui
    assert "BuildCleanReminderPage" in ui
    assert "MakeFilledLabel(list, meeting_data_.reminders[i].time.c_str()" in ui


def test_board_has_online_timed_meeting_scheduler():
    source = read("main/boards/zectrix-s3-epaper-4.2/zectrix-s3-epaper-4.2.cc")

    assert "kMeetingTimedUpdateIntervalMs" in source
    assert "kMeetingVersionCheckIntervalMs" in source
    assert "TimedMeetingTaskEntry" in source
    assert "TimedMeetingTask()" in source
    assert "ParseAgendaStartMinutes" in source
    assert "ResolveCurrentAgendaIndex" in source
    assert "ResolveActiveReminderIndex" in source
    assert "ApplyTimedMeetingState" in source


def test_meeting_assistant_uses_clean_low_density_visual_language():
    firmware_ui = read("main/display/pages/meeting_assistant_page_adapter.cc")
    preview = read("tools/ui_preview/render_ui_preview.py")

    assert "BuildPrimaryQrPanel" in firmware_ui
    assert "BuildCleanAgendaPage" in firmware_ui
    assert "BuildKioskQrCard" in firmware_ui
    assert "BuildCleanMaterialsPage" in firmware_ui
    assert "BuildCleanInsightPage" in firmware_ui
    assert "BuildCleanReminderPage" in firmware_ui
    assert "EXEC CONSOLE" not in firmware_ui
    assert "SCAN DESK" not in firmware_ui
    assert "AI CONSOLE" not in firmware_ui
    assert "ALERT DESK" not in firmware_ui
    assert "MEETING PASS" not in firmware_ui
    assert "MakePassStamp" not in firmware_ui
    assert '"PASS"' not in firmware_ui

    assert "primary_qr_panel" in preview
    assert "clean_agenda_page" in preview
    assert "clean_materials_page" in preview
    assert "clean_insight_page" in preview
    assert "clean_reminder_page" in preview
    assert "kiosk_qr_card" in preview
    assert "MEETING PASS" not in preview
    assert "pass_stamp" not in preview
