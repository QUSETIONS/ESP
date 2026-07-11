from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_meeting_json_carries_all_p0_surfaces():
    data = json.loads(read("tools/meeting_data/meeting_current.json"))

    assert data["attendee"]["id"]
    assert data["attendee"]["role"]
    assert data["badge"]["label"] == "会后身份 Badge"
    assert data["live"]["speaker"]
    assert data["live"]["topic"]
    assert data["live"]["remote_update"]
    assert len(data["summary"]["metrics"]) >= 3
    assert len(data["desktop_tasks"]) >= 2
    assert len(data["health_reminders"]) >= 2


def test_firmware_meeting_data_parses_p0_contract():
    header = read("main/meeting/meeting_data.h")
    parser = read("main/meeting/meeting_data.cc")

    for symbol in [
        "MeetingMetricItem",
        "MeetingTaskItem",
        "HealthReminderItem",
        "attendee_id",
        "attendee_role",
        "badge_label",
        "live_speaker",
        "live_topic",
        "remote_update",
        "metrics",
        "desktop_tasks",
        "health_reminders",
    ]:
        assert symbol in header

    for json_key in [
        '"id"',
        '"role"',
        '"badge"',
        '"live"',
        '"remote_update"',
        '"metrics"',
        '"desktop_tasks"',
        '"health_reminders"',
    ]:
        assert json_key in parser


def test_firmware_and_preview_render_p0_pages():
    firmware_ui = read("main/display/pages/meeting_assistant_page_adapter.cc")
    preview = read("tools/ui_preview/render_ui_preview.py")

    for symbol in [
        "BuildLiveBriefingPage",
        "BuildKeyPointsPage",
        "BuildBadgeReminderPage",
        "MakeMetricStrip",
        "MakeIdentityBadge",
        "MakeTaskList",
        "MakeHealthReminderList",
    ]:
        assert symbol in firmware_ui

    for symbol in [
        "live_briefing_page",
        "key_points_page",
        "badge_reminder_page",
        "metric_strip",
        "identity_badge",
        "task_list",
        "health_reminder_list",
    ]:
        assert symbol in preview


def test_server_exposes_fleet_push_endpoint_for_batch_updates():
    server = read("tools/meeting_server/meeting_server.py")
    editor = read("tools/meeting_server/meeting_server.py")

    assert '"/fleet/push"' in server
    assert "saveFleetPush" in editor
    assert "一键推送全部设备" in editor
