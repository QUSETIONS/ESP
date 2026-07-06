#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import qrcode
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
DEFAULT_DATA = PROJECT_ROOT / "tools" / "meeting_data" / "meeting_current.json"
OUT = ROOT / "out"
W, H = 400, 300


def load_data(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for item in candidates:
        if item and Path(item).exists():
            return ImageFont.truetype(item, size)
    return ImageFont.load_default()


F10 = font(10)
F12 = font(12)
F14 = font(14)
F15 = font(15)
F16 = font(16)
F18 = font(18, True)
F20 = font(20, True)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("1", (W, H), 255)
    return img, ImageDraw.Draw(img)


def text(draw: ImageDraw.ImageDraw, xy, value: str, fnt=F12, fill=0) -> None:
    draw.text(xy, str(value), font=fnt, fill=fill)


def fit_text(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: max(0, limit - 1)] + "…"


def header(draw: ImageDraw.ImageDraw, title: str, right: str) -> None:
    draw.rectangle((0, 0, W - 1, 31), fill=0)
    text(draw, (12, 5), fit_text(title, 18), F16, 255)
    text(draw, (W - 12 - int(draw.textlength(right, font=F12)), 8), right, F12, 255)


def box(draw: ImageDraw.ImageDraw, xywh, width: int = 1, fill: int | None = None) -> None:
    x, y, w, h = xywh
    draw.rounded_rectangle((x, y, x + w, y + h), radius=2, outline=0, width=width, fill=fill)


def band(draw: ImageDraw.ImageDraw, xywh, title: str) -> None:
    x, y, w, h = xywh
    draw.rectangle((x, y, x + w, y + h), fill=0)
    text(draw, (x + 7, y + 3), fit_text(title, 18), F14, 255)


def time_row(draw: ImageDraw.ImageDraw, x: int, y: int, t: str, title: str, active: bool = False) -> None:
    if active:
        draw.rectangle((x, y, x + 50, y + 22), fill=0)
        text(draw, (x + 7, y + 4), t, F10, 255)
    else:
        box(draw, (x, y, 50, 22))
        text(draw, (x + 7, y + 4), t, F10)
    text(draw, (x + 62, y + 1), fit_text(title, 11), F15)


def selected_row(draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, selected: bool) -> None:
    x, y, w, h = xywh
    box(draw, (x, y, w, h), fill=0 if selected else 255)
    fill = 255 if selected else 0
    text(draw, (x + 10, y + 5), title, F15, fill)
    text(draw, (x + 116, y + 8), fit_text(subtitle, 20), F12, fill)


def qr(payload: str, size: int) -> Image.Image:
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
    code.add_data(payload)
    code.make(fit=True)
    img = code.make_image(fill_color="black", back_color="white").convert("1")
    return img.resize((size, size), Image.Resampling.NEAREST)


def qr_card(img: Image.Image, draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, payload: str) -> None:
    x, y, w, h = xywh
    box(draw, (x, y, w, h))
    draw.rectangle((x + 6, y + 6, x + w - 7, y + 32), fill=0)
    text(draw, (x + 12, y + 9), title, F12, 255)
    text(draw, (x + 8, y + 40), fit_text(subtitle, 13), F12)
    q = qr(payload, min(w - 38, h - 66))
    img.paste(q, (x + (w - q.width) // 2, y + h - q.height - 8))


def agenda_items(data: dict[str, Any]) -> list[dict[str, str]]:
    return list(data.get("agenda", []))


def render_home(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    home = data.get("home", {})
    status = data.get("device_status", {})
    header(draw, home.get("title", "极趣实验室 Note"), home.get("date_label", "07/05 周日"))
    box(draw, (12, 44, 250, 164))
    band(draw, (20, 52, 232, 25), "今日待办")
    for idx, item in enumerate(agenda_items(data)[:4]):
        time_row(draw, 20, 82 + idx * 30, item.get("time", "--:--"), item.get("title", ""), idx == data.get("current_agenda_index", 0))

    box(draw, (274, 44, 114, 72))
    text(draw, (282, 52), home.get("month", "JUL"), F12)
    text(draw, (282, 70), home.get("day", "05"), F20)
    text(draw, (340, 88), home.get("weekday", "周日"), F15)

    box(draw, (274, 128, 114, 80))
    text(draw, (282, 136), status.get("network", "离线"), F15)
    text(draw, (340, 136), status.get("mode", "本地"), F15)
    draw.line((282, 164, 378, 164), fill=0)
    text(draw, (282, 178), "NFC", F12)
    text(draw, (340, 178), status.get("nfc", "Ready"), F12)

    selected_row(draw, (12, 222, 376, 30), "便利贴", "今日待办", True)
    selected_row(draw, (12, 258, 376, 30), "实验室", "会议助手", False)
    return img


def render_lab(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    header(draw, "实验室", "LAB")
    text(draw, (12, 48), "实验功能", F18)
    text(draw, (306, 51), data.get("device_status", {}).get("mode", "本地模式"), F12)
    rows = data.get("lab_features", [])
    for i, row in enumerate(rows[:4]):
        x, y, w, h = 12, 78 + i * 48, 376, 40
        selected = i == 0
        box(draw, (x, y, w, h), fill=0 if selected else 255)
        fill = 255 if selected else 0
        text(draw, (x + 10, y + 9), f"{i + 1:02d}", F12, fill)
        text(draw, (x + 52, y + 5), row.get("title", ""), F15, fill)
        text(draw, (x + 176, y + 9), fit_text(row.get("subtitle", ""), 16), F12, fill)
    return img


def render_agenda(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    current_idx = int(data.get("current_agenda_index", 0))
    items = agenda_items(data)
    current = items[current_idx] if 0 <= current_idx < len(items) else (items[0] if items else {})
    header(draw, "会议议程", "1/4")
    band(draw, (10, 42, 380, 25), "当前议程")
    box(draw, (10, 78, 380, 56))
    draw.rectangle((20, 88, 76, 112), fill=0)
    text(draw, (28, 93), current.get("time", "--:--"), F12, 255)
    text(draw, (88, 87), fit_text(current.get("title", ""), 14), F16)
    meta = " | ".join(part for part in (current.get("speaker", ""), current.get("note", "")) if part)
    text(draw, (88, 112), fit_text(meta, 22), F12)
    for i, item in enumerate(items[current_idx + 1: current_idx + 6]):
        time_row(draw, 22, 148 + i * 30, item.get("time", "--:--"), item.get("title", ""))
    return img


def render_materials(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    materials = data.get("materials", {})
    interaction = data.get("interaction", {})
    header(draw, "会议资料与互动", "2/4")
    band(draw, (10, 44, 380, 26), "资料和互动入口")
    qr_card(img, draw, (12, 84, 180, 186), "资料下载", materials.get("label", "PPT / PDF"), materials.get("url", "https://msh.cn/m"))
    qr_card(img, draw, (208, 84, 180, 186), "现场提问", interaction.get("label", "提交问题"), interaction.get("url", "https://msh.cn/q"))
    return img


def render_summary(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    summary = data.get("summary", {})
    header(draw, "AI 会议要点", "3/4")
    band(draw, (10, 44, 380, 25), summary.get("title", "09:35 AI 摘要"))
    box(draw, (10, 82, 252, 184))
    text(draw, (20, 92), "核心要点", F16)
    draw.line((20, 120, 250, 120), fill=0)
    for i, line in enumerate(summary.get("bullets", [])[:5]):
        text(draw, (20, 132 + i * 22), fit_text(line, 18), F12)
    box(draw, (276, 82, 112, 184))
    band(draw, (284, 90, 94, 25), "关键词")
    text(draw, (284, 130), "\n".join(summary.get("keywords", [])[:5]), F12)
    return img


def render_reminder(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    user = data.get("attendee", {})
    reminder = data.get("reminder", {})
    header(draw, "个人提醒", "4/4")
    band(draw, (10, 44, 214, 28), user.get("name", "参会者"))
    box(draw, (10, 86, 214, 158))
    for i, item in enumerate(reminder.get("items", [])[:3]):
        y = 98 + i * 48
        draw.rectangle((22, y, 76, y + 24), fill=0)
        text(draw, (29, y + 5), item.get("time", "--:--"), F12, 255)
        text(draw, (88, y + 4), fit_text(item.get("title", ""), 8), F15)
        if i < 2:
            draw.line((22, y + 38, 210, y + 38), fill=0)
    qr_card(img, draw, (242, 72, 146, 194), "提醒设置", "扫码修改", reminder.get("url", "https://msh.cn/r"))
    return img


def verify_qr(paths: list[Path]) -> None:
    try:
        import zxingcpp
    except ModuleNotFoundError:
        return
    for path in paths:
        decoded = [item.text for item in zxingcpp.read_barcodes(Image.open(path).convert("RGB"))]
        if decoded:
            print(f"{path.name}: {decoded}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render 400x300 e-paper UI previews from meeting JSON.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--verify-qr", action="store_true")
    args = parser.parse_args()

    data = load_data(args.data)
    args.out.mkdir(parents=True, exist_ok=True)
    pages = {
        "01_home.png": render_home(data),
        "02_lab.png": render_lab(data),
        "03_meeting_agenda.png": render_agenda(data),
        "04_meeting_materials.png": render_materials(data),
        "05_meeting_summary.png": render_summary(data),
        "06_meeting_reminder.png": render_reminder(data),
    }
    paths: list[Path] = []
    for name, img in pages.items():
        path = args.out / name
        img.save(path)
        paths.append(path)
        print(path)
    if args.verify_qr:
        verify_qr(paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
