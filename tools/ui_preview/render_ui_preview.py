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


def wrap_text(draw: ImageDraw.ImageDraw, value: str, fnt, max_width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in str(value):
        candidate = current + char
        if draw.textlength(candidate, font=fnt) <= max_width or not current:
            current = candidate
            continue
        lines.append(current)
        current = char
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and draw.textlength(lines[-1], font=fnt) > max_width:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=fnt) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


def multiline(draw: ImageDraw.ImageDraw, xy, value: str, fnt=F12, fill=0, max_width: int = 120,
              max_lines: int = 2, line_gap: int = 4) -> None:
    x, y = xy
    for idx, line in enumerate(wrap_text(draw, value, fnt, max_width, max_lines)):
        text(draw, (x, y + idx * (fnt.size + line_gap)), line, fnt, fill)


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


def status_pill(draw: ImageDraw.ImageDraw, xywh, label: str, inverted: bool = False) -> None:
    x, y, w, h = xywh
    box(draw, (x, y, w, h), fill=0 if inverted else 255)
    fill = 255 if inverted else 0
    visible = fit_text(label, 14)
    text_width = int(draw.textlength(visible, font=F12))
    text(draw, (x + max(4, (w - text_width) // 2), y + 4), visible, F12, fill)


def console_header(draw: ImageDraw.ImageDraw, section: str, title: str, meta: str) -> None:
    status_pill(draw, (10, 42, 92, 22), section, True)
    text(draw, (114, 42), fit_text(title, 18), F18)
    status_pill(draw, (298, 42, 92, 22), meta)
    draw.line((10, 74, 390, 74), fill=0)


def signal_rail(draw: ImageDraw.ImageDraw, x: int, y: int, h: int, active: bool = True) -> None:
    width = 4 if active else 2
    draw.rectangle((x, y, x + width, y + h), fill=0)
    for offset in range(0, max(1, h - 4), 24):
        draw.rectangle((x - 1, y + offset, x + 5, y + offset + 5), fill=0)


def clock_block(draw: ImageDraw.ImageDraw, x: int, y: int, h: int, value: str) -> None:
    draw.rectangle((x, y, x + 74, y + h), fill=0)
    text(draw, (x + 18, y + 7), "ON AIR", F10, 255)
    text(draw, (x + 12, y + h - 24), value, F14, 255)


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


def kiosk_qr_card(img: Image.Image, draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, payload: str) -> None:
    x, y, w, h = xywh
    box(draw, (x, y, w, h))
    draw.rectangle((x + 8, y + 8, x + w - 9, y + 34), fill=0)
    text(draw, (x + 14, y + 11), title, F12, 255)
    text(draw, (x + 10, y + 43), fit_text(subtitle, 13), F12)
    q = qr(payload, min(w - 48, h - 74))
    img.paste(q, (x + (w - q.width) // 2, y + h - q.height - 10))


def primary_qr_panel(img: Image.Image, draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, payload: str) -> None:
    x, y, w, h = xywh
    box(draw, (x, y, w, h))
    draw.rectangle((x + 8, y + 8, x + w - 9, y + 36), fill=0)
    text(draw, (x + 14, y + 12), title, F14, 255)
    text(draw, (x + 12, y + 48), fit_text(subtitle, 16), F12)
    q = qr(payload, min(w - 62, h - 72))
    img.paste(q, (x + (w - q.width) // 2, y + h - q.height - 10))


def keyword_strip(draw: ImageDraw.ImageDraw, keywords: list[str], x: int, y: int) -> None:
    for idx, word in enumerate(keywords[:4]):
        status_pill(draw, (x, y + idx * 28, 86 if idx == 0 else 76, 22), word, idx == 0)


def agenda_items(data: dict[str, Any]) -> list[dict[str, str]]:
    return list(data.get("agenda", []))


def render_home(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    home = data.get("home", {})
    status = data.get("device_status", {})
    header(draw, "NOTE DESK", home.get("date_label", "07/05 周日"))
    home_command_desk(draw, data, status)
    return img


def home_command_desk(draw: ImageDraw.ImageDraw, data: dict[str, Any], status: dict[str, Any]) -> None:
    items = agenda_items(data)
    current_idx = int(data.get("current_agenda_index", 0))
    current = items[current_idx] if 0 <= current_idx < len(items) else (items[0] if items else {})
    next_item = items[current_idx + 1] if current_idx + 1 < len(items) else {}
    home_hero_card(draw, current)
    device_status_panel(draw, data.get("home", {}), status)
    next_title = next_item.get("title", "暂无后续待办")
    next_time = next_item.get("time", "--:--")
    box(draw, (12, 158, 376, 46))
    text(draw, (24, 168), "下一个", F12)
    text(draw, (82, 166), f"{next_time}  {fit_text(next_title, 16)}", F15)
    home_action_card(draw, (12, 220, 182, 62), "便利贴", "今日待办", True)
    home_action_card(draw, (206, 220, 182, 62), "实验室", "会议助手", False)


def home_hero_card(draw: ImageDraw.ImageDraw, item: dict[str, str]) -> None:
    box(draw, (12, 44, 236, 98), fill=0)
    text(draw, (24, 54), "当前待办", F12, 255)
    text(draw, (24, 82), item.get("time", "--:--"), F20, 255)
    multiline(draw, (104, 78), item.get("title", ""), F16, 255, 116, 2, 3)
    text(draw, (24, 122), "确认保留在便利贴模式", F10, 255)


def device_status_panel(draw: ImageDraw.ImageDraw, home: dict[str, Any], status: dict[str, Any]) -> None:
    box(draw, (260, 44, 128, 98))
    text(draw, (272, 54), home.get("month", "JUL"), F12)
    text(draw, (272, 76), home.get("day", "05"), F20)
    text(draw, (334, 84), home.get("weekday", "周日"), F15)
    draw.line((272, 112, 376, 112), fill=0)
    text(draw, (272, 122), fit_text(status.get("network", "离线"), 4), F12)
    text(draw, (330, 122), fit_text(status.get("nfc", "Ready"), 5), F12)


def home_action_card(draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, selected: bool) -> None:
    x, y, w, h = xywh
    box(draw, (x, y, w, h), fill=0 if selected else 255)
    fill = 255 if selected else 0
    text(draw, (x + 12, y + 10), title, F16, fill)
    text(draw, (x + 12, y + 36), subtitle, F12, fill)


def render_lab(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    header(draw, "实验室", "LAB")
    lab_console(draw, data)
    return img


def lab_console(draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
    rows = data.get("lab_features", [])
    if rows:
        lab_hero_card(draw, rows[0], True)
    capability_tile(draw, rows[1] if len(rows) > 1 else {}, 2, (12, 160), False)
    capability_tile(draw, rows[2] if len(rows) > 2 else {}, 3, (206, 160), False)
    box(draw, (12, 240, 376, 42), fill=0)
    text(draw, (24, 252), "设备状态", F12, 255)
    text(draw, (112, 252), "RTC / NFC / 网络", F12, 255)


def lab_hero_card(draw: ImageDraw.ImageDraw, row: dict[str, str], selected: bool) -> None:
    x, y, w, h = 12, 54, 376, 88
    box(draw, (x, y, w, h), fill=0 if selected else 255)
    fill = 255 if selected else 0
    text(draw, (x + 16, y + 12), row.get("title", "会议助手"), F18, fill)
    multiline(draw, (x + 16, y + 44), row.get("subtitle", ""), F12, fill, 220, 2, 2)
    text(draw, (x + 284, y + 18), "确认进入", F12, fill)
    text(draw, (x + 284, y + 46), "AI / QR", F12, fill)


def capability_tile(draw: ImageDraw.ImageDraw, row: dict[str, str], number: int, xy, selected: bool) -> None:
    x, y = xy
    box(draw, (x, y, 182, 64), fill=0 if selected else 255)
    fill = 255 if selected else 0
    text(draw, (x + 12, y + 10), row.get("title", ""), F15, fill)
    text(draw, (x + 12, y + 36), fit_text(row.get("subtitle", ""), 14), F12, fill)


def render_agenda(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    header(draw, "GoTim ink", "1/4")
    clean_agenda_page(draw, data)
    return img


def clean_agenda_page(draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
    current_idx = int(data.get("current_agenda_index", 0))
    items = agenda_items(data)
    current = items[current_idx] if 0 <= current_idx < len(items) else (items[0] if items else {})
    next_item = items[current_idx + 1] if current_idx + 1 < len(items) else {}
    box(draw, (12, 48, 376, 112), fill=0)
    text(draw, (24, 60), "当前议程", F12, 255)
    text(draw, (24, 88), current.get("time", "--:--"), F20, 255)
    multiline(draw, (116, 84), current.get("title", ""), F16, 255, 220, 2, 3)
    meta = " | ".join(part for part in (current.get("speaker", ""), current.get("note", "")) if part)
    text(draw, (24, 136), fit_text(meta, 28), F12, 255)
    box(draw, (12, 176, 376, 54))
    text(draw, (24, 188), "下一个", F12)
    text(draw, (94, 188), f"{next_item.get('time', '--:--')}  {fit_text(next_item.get('title', '暂无'), 15)}", F15)
    text(draw, (24, 250), "向下滚动查看更多议程", F12)


def render_materials(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    materials = data.get("materials", {})
    interaction = data.get("interaction", {})
    header(draw, "GoTim ink", "2/4")
    clean_materials_page(img, draw, materials, interaction)
    return img


def clean_materials_page(img: Image.Image, draw: ImageDraw.ImageDraw, materials: dict[str, Any], interaction: dict[str, Any]) -> None:
    primary_qr_panel(img, draw, (12, 48, 210, 210), "资料下载", materials.get("label", "PPT / PDF"), materials.get("url", "https://msh.cn/m"))
    kiosk_qr_card(img, draw, (242, 72, 146, 162), "现场提问", interaction.get("label", "提交问题"), interaction.get("url", "https://msh.cn/q"))
    text(draw, (18, 276), "左侧下载材料，右侧提交问题", F12)


def render_summary(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    summary = data.get("summary", {})
    header(draw, "GoTim ink", "3/4")
    clean_insight_page(draw, summary)
    return img


def clean_insight_page(draw: ImageDraw.ImageDraw, summary: dict[str, Any]) -> None:
    box(draw, (12, 48, 376, 164))
    text(draw, (24, 60), summary.get("title", "AI 摘要"), F12)
    draw.line((24, 88, 376, 88), fill=0)
    y = 100
    for line in summary.get("bullets", [])[:4]:
        lines = wrap_text(draw, line, F12, 330, 1)
        for wrapped in lines:
            text(draw, (24, y), wrapped, F12)
            y += 17
    box(draw, (12, 228, 376, 46), fill=0)
    text(draw, (24, 240), "关键词", F12, 255)
    text(draw, (98, 240), " / ".join(summary.get("keywords", [])[:3]), F12, 255)


def render_reminder(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    user = data.get("attendee", {})
    reminder = data.get("reminder", {})
    header(draw, "GoTim ink", "4/4")
    clean_reminder_page(img, draw, user, reminder, int(data.get("active_reminder_index", -1)))
    return img


def clean_reminder_page(img: Image.Image, draw: ImageDraw.ImageDraw, user: dict[str, Any], reminder: dict[str, Any], active_index: int) -> None:
    box(draw, (12, 48, 220, 176))
    text(draw, (24, 60), f"{user.get('name', '参会者')} 的提醒", F12)
    draw.line((24, 86, 218, 86), fill=0)
    for i, item in enumerate(reminder.get("items", [])[:3]):
        y = 100 + i * 36
        draw.rectangle((22, y, 76, y + 24), fill=0)
        text(draw, (29, y + 5), item.get("time", "--:--"), F12, 255)
        if i == active_index:
            draw.rectangle((84, y - 2, 218, y + 28), fill=0)
            text(draw, (92, y + 4), fit_text(item.get("title", ""), 8), F15, 255)
        else:
            text(draw, (92, y + 4), fit_text(item.get("title", ""), 8), F15)
    kiosk_qr_card(img, draw, (250, 68, 138, 166), "提醒设置", "扫码修改", reminder.get("url", "https://msh.cn/r"))
    text(draw, (18, 276), "到点自动高亮，可滚动查看更多", F12)


def render_pages(data: dict[str, Any], out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
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
        path = out / name
        img.save(path)
        paths.append(path)
    return paths


def check_layout(paths: list[Path]) -> list[str]:
    warnings: list[str] = []
    for path in paths:
        img = Image.open(path).convert("1")
        if img.size != (W, H):
            warnings.append(f"{path.name}: expected {W}x{H}, got {img.width}x{img.height}")
            continue

        # Catch accidental drawing outside the intended e-paper safe area.
        border_pixels = 0
        for x in range(W):
            border_pixels += img.getpixel((x, 0)) == 0
            border_pixels += img.getpixel((x, H - 1)) == 0
        for y in range(H):
            border_pixels += img.getpixel((0, y)) == 0
            border_pixels += img.getpixel((W - 1, y)) == 0
        if border_pixels > W + H:
            warnings.append(f"{path.name}: excessive black pixels on outer edge")

        # QR pages need a quiet white margin around the cards, or phone scanning gets flaky.
        if "materials" in path.name:
            quiet_samples = [
                img.getpixel((8, 78)),
                img.getpixel((232, 78)),
                img.getpixel((232, 38)),
                img.getpixel((392, 38)),
            ]
            if any(pixel == 0 for pixel in quiet_samples):
                warnings.append(f"{path.name}: QR quiet-zone guard samples are not white")
        if "reminder" in path.name:
            quiet_samples = [
                img.getpixel((8, 78)),
                img.getpixel((238, 78)),
                img.getpixel((238, 38)),
                img.getpixel((392, 38)),
            ]
            if any(pixel == 0 for pixel in quiet_samples):
                warnings.append(f"{path.name}: QR quiet-zone guard samples are not white")
    return warnings


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
    parser.add_argument("--check-layout", action="store_true")
    args = parser.parse_args()

    data = load_data(args.data)
    paths = render_pages(data, args.out)
    for path in paths:
        print(path)
    if args.verify_qr:
        verify_qr(paths)
    if args.check_layout:
        warnings = check_layout(paths)
        for warning in warnings:
            print(f"layout: {warning}")
        if warnings:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
