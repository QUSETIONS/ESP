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


def test_frontend_uses_sticky_note_and_plugin_drawer_language():
    firmware_home = read("main/display/pages/sticky_note_home_page_adapter.cc")
    firmware_lab = read("main/display/pages/lab_features_page_adapter.cc")
    firmware_meeting = read("main/display/pages/meeting_assistant_page_adapter.cc")
    preview = read("tools/ui_preview/render_ui_preview.py")

    assert "home_binder_rail" in preview
    assert "home_sticky_surface" in preview
    assert "MakeHomeBinderRail" in firmware_home
    assert "MakeHomeStickySurface" in firmware_home

    assert "lab_plugin_drawer" in preview
    assert "MakeLabPluginDrawer" in firmware_lab
    assert "MakeDrawerFeatureRow" in firmware_lab

    assert "meeting_scroll_canvas" in preview
    assert "BuildScrollCanvas" in firmware_meeting
    assert "kScrollableContentHeight" in firmware_meeting



def test_home_and_lab_share_named_ui_system_primitives():
    firmware_home = read("main/display/pages/sticky_note_home_page_adapter.cc")
    firmware_lab = read("main/display/pages/lab_features_page_adapter.cc")
    preview = read("tools/ui_preview/render_ui_preview.py")

    assert "MakeBindingRail" in firmware_home
    assert "MakeCurrentNoteStage" in firmware_home
    assert "MakeLabToolDrawer" in firmware_lab
    assert "make_binding_rail" in preview
    assert "current_note_stage" in preview
    assert "lab_tool_drawer" in preview


def test_firmware_home_rail_respects_bottom_safety_area():
    firmware_home = read("main/display/pages/sticky_note_home_page_adapter.cc")

    assert "kBottomSafeHeight = 12" in firmware_home
    assert "kPageHeight - kBottomSafeHeight - y" in firmware_home
