from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_lab_features_page_uses_low_density_lab_layout():
    firmware_ui = read("main/display/pages/lab_features_page_adapter.cc")
    preview = read("tools/ui_preview/render_ui_preview.py")

    assert "MakeLabConsoleHeader" in firmware_ui
    assert "MakeLabHeroCard" in firmware_ui
    assert "MakeSimpleFeatureTile" in firmware_ui
    assert "CLIENT DEMO" not in firmware_ui
    assert "DEMO READY" not in firmware_ui

    assert "lab_console" in preview
    assert "lab_hero_card" in preview
    assert "capability_tile" in preview
    assert "CLIENT DEMO" not in preview
