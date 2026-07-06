from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_home_uses_low_density_command_desk():
    firmware_ui = read("main/display/pages/sticky_note_home_page_adapter.cc")
    preview = read("tools/ui_preview/render_ui_preview.py")

    assert "MakeHomeHeroCard" in firmware_ui
    assert "MakeDeviceStatusPanel" in firmware_ui
    assert "MakeHomeActionCard" in firmware_ui
    assert "NOTE DESK" in firmware_ui

    assert "home_command_desk" in preview
    assert "home_hero_card" in preview
    assert "device_status_panel" in preview
    assert "home_action_card" in preview


def test_lab_and_meeting_remove_dense_console_language():
    sources = "\n".join(
        [
            read("main/display/pages/lab_features_page_adapter.cc"),
            read("main/display/pages/meeting_assistant_page_adapter.cc"),
            read("tools/ui_preview/render_ui_preview.py"),
        ]
    )

    assert "MakeLabHeroCard" in sources
    assert "MakeSimpleFeatureTile" in sources
    assert "BuildCleanAgendaPage" in sources
    assert "BuildCleanMaterialsPage" in sources
    assert "BuildCleanInsightPage" in sources
    assert "BuildCleanReminderPage" in sources
    assert "clean_agenda_page" in sources
    assert "clean_materials_page" in sources
    assert "clean_insight_page" in sources
    assert "clean_reminder_page" in sources

    assert "CLIENT DEMO" not in sources
    assert "EXEC CONSOLE" not in sources
    assert "SCAN DESK" not in sources
    assert "AI CONSOLE" not in sources
    assert "ALERT DESK" not in sources
