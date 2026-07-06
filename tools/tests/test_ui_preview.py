from __future__ import annotations

import importlib.util
import json
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
        "02_lab.png",
        "03_meeting_agenda.png",
        "04_meeting_materials.png",
        "05_meeting_summary.png",
        "06_meeting_reminder.png",
    ]
    assert all(path.exists() for path in paths)


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
    assert "06_meeting_reminder.png" in html
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


def test_firmware_layout_has_safe_text_and_qr_helpers():
    source = (ROOT / "main" / "display" / "pages" / "meeting_assistant_page_adapter.cc").read_text(encoding="utf-8")

    assert "MakeWrappedLabel" in source
    assert "kQrQuietZone" in source
    assert "LV_LABEL_LONG_WRAP" in source
    assert "LV_SCROLLBAR_MODE_ACTIVE" in source
