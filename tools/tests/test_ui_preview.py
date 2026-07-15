from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREVIEW_DIR = ROOT / "tools" / "ui_preview"
DATA_PATH = ROOT / "tools" / "meeting_data" / "meeting_current.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_render_pages_exposes_preview_contract(tmp_path: Path):
    render = load_module("render_ui_preview", PREVIEW_DIR / "render_ui_preview.py")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    paths = render.render_pages(data, tmp_path)

    assert [path.name for path in paths] == [
        "01_home.png",
        "02_note_detail.png",
        "03_lab.png",
        "04_meeting_agenda.png",
        "05_meeting_materials.png",
        "06_meeting_summary.png",
        "07_meeting_reminder.png",
    ]
    assert all(path.exists() for path in paths)
    assert render.W == 400
    assert render.H == 300
    assert render.BOTTOM_SAFE_H == 12

    from PIL import Image

    assert all(Image.open(path).size == (400, 300) for path in paths)


def test_layout_check_accepts_generated_pages(tmp_path: Path):
    render = load_module("render_ui_preview", PREVIEW_DIR / "render_ui_preview.py")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    paths = render.render_pages(data, tmp_path)

    warnings = render.check_layout(paths)

    assert warnings == []


def test_preview_server_html_contains_phone_visible_gallery(tmp_path: Path):
    render = load_module("render_ui_preview", PREVIEW_DIR / "render_ui_preview.py")
    server = load_module("serve_ui_preview", PREVIEW_DIR / "serve_ui_preview.py")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    paths = render.render_pages(data, tmp_path)

    html = server.build_gallery_html(paths, host="0.0.0.0", port=8790)

    assert "GoTim Ink UI Preview" in html
    assert "400 x 300" in html
    assert "01_home.png" in html
    assert "02_note_detail.png" in html
    assert "07_meeting_reminder.png" in html
    assert "手机访问" in html


def test_preview_long_text_dataset_keeps_safe_layout(tmp_path: Path):
    render = load_module("render_ui_preview", PREVIEW_DIR / "render_ui_preview.py")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    data["agenda"][0]["title"] = "生态环境产业协同创新发展规划审议与跨区域重点项目资金安排说明"
    data["agenda"][0]["speaker"] = "孙晓华主席 / 张军秘书长 / 外部专家代表"
    data["summary"]["bullets"] = [
        "本阶段需要把会议议程、资料入口、现场问题和个人提醒合并成一个低干扰的信息面板。",
        "设备端只展示关键结论，完整纪要和附件通过二维码或手机端继续查看，避免墨水屏塞满文字。",
        "当会议进程变化时，手机客户端或后台应能同步刷新当前议程、下一项安排和提醒时间。",
        "长文本必须进入滚动区域，不能压到边框，也不能遮挡二维码静区。",
    ]
    data["reminder"]["items"][0]["title"] = "午餐与嘉宾闭门交流地点确认"

    paths = render.render_pages(data, tmp_path)
    warnings = render.check_layout(paths)

    assert warnings == []


def test_home_preview_maps_notes_and_has_safe_empty_state():
    render = load_module("render_ui_preview", PREVIEW_DIR / "render_ui_preview.py")

    notes = [
        {"title": "长正文便签", "body": "第一段\n" + "会议内容 " * 80, "remind_at": "09:30"},
        {"title": "下一项", "body": "第二条", "remind_at": "10:30"},
    ]
    assert render.home_note_items({"notes": notes}) == notes
    assert render.home_note_items({"notes": []}) == []
    assert render.home_note_items({"agenda": [{"time": "09:30", "title": "议程"}]})[0]["title"] == "议程"


def test_home_preview_geometry_matches_firmware_focus_desk():
    preview = (PREVIEW_DIR / "render_ui_preview.py").read_text(encoding="utf-8")

    assert "HOME_FOCUS_TOP = 74" in preview
    assert "HOME_FOCUS_H = 118" in preview
    assert "HOME_QUEUE_TOP = 202" in preview
    assert "HOME_FOOTER_TOP = 250" in preview
    assert "\"上下选择 · 确认查看\"" in preview
    assert '"暂无便签"' in preview
    assert '"手机编辑后同步到设备"' in preview


def test_note_detail_preview_has_fixed_reading_viewport(tmp_path: Path):
    render = load_module("render_ui_preview_detail", PREVIEW_DIR / "render_ui_preview.py")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    data["notes"] = [{
        "title": "跨区域重点项目复盘与下一阶段安排",
        "body": "第一段\n" + "这是一段用于验证详情页滚动、裁剪和底部操作栏互不覆盖的长正文。" * 20,
        "remind_at": "09:30",
        "completed": False,
    }]

    paths = render.render_pages(data, tmp_path)

    assert (tmp_path / "02_note_detail.png") in paths
    assert render.DETAIL_BODY_TOP == 116
    assert render.DETAIL_BODY_VIEWPORT_H == 124
    assert render.DETAIL_FOOTER_TOP == 248
    assert render.check_layout(paths) == []


def test_firmware_layout_has_safe_text_and_qr_helpers():
    source = (ROOT / "main" / "display" / "pages" / "meeting_assistant_page_adapter.cc").read_text(encoding="utf-8")
    preview = (ROOT / "tools" / "ui_preview" / "render_ui_preview.py").read_text(encoding="utf-8")

    assert "MakeWrappedLabel" in source
    assert "constexpr lv_coord_t kQrQuietZone = 12;" in source
    assert "kTextSafePad" in source
    assert "LV_LABEL_LONG_WRAP" in source
    assert "LV_SCROLLBAR_MODE_ACTIVE" in source
    assert "QR_QUIET_ZONE = 12" in preview
    assert "TEXT_SAFE_PAD = 16" in preview
    assert "decode_qr_payloads" in preview


def test_qr_pages_decode_all_visible_payloads(tmp_path: Path):
    render = load_module("render_ui_preview", PREVIEW_DIR / "render_ui_preview.py")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    paths = render.render_pages(data, tmp_path)

    decoded_by_page = {
        path.name: set(render.decode_qr_payloads(path))
        for path in paths
        if "materials" in path.name or "reminder" in path.name
    }

    assert decoded_by_page["05_meeting_materials.png"] == {
        data["materials"]["url"],
        data["interaction"]["url"],
    }
    assert decoded_by_page["07_meeting_reminder.png"] == {data["reminder"]["url"]}


def test_qr_pages_use_large_scan_targets(tmp_path: Path):
    render = load_module("render_ui_preview", PREVIEW_DIR / "render_ui_preview.py")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    paths = render.render_pages(data, tmp_path)

    decoded_by_text = {}
    for path in paths:
        if "materials" not in path.name and "reminder" not in path.name:
            continue
        for item in render.decode_qr_items(path):
            pos = item.position
            width = math.dist((pos.top_left.x, pos.top_left.y), (pos.top_right.x, pos.top_right.y))
            height = math.dist((pos.top_left.x, pos.top_left.y), (pos.bottom_left.x, pos.bottom_left.y))
            decoded_by_text[item.text] = min(width, height)

    assert decoded_by_text[data["materials"]["url"]] >= 118
    assert decoded_by_text[data["interaction"]["url"]] >= 118
    assert decoded_by_text[data["reminder"]["url"]] >= 118
