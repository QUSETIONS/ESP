from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_lab_features_page_uses_demo_console_layout():
    firmware_ui = read("main/display/pages/lab_features_page_adapter.cc")
    preview = read("tools/ui_preview/render_ui_preview.py")

    assert "MakeLabConsoleHeader" in firmware_ui
    assert "MakeHeroFeatureCard" in firmware_ui
    assert "MakeCapabilityTile" in firmware_ui
    assert "MakeDemoStatusBar" in firmware_ui
    assert "LAB CONSOLE" in firmware_ui
    assert "CLIENT DEMO" in firmware_ui
    assert "DEMO READY" in firmware_ui

    assert "lab_console" in preview
    assert "hero_feature_card" in preview
    assert "capability_tile" in preview
    assert "demo_status_bar" in preview
    assert "LAB CONSOLE" in preview
    assert "CLIENT DEMO" in preview
