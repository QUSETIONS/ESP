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


def pass_stamp(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, title: str, subtitle: str) -> None:
    draw.rectangle((x, y, x + 46, y + 42), fill=0)
    text(draw, (x + 8, y + 14), "PASS", F12, 255)
    box(draw, (x + 46, y, w - 46, 42))
    text(draw, (x + 56, y + 6), fit_text(title, 20), F16)
    text(draw, (x + 56, y + 25), fit_text(subtitle, 25), F12)


def now_block(draw: ImageDraw.ImageDraw, x: int, y: int, h: int, value: str) -> None:
    draw.rectangle((x, y, x + 64, y + h), fill=0)
    text(draw, (x + 19, y + 7), "NOW", F10, 255)
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


def qr_card(img: Image.Image, draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, payload: str) -> None:
    x, y, w, h = xywh
    box(draw, (x, y, w, h))
    draw.rectangle((x + 8, y + 8, x + w - 9, y + 34), fill=0)
    text(draw, (x + 14, y + 11), title, F12, 255)
    text(draw, (x + 10, y + 43), fit_text(subtitle, 13), F12)
    q = qr(payload, min(w - 48, h - 74))
    img.paste(q, (x + (w - q.width) // 2, y + h - q.height - 10))


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
    header(draw, "GoTim ink", "1/4")
    pass_stamp(draw, 10, 42, 380, "MEETING PASS", "会议议程 / 自动跟随时间")
    box(draw, (10, 96, 380, 82))
    now_block(draw, 20, 106, 62, current.get("time", "--:--"))
    multiline(draw, (98, 104), current.get("title", ""), F16, 0, 276, 2, 3)
    meta = " | ".join(part for part in (current.get("speaker", ""), current.get("note", "")) if part)
    text(draw, (98, 154), fit_text(meta, 26), F12)
    for i, item in enumerate(items[current_idx + 1: current_idx + 6]):
        time_row(draw, 22, 192 + i * 28, item.get("time", "--:--"), item.get("title", ""))
    return img


def render_materials(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    materials = data.get("materials", {})
    interaction = data.get("interaction", {})
    header(draw, "GoTim ink", "2/4")
    pass_stamp(draw, 10, 42, 380, "MEETING PASS", "资料与互动 / 扫码继续")
    qr_card(img, draw, (12, 96, 180, 194), "资料下载", materials.get("label", "PPT / PDF"), materials.get("url", "https://msh.cn/m"))
    qr_card(img, draw, (208, 96, 180, 194), "现场提问", interaction.get("label", "提交问题"), interaction.get("url", "https://msh.cn/q"))
    return img


def render_summary(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    summary = data.get("summary", {})
    header(draw, "GoTim ink", "3/4")
    pass_stamp(draw, 10, 42, 380, "AI NOTE", summary.get("title", "09:35 AI 摘要"))
    box(draw, (10, 96, 252, 194))
    text(draw, (20, 106), "核心要点", F16)
    draw.line((20, 134, 250, 134), fill=0)
    y = 146
    for line in summary.get("bullets", [])[:4]:
        lines = wrap_text(draw, line, F12, 224, 2)
        for wrapped in lines:
            text(draw, (20, y), wrapped, F12)
            y += 17
        y += 4
    box(draw, (276, 96, 112, 194))
    band(draw, (284, 104, 94, 25), "关键词")
    text(draw, (284, 144), "\n".join(summary.get("keywords", [])[:5]), F12)
    return img


def render_reminder(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    user = data.get("attendee", {})
    reminder = data.get("reminder", {})
    header(draw, "GoTim ink", "4/4")
    pass_stamp(draw, 10, 42, 380, "PERSONAL PASS", f"{user.get('name', '参会者')} / 个人提醒")
    box(draw, (10, 96, 214, 174))
    active_index = int(data.get("active_reminder_index", -1))
    for i, item in enumerate(reminder.get("items", [])[:3]):
        y = 108 + i * 48
        draw.rectangle((22, y, 76, y + 24), fill=0)
        text(draw, (29, y + 5), item.get("time", "--:--"), F12, 255)
        if i == active_index:
            draw.rectangle((84, y - 2, 212, y + 34), fill=0)
            multiline(draw, (90, y + 2), item.get("title", ""), F15, 255, 116, 2, 2)
        else:
            multiline(draw, (88, y + 2), item.get("title", ""), F15, 0, 122, 2, 2)
        if i < 2:
            draw.line((22, y + 38, 210, y + 38), fill=0)
    qr_card(img, draw, (242, 86, 146, 204), "提醒设置", "扫码修改", reminder.get("url", "https://msh.cn/r"))
    return img


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
        if "materials" in path.name or "reminder" in path.name:
            quiet_samples = [
                img.getpixel((8, 78)),
                img.getpixel((198, 78)),
                img.getpixel((232, 38)),
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
