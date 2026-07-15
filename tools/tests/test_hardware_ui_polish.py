from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
PREVIEW_DIR = ROOT / "tools" / "ui_preview"
DATA_PATH = ROOT / "tools" / "meeting_data" / "meeting_current.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def render_previews(tmp_path: Path) -> dict[str, Image.Image]:
    render = load_module("render_ui_preview", PREVIEW_DIR / "render_ui_preview.py")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    paths = render.render_pages(data, tmp_path)
    return {path.name: Image.open(path).convert("1") for path in paths}


def is_white(img: Image.Image, xy: tuple[int, int]) -> bool:
    return img.getpixel(xy) != 0


def test_home_and_lab_drop_heavy_outer_boxes(tmp_path: Path):
    pages = render_previews(tmp_path)

    assert is_white(pages["01_home.png"], (38, 40))
    assert is_white(pages["01_home.png"], (386, 292))
    assert is_white(pages["03_lab.png"], (38, 68))
    assert is_white(pages["03_lab.png"], (386, 292))


def test_meeting_pages_use_open_cards_instead_of_full_width_walls(tmp_path: Path):
    pages = render_previews(tmp_path)

    assert is_white(pages["05_meeting_materials.png"], (16, 66))
    assert is_white(pages["05_meeting_materials.png"], (208, 66))
    assert is_white(pages["06_meeting_summary.png"], (380, 259))
    assert is_white(pages["07_meeting_reminder.png"], (232, 66))


def test_summary_keeps_bottom_safe_area_clear(tmp_path: Path):
    summary = render_previews(tmp_path)["06_meeting_summary.png"]

    bottom_safe_area = summary.crop((0, summary.height - 12, summary.width, summary.height))
    assert bottom_safe_area.getextrema() == (255, 255)


def test_all_pages_keep_bottom_safe_area_clear(tmp_path: Path):
    for page in render_previews(tmp_path).values():
        bottom_safe_area = page.crop((0, page.height - 12, page.width, page.height))
        assert bottom_safe_area.getextrema() == (255, 255)


def test_summary_preview_matches_firmware_metric_geometry():
    firmware = (ROOT / "main" / "display" / "pages" / "meeting_assistant_page_adapter.cc").read_text(
        encoding="utf-8"
    )
    preview = (PREVIEW_DIR / "render_ui_preview.py").read_text(encoding="utf-8")

    assert "MakeMetricStrip(content_, kMargin, 184, main_w);" in firmware
    assert "for item in summary.get(\"keywords\", [])[:3]:" not in preview


def test_firmware_exposes_polished_hardware_ui_helpers():
    sources = "\n".join(
        [
            (ROOT / "main" / "display" / "pages" / "sticky_note_home_page_adapter.cc").read_text(encoding="utf-8"),
            (ROOT / "main" / "display" / "pages" / "lab_features_page_adapter.cc").read_text(encoding="utf-8"),
            (ROOT / "main" / "display" / "pages" / "meeting_assistant_page_adapter.cc").read_text(encoding="utf-8"),
            (ROOT / "tools" / "ui_preview" / "render_ui_preview.py").read_text(encoding="utf-8"),
        ]
    )

    assert "StickyNoteHomePageAdapter::BuildDetail" in sources
    assert "MakeLabFeatureStage" in sources
    assert "BuildQrTicket" in sources
    assert "summary_receipt_page" in sources



def test_metric_columns_use_vertical_separators():
    firmware = (ROOT / "main" / "display" / "pages" / "meeting_assistant_page_adapter.cc").read_text(
        encoding="utf-8"
    )
    preview = (PREVIEW_DIR / "render_ui_preview.py").read_text(encoding="utf-8")

    assert "void MakeVerticalRule" in firmware
    assert "MakeVerticalRule(parent, cx - kGap, y + 4, 50);" in firmware
    assert "def vertical_rule" in preview
    assert "vertical_rule(draw, (cx - SP_8, y + 4), h - SP_8)" in preview



def test_meeting_firmware_reserves_fixed_footer_and_safe_bottom():
    firmware = (ROOT / "main" / "display" / "pages" / "meeting_assistant_page_adapter.cc").read_text(
        encoding="utf-8"
    )

    assert "kBottomSafeHeight = 12" in firmware
    assert "lv_obj_set_height(footer_label_, kFooterHeight);" in firmware
    assert "LV_ALIGN_BOTTOM_MID, 0, -kBottomSafeHeight" in firmware
    assert "MakeHealthReminderList(content_, kMargin, 188);" in firmware


def test_meeting_long_text_contract_is_bounded():
    firmware = (ROOT / "main" / "display" / "pages" / "meeting_assistant_page_adapter.cc").read_text(
        encoding="utf-8"
    )

    assert "constexpr lv_coord_t kScrollStep = 44;" in firmware
    assert "summary_bullet_count && i < 5" in firmware
    assert "desktop_task_count && i < 2" in firmware
    assert "desktop_tasks[i].title.c_str()" in firmware
    assert "LV_LABEL_LONG_CLIP" in firmware
    assert "constexpr lv_coord_t kQrCodeSize = 132;" in firmware



def test_badge_identity_uses_one_non_overlapping_metadata_row():
    firmware = (ROOT / "main" / "display" / "pages" / "meeting_assistant_page_adapter.cc").read_text(
        encoding="utf-8"
    )
    preview = (PREVIEW_DIR / "render_ui_preview.py").read_text(encoding="utf-8")

    assert "attendee_name.c_str(), kPad, 38" in firmware
    assert "attendee_name.c_str(), kPad, 38, w - 2 * kPad,\n              &BUILTIN_TEXT_FONT" in firmware
    assert "constexpr int32_t kCompactTextScale = 224;" in firmware
    assert "MakeCompactLabel" in firmware
    assert "lv_obj_set_style_transform_scale(label, kCompactTextScale, 0);" in firmware
    assert "const std::string identity_meta" in firmware
    assert "attendee_role.c_str(), kPad, 64" not in firmware
    assert "attendee_id.c_str(), kPad, 74" not in firmware
    assert 'fit_text(user.get("name", "参会者"), 10), F12' in preview
    assert 'fit_text(item.get("title", ""), 10), F10' in preview
    assert "identity_meta = f" in preview
    assert "y + 74" not in preview

def test_summary_heading_rule_clears_chinese_title_line_height():
    firmware = (ROOT / "main" / "display" / "pages" / "meeting_assistant_page_adapter.cc").read_text(encoding="utf-8")
    preview = (PREVIEW_DIR / "render_ui_preview.py").read_text(encoding="utf-8")

    assert "MakeFilledBlock(main, 0, 28, 54, 4, 0);" in firmware
    assert "MakeWrappedLabel(main, bullets.c_str(), 0, 36" in firmware
    assert "iy + 28" in preview
    assert "y = iy + 36" in preview
