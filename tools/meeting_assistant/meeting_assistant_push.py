#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import qrcode
    import requests
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError as exc:
    print(
        "Missing dependency: "
        f"{exc.name}. Install with: python3 -m pip install -r tools/meeting_assistant/requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(2)


WIDTH = 400
HEIGHT = 300
API_BASE = "https://cloud.zectrix.com/open/v1"
ROOT = Path(__file__).resolve().parent


@dataclass
class MeetingData:
    title: str
    time: str
    location: str
    agenda: list[str]
    materials_url: str
    questions_url: str
    summary: list[str]
    reminders: list[str]
    reminder_url: str


def load_meeting(path: Path | None) -> MeetingData:
    if path is None:
        return MeetingData(
            title="AI 会议助手",
            time="09:30-11:30",
            location="主论坛 A 厅",
            agenda=[
                "09:30 开场与嘉宾介绍",
                "09:45 主题演讲：AI 与未来办公",
                "10:30 圆桌讨论：智能硬件落地",
                "11:10 互动问答与会后安排",
            ],
            materials_url="https://msh.cn/m",
            questions_url="https://msh.cn/q",
            summary=[
                "本场会议重点关注 AI 会议纪要、个人提醒、资料分发和现场互动。",
                "参会者可以通过二维码获取资料，也可以提交问题进入会后整理。",
                "设备侧优先保证低功耗、清晰二维码和长内容分页可读性。",
            ],
            reminders=[
                "11:30 午餐与自由交流",
                "14:00 分论坛开始，请提前 10 分钟入场",
                "15:30 集体合影，地点在签到墙",
            ],
            reminder_url="https://msh.cn/r",
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    return MeetingData(
        title=data.get("title", "AI 会议助手"),
        time=data.get("time", ""),
        location=data.get("location", ""),
        agenda=list(data.get("agenda", [])),
        materials_url=data.get("materials_url", "https://msh.cn/m"),
        questions_url=data.get("questions_url", "https://msh.cn/q"),
        summary=list(data.get("summary", [])),
        reminders=list(data.get("reminders", [])),
        reminder_url=data.get("reminder_url", "https://msh.cn/r"),
    )


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


FONT_HERO = font(24, bold=True)
FONT_TITLE = font(20, bold=True)
FONT_SUBTITLE = font(15, bold=True)
FONT_BODY = font(15)
FONT_SMALL = font(12)
FONT_TINY = font(10)


def text_width(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.ImageFont) -> float:
    return float(draw.textlength(text, font=face))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        current = ""
        for ch in raw_line:
            candidate = current + ch
            if current and text_width(draw, candidate, face) > max_width:
                lines.append(current)
                current = ch
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def make_canvas(title: str, page: int, total: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("1", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, WIDTH - 1, 34), fill=0)
    draw.text((12, 5), title[:18], fill=255, font=FONT_SUBTITLE)
    draw.text((342, 8), f"{page}/{total}", fill=255, font=FONT_SMALL)
    draw.line((0, 35, WIDTH - 1, 35), fill=0, width=1)
    return img, draw


def draw_section_title(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, width: int = 376) -> None:
    x, y = xy
    draw.rectangle((x, y, x + width, y + 24), fill=0)
    draw.text((x + 8, y + 3), text, fill=255, font=FONT_SUBTITLE)


def draw_list(draw: ImageDraw.ImageDraw, items: Iterable[str], x: int, y: int, width: int, bottom: int) -> int:
    for item in items:
        lines = wrap_text(draw, item, FONT_BODY, width - 26)
        block_h = max(28, len(lines) * 18 + 8)
        if y + block_h > bottom:
            break
        draw.rounded_rectangle((x, y, x + width, y + block_h), radius=2, outline=0, width=1)
        draw.rectangle((x + 8, y + 11, x + 14, y + 17), fill=0)
        ty = y + 5
        for line in lines:
            draw.text((x + 24, ty), line, fill=0, font=FONT_BODY)
            ty += 18
        y += block_h + 7
    return y


def make_qr(payload: str, size: int) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("1")
    return img.resize((size, size), Image.Resampling.NEAREST)


def draw_qr_card(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    xywh: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    payload: str,
) -> None:
    x, y, w, h = xywh
    draw.rounded_rectangle((x, y, x + w, y + h), radius=2, outline=0, width=1)
    draw.rectangle((x + 6, y + 6, x + w - 7, y + 31), fill=0)
    draw.text((x + 12, y + 7), title, fill=255, font=FONT_SMALL)
    draw.text((x + 10, y + 38), subtitle, fill=0, font=FONT_SMALL)
    qr_size = min(w - 28, h - 64)
    qr = make_qr(payload, qr_size)
    img.paste(qr, (x + (w - qr_size) // 2, y + h - qr_size - 10))


def render_pages(meeting: MeetingData, max_pages: int = 5) -> list[Image.Image]:
    pages: list[Image.Image] = []

    img, draw = make_canvas("会议议程", 1, 1)
    title_lines = wrap_text(draw, meeting.title, FONT_HERO, 300)
    title_y = 47
    for line in title_lines[:2]:
        draw.text((12, title_y), line, fill=0, font=FONT_HERO)
        title_y += 27
    draw.rectangle((304, 48, 388, 90), outline=0, width=1)
    draw.text((314, 53), meeting.time[:12], fill=0, font=FONT_SMALL)
    draw.text((314, 70), meeting.location[:10], fill=0, font=FONT_SMALL)
    draw_section_title(draw, (12, 104), "今日安排")
    draw_list(draw, meeting.agenda, 12, 139, 376, 286)
    pages.append(img)

    img, draw = make_canvas("资料与互动", 1, 1)
    draw.text((12, 48), "资料下载与现场互动", fill=0, font=FONT_TITLE)
    draw.text((14, 75), "二维码已按墨水屏高对比度生成，适合手机扫码。", fill=0, font=FONT_SMALL)
    draw_qr_card(img, draw, (14, 101, 176, 174), "会议资料", "PPT / PDF / 附件", meeting.materials_url)
    draw_qr_card(img, draw, (210, 101, 176, 174), "现场提问", "提交问题与反馈", meeting.questions_url)
    pages.append(img)

    summary_chunks = paginate_lines(meeting.summary, max_lines=10, line_width=338)
    for idx, chunk in enumerate(summary_chunks[: max(1, max_pages - 3)]):
        img, draw = make_canvas("AI 会议要点", 1, 1)
        draw_section_title(draw, (12, 50), "自动摘要" if idx == 0 else "自动摘要 续")
        draw_list(draw, chunk, 12, 86, 376, 286)
        pages.append(img)

    img, draw = make_canvas("个人提醒", 1, 1)
    draw_section_title(draw, (12, 50), "后续安排", width=222)
    draw_list(draw, meeting.reminders, 12, 86, 222, 274)
    draw_qr_card(img, draw, (252, 72, 132, 203), "提醒设置", "扫码修改", meeting.reminder_url)
    pages.append(img)

    pages = pages[:max_pages]
    total = len(pages)
    for idx, page in enumerate(pages, start=1):
        draw = ImageDraw.Draw(page)
        draw.rectangle((336, 7, 388, 31), fill=0)
        draw.text((346, 10), f"{idx}/{total}", fill=255, font=FONT_SMALL)
    return pages


def paginate_lines(items: list[str], max_lines: int, line_width: int) -> list[list[str]]:
    scratch = Image.new("1", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(scratch)
    pages: list[list[str]] = []
    current: list[str] = []
    used = 0
    for item in items:
        wrapped = wrap_text(draw, item, FONT_BODY, line_width)
        cost = max(1, len(wrapped))
        if current and used + cost > max_lines:
            pages.append(current)
            current = []
            used = 0
        current.append(item)
        used += cost
    if current:
        pages.append(current)
    return pages or [["暂无会议要点"]]


def save_pages(pages: list[Image.Image], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for idx, page in enumerate(pages, start=1):
        path = out_dir / f"meeting_assistant_{idx}.png"
        page.save(path)
        paths.append(path)
    return paths


def headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key}


def get_devices(api_key: str) -> list[dict]:
    response = requests.get(f"{API_BASE}/devices", headers=headers(api_key), timeout=20)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"API returned error: {payload}")
    return list(payload.get("data", []))


def list_devices(api_key: str) -> None:
    print(json.dumps({"code": 0, "data": get_devices(api_key)}, ensure_ascii=False, indent=2))


def choose_device(api_key: str) -> str:
    devices = get_devices(api_key)
    if not devices:
        raise RuntimeError("No ZecTrix device is bound to this API key.")
    device_id = devices[0].get("deviceId")
    if not device_id:
        raise RuntimeError(f"Device response has no deviceId: {devices[0]}")
    alias = devices[0].get("alias") or "unnamed"
    print(f"auto device: {alias} ({device_id})")
    return device_id


def verify_qr(paths: list[Path]) -> None:
    try:
        import zxingcpp
    except ModuleNotFoundError:
        print("QR verify skipped: install zxing-cpp to enable --verify-qr", file=sys.stderr)
        return
    for path in paths:
        decoded = [result.text for result in zxingcpp.read_barcodes(Image.open(path).convert("RGB"))]
        print(f"qr {path.name}: {decoded}")


def push_images(api_key: str, device_id: str, paths: list[Path], start_page: int, dither: bool) -> None:
    for offset, path in enumerate(paths):
        page_id = str(start_page + offset)
        with path.open("rb") as fp:
            response = requests.post(
                f"{API_BASE}/devices/{device_id}/display/image",
                headers=headers(api_key),
                data={"pageId": page_id, "dither": "false" if not dither else "true"},
                files=[("images", (path.name, fp, "image/png"))],
                timeout=60,
            )
        response.raise_for_status()
        print(f"pushed {path.name} -> page {page_id}: {response.text}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and push ZecTrix meeting assistant pages.")
    parser.add_argument("--input", type=Path, help="Meeting JSON file. Uses a sample meeting when omitted.")
    parser.add_argument("--out", type=Path, default=ROOT / "out", help="Output directory for PNG pages.")
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum image pages to render/push.")
    parser.add_argument("--api-key", default=os.getenv("ZECTRIX_API_KEY"), help="Zectrix Open API key.")
    parser.add_argument("--device-id", default=os.getenv("ZECTRIX_DEVICE_ID"), help="Device MAC address.")
    parser.add_argument("--auto-device", action="store_true", help="Use the first device from the Open API device list.")
    parser.add_argument("--start-page", type=int, default=1, help="First persistent display page slot.")
    parser.add_argument("--no-dither", action="store_true", help="Use hard threshold instead of cloud dithering.")
    parser.add_argument("--list-devices", action="store_true", help="List devices and exit.")
    parser.add_argument("--verify-qr", action="store_true", help="Decode generated QR codes locally when zxing-cpp is installed.")
    parser.add_argument("--push", action="store_true", help="Push rendered pages to the device.")
    args = parser.parse_args()

    if args.list_devices:
        if not args.api_key:
            parser.error("--api-key or ZECTRIX_API_KEY is required")
        list_devices(args.api_key)
        return 0

    meeting = load_meeting(args.input)
    pages = render_pages(meeting, max_pages=args.max_pages)
    paths = save_pages(pages, args.out)
    for path in paths:
        print(path)
    if args.verify_qr:
        verify_qr(paths)

    if args.push:
        if not args.api_key:
            parser.error("--api-key or ZECTRIX_API_KEY is required")
        device_id = args.device_id
        if args.auto_device:
            device_id = choose_device(args.api_key)
        if not device_id:
            parser.error("--device-id, --auto-device, or ZECTRIX_DEVICE_ID is required")
        push_images(args.api_key, device_id, paths, args.start_page, not args.no_dither)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
