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
BOTTOM_SAFE_H = 12

# 4px spacing grid: 4 / 8 / 12 / 16 / 20 / 24 / 32
SP_4, SP_8, SP_12, SP_16, SP_20, SP_24, SP_32 = 4, 8, 12, 16, 20, 24, 32

# Safe-area margins (keep e-paper edges clean)
MARGIN = 12
HEADER_H = 32
TEXT_SAFE_PAD = 16
QR_QUIET_ZONE = 12
QR_CARD_W = 176
QR_CARD_H = 220
QR_CODE_SIZE = 132

# Keep the browser preview aligned with the firmware's sticky-note list/detail views.
HOME_FOCUS_TOP = 74
HOME_FOCUS_H = 118
HOME_QUEUE_TOP = 202
HOME_FOOTER_TOP = 250
DETAIL_BODY_TOP = 116
DETAIL_BODY_VIEWPORT_H = 124
DETAIL_FOOTER_TOP = 248


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


# Type scale: header 18, section 14, body 12, note 10
F10 = font(10)
F12 = font(12)
F14 = font(14)
F16 = font(16)
F18 = font(18, True)
F20 = font(20, True)
F22 = font(22, True)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("1", (W, H), 255)
    return img, ImageDraw.Draw(img)


def text(draw: ImageDraw.ImageDraw, xy, value: str, fnt=F12, fill=0) -> None:
    draw.text(xy, str(value), font=fnt, fill=fill)


def wrap_text(draw: ImageDraw.ImageDraw, value: str, fnt, max_width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    truncated = False
    for char in str(value):
        if char == "\n":
            lines.append(current or " ")
            current = ""
            if len(lines) >= max_lines:
                truncated = True
                break
            continue
        candidate = current + char
        if draw.textlength(candidate, font=fnt) <= max_width or not current:
            current = candidate
            continue
        lines.append(current)
        current = char
        if len(lines) >= max_lines:
            truncated = True
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if truncated and lines:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=fnt) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


def multiline(draw: ImageDraw.ImageDraw, xy, value: str, fnt=F12, fill=0, max_width: int = 120,
              max_lines: int = 2, line_gap: int = 4) -> int:
    """Render wrapped text, return total height consumed."""
    x, y = xy
    line_h = fnt.size + line_gap
    lines = wrap_text(draw, value, fnt, max_width, max_lines)
    for idx, line in enumerate(lines):
        text(draw, (x, y + idx * line_h), line, fnt, fill)
    return len(lines) * line_h


def fit_text(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: max(0, limit - 1)] + "…"


# ---------------------------------------------------------------------------
# Layout primitives — emphasis via fill blocks and whitespace, not thin lines.
# ---------------------------------------------------------------------------

def header(draw: ImageDraw.ImageDraw, title: str, right: str) -> None:
    """Filled page header band. Title left, meta right, both reversed on black."""
    draw.rectangle((0, 0, W - 1, HEADER_H - 1), fill=0)
    text(draw, (TEXT_SAFE_PAD, (HEADER_H - F18.size) // 2), fit_text(title, 18), F18, 255)
    rx = W - TEXT_SAFE_PAD - int(draw.textlength(right, font=F12))
    text(draw, (rx, (HEADER_H - F12.size) // 2 + 1), right, F12, 255)


def filled_block(draw: ImageDraw.ImageDraw, xywh) -> None:
    """Solid black rectangle — the primary emphasis device on monochrome e-paper."""
    x, y, w, h = xywh
    draw.rectangle((x, y, x + w - 1, y + h - 1), fill=0)


def soft_card(draw: ImageDraw.ImageDraw, xywh) -> None:
    """Whitespace card with no border — used for non-emphasized content sections."""
    # Deliberately draws nothing; kept as a hook for parity with firmware.
    _ = (draw, xywh)


def section_label(draw: ImageDraw.ImageDraw, xy, label: str, fill=0) -> None:
    """Small caps-style section heading."""
    x, y = xy
    text(draw, (x, y), label, F12, fill)


def status_pill(draw: ImageDraw.ImageDraw, xywh, label: str, inverted: bool = False) -> None:
    x, y, w, h = xywh
    if inverted:
        filled_block(draw, (x, y, w, h))
    fill = 255 if inverted else 0
    visible = fit_text(label, 14)
    tw = int(draw.textlength(visible, font=F12))
    text(draw, (x + max(SP_4, (w - tw) // 2), y + (h - F12.size) // 2), visible, F12, fill)


def thin_rule(draw: ImageDraw.ImageDraw, xy, w: int, fill=0) -> None:
    """A single 1px rule — used sparingly inside filled blocks only."""
    x, y = xy
    draw.line((x, y, x + w - 1, y), fill=fill)


def vertical_rule(draw: ImageDraw.ImageDraw, xy, h: int, fill=0) -> None:
    x, y = xy
    draw.line((x, y, x, y + h - 1), fill=fill)


def dotted_rule(draw: ImageDraw.ImageDraw, xy, w: int, fill=0, step: int = 6) -> None:
    x, y = xy
    for px in range(x, x + w, step):
        draw.line((px, y, min(px + 2, x + w - 1), y), fill=fill)


def time_pill(draw: ImageDraw.ImageDraw, xywh, value: str, active: bool) -> None:
    """Time label pill: filled when active, plain text otherwise."""
    x, y, w, h = xywh
    if active:
        filled_block(draw, (x, y, w, h))
        fill = 255
    else:
        fill = 0
    text(draw, (x + SP_8, y + (h - F12.size) // 2), value, F12, fill)


def qr(payload: str, max_size: int) -> Image.Image:
    probe = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=0)
    probe.add_data(payload)
    probe.make(fit=True)
    box_size = max(1, max_size // probe.modules_count)
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=0)
    code.add_data(payload)
    code.make(fit=True)
    return code.make_image(fill_color="black", back_color="white").convert("1")


def qr_panel(img: Image.Image, draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, payload: str,
             qr_size: int, title_font=F14) -> None:
    """Open QR ticket with text safe padding and a scan-friendly quiet zone."""
    x, y, w, h = xywh
    filled_block(draw, (x + SP_4, y + SP_8, 24, 4))

    label_x = x + SP_12
    text(draw, (label_x, y + 10), fit_text(title, 12), title_font, 0)
    text(draw, (label_x, y + 34), fit_text(subtitle, 16), F10, 0)

    q_size = min(qr_size, w - 2 * QR_QUIET_ZONE, h - 64 - 2 * QR_QUIET_ZONE)
    q = qr(payload, q_size)
    outer_w = q.width + 2 * QR_QUIET_ZONE
    outer_x = x + (w - outer_w) // 2
    outer_y = y + h - outer_w - QR_QUIET_ZONE
    draw.rectangle((outer_x, outer_y, outer_x + outer_w - 1, outer_y + outer_w - 1), fill=255)
    img.paste(q, (outer_x + QR_QUIET_ZONE, outer_y + QR_QUIET_ZONE))


def kiosk_qr_card(img: Image.Image, draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, payload: str) -> None:
    """Small QR card: side-rail title + centered QR with a generous quiet zone."""
    qr_panel(img, draw, xywh, title, subtitle, payload, QR_CODE_SIZE, F12)


def primary_qr_panel(img: Image.Image, draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, payload: str) -> None:
    """Large QR panel: same card grammar as small QR, with a larger code."""
    qr_panel(img, draw, xywh, title, subtitle, payload, QR_CODE_SIZE, F14)


def BuildQrTicket(img: Image.Image, draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, payload: str,
                  qr_size: int = QR_CODE_SIZE, title_font=F14) -> None:
    """Name kept in sync with firmware helper."""
    qr_panel(img, draw, xywh, title, subtitle, payload, qr_size, title_font)


def agenda_items(data: dict[str, Any]) -> list[dict[str, str]]:
    return list(data.get("agenda", []))


def home_note_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return device-shaped notes while keeping agenda fixtures backward compatible."""
    raw_notes = data.get("notes")
    if isinstance(raw_notes, list):
        return [item for item in raw_notes if isinstance(item, dict)]

    notes: list[dict[str, Any]] = []
    for item in agenda_items(data):
        meta = " / ".join(part for part in (item.get("speaker", ""), item.get("note", "")) if part)
        notes.append({
            "title": item.get("title", ""),
            "body": meta or "便利贴模式保留原功能",
            "remind_at": item.get("time", ""),
        })
    return notes


# ===========================================================================
# Page 1 — Home / NOTE DESK
# ===========================================================================

def render_home(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    home = data.get("home", {})
    status = data.get("device_status", {})
    header(draw, "极趣实验室 / 便利贴", home.get("date_label", "07/05 周日"))
    home_sticky_surface(draw, data, status)
    return img


def selected_note(data: dict[str, Any]) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    items = home_note_items(data)
    selected = int(data.get("selected_note_index", data.get("current_agenda_index", 0)))
    if not items:
        return items, 0, {}
    selected = max(0, min(selected, len(items) - 1))
    return items, selected, items[selected]


def make_binding_rail(draw: ImageDraw.ImageDraw) -> None:
    """Three-hole binder rail: a subtle sticky-note signature instead of a large black card."""
    x, y = MARGIN, HEADER_H + SP_12
    h = H - BOTTOM_SAFE_H - y - 1
    draw.line((x + 10, y, x + 10, y + h), fill=0, width=2)
    for cy in (y + 34, y + 100, y + 166):
        draw.ellipse((x + 3, cy - 5, x + 13, cy + 5), outline=0, width=2)



def home_binder_rail(draw: ImageDraw.ImageDraw) -> None:
    make_binding_rail(draw)

def home_sticky_surface(draw: ImageDraw.ImageDraw, data: dict[str, Any], status: dict[str, Any]) -> None:
    current_note_stage(draw, data, status)


def current_note_stage(draw: ImageDraw.ImageDraw, data: dict[str, Any], status: dict[str, Any]) -> None:
    """Focus Desk: one active task, two quiet queue items, fixed command footer."""
    items, selected, item = selected_note(data)
    text(draw, (16, 45), "今日待办", F18)
    count_label = f"{len(items)} 项"
    text(draw, (384 - int(draw.textlength(count_label, font=F12)), 48), count_label, F12)
    draw.rectangle((16, 68, 383, 69), fill=0)

    filled_block(draw, (16, HOME_FOCUS_TOP, 368, HOME_FOCUS_H))
    if item:
        reminder = item.get("remind_at", "") or "现在"
        title_value = item.get("title", "") or "无标题"
        body_value = "已完成 · 确认查看详情" if item.get("completed", False) else (
            item.get("body", "") or "无内容 · 确认查看详情"
        )
        text(draw, (30, 84), fit_text(f"NOW · {reminder}", 22), F12, 255)
        text(draw, (30, 110), fit_text(title_value, 22), F20, 255)
        text(draw, (30, 148), fit_text(body_value.replace("\n", " "), 40), F12, 255)
        text(draw, (350, 116), "›", F22, 255)
    else:
        text(draw, (30, 84), "NOW · --:--", F12, 255)
        text(draw, (30, 110), "暂无便签", F20, 255)
        text(draw, (30, 148), "手机编辑后同步到设备", F12, 255)

    for slot in range(2):
        x = 16 + slot * 184
        if slot == 1:
            draw.line((199, HOME_QUEUE_TOP, 199, HOME_QUEUE_TOP + 39), fill=0)
        if len(items) <= slot + 1:
            continue
        queued = items[(selected + slot + 1) % len(items)]
        text(draw, (x + 10, HOME_QUEUE_TOP + 5),
             fit_text(queued.get("remind_at", "") or "现在", 7), F10)
        text(draw, (x + 64, HOME_QUEUE_TOP + 5),
             fit_text(queued.get("title", "") or "无标题", 11), F12)

    draw.line((16, HOME_FOOTER_TOP, 383, HOME_FOOTER_TOP), fill=0)
    text(draw, (16, 256), "上下选择 · 确认查看", F10)
    lab_hint = "长按 · 实验室"
    text(draw, (384 - int(draw.textlength(lab_hint, font=F10)), 256), lab_hint, F10)
    status_text = " · ".join((
        str(status.get("network", "离线")),
        str(status.get("mode", "本地模式")),
        str(status.get("nfc", "NFC READY")),
    ))
    text(draw, (16, 274), fit_text(status_text, 38), F10)

def home_task_row(draw: ImageDraw.ImageDraw, xywh, reminder: str, title: str,
                  body: str, selected: bool) -> None:
    x, y, w, h = xywh
    if selected:
        filled_block(draw, xywh)
        fill = 255
    else:
        draw.rectangle((x, y, x + w - 1, y + h - 1), outline=0, width=1)
        fill = 0
    text(draw, (x + 10, y + 8), fit_text(reminder, 8), F10, fill)
    text(draw, (x + 74, y + 5), fit_text(title, 22), F14, fill)
    text(draw, (x + 74, y + 25), fit_text(body.replace("\n", " "), 34), F10, fill)



def note_paper_surface(draw: ImageDraw.ImageDraw, data: dict[str, Any], status: dict[str, Any]) -> None:
    current_note_stage(draw, data, status)

def home_command_desk(draw: ImageDraw.ImageDraw, data: dict[str, Any], status: dict[str, Any]) -> None:
    make_binding_rail(draw)
    home_sticky_surface(draw, data, status)


def home_hero_card(draw: ImageDraw.ImageDraw, item: dict[str, str]) -> None:
    _ = (draw, item)


def device_status_panel(draw: ImageDraw.ImageDraw, home: dict[str, Any], status: dict[str, Any]) -> None:
    _ = (draw, home, status)


def home_status_line(draw: ImageDraw.ImageDraw, xywh, home: dict[str, Any], status: dict[str, Any]) -> None:
    x, y, w, h = xywh
    text(draw, (x, y), f"{home.get('month', 'JUL')} {home.get('day', '05')} {home.get('weekday', '周日')}", F14)
    text(draw, (x + 170, y + 1), fit_text(status.get("network", "离线"), 5), F12)
    text(draw, (x + 218, y + 1), fit_text(status.get("mode", "本地"), 5), F12)
    text(draw, (x + 266, y + 1), fit_text(status.get("nfc", "Ready"), 5), F12)


def home_action_card(draw: ImageDraw.ImageDraw, xywh, title: str, subtitle: str, selected: bool) -> None:
    x, y, w, h = xywh
    if selected:
        filled_block(draw, (x, y, w, h))
        fill = 255
    else:
        soft_card(draw, (x, y, w, h))
        # Subtle outline only on unselected, so the selected one reads as emphasized
        draw.rectangle((x, y, x + w - 1, y + h - 1), outline=0, width=1)
        fill = 0
    text(draw, (x + SP_12, y + 7), title, F12, fill)
    subtitle_x = x + w - SP_12 - int(draw.textlength(subtitle, font=F10))
    text(draw, (subtitle_x, y + 11), subtitle, F10, fill)


def render_note_detail(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    items, selected, item = selected_note(data)
    position = f"{selected + 1}/{len(items)}" if items else "0/0"
    header(draw, "便签详情", position)
    make_binding_rail(draw)

    completed = bool(item.get("completed", False))
    filled_block(draw, (52, 46, 72, 24))
    state = "已完成" if completed else "待完成"
    state_x = 52 + (72 - int(draw.textlength(state, font=F12))) // 2
    text(draw, (state_x, 51), state, F12, 255)
    reminder = item.get("remind_at", "") or "未设置"
    text(draw, (138, 51), f"提醒  {fit_text(reminder, 12)}", F12)

    multiline(draw, (52, 76), item.get("title", "") or "无标题", F18, 0, 330, 2, 2)
    thin_rule(draw, (52, 110), 330)

    body = item.get("body", "") or "无内容"
    max_lines = max(1, DETAIL_BODY_VIEWPORT_H // (F12.size + SP_4))
    body_lines = wrap_text(draw, body, F12, 306, 100)
    for index, line in enumerate(body_lines[:max_lines]):
        text(draw, (52, DETAIL_BODY_TOP + index * (F12.size + SP_4)), line, F12)

    draw.rectangle((374, DETAIL_BODY_TOP, 379,
                    DETAIL_BODY_TOP + DETAIL_BODY_VIEWPORT_H - 1), outline=0, width=1)
    total_h = max(DETAIL_BODY_VIEWPORT_H, len(body_lines) * (F12.size + SP_4))
    thumb_h = max(20, (DETAIL_BODY_VIEWPORT_H - 2) * DETAIL_BODY_VIEWPORT_H // total_h)
    filled_block(draw, (375, DETAIL_BODY_TOP + 1, 4, thumb_h))

    filled_block(draw, (52, DETAIL_FOOTER_TOP, 330, 40))
    text(draw, (64, DETAIL_FOOTER_TOP + 11), "确认  切换完成", F12, 255)
    back = "长按  返回列表"
    back_x = 370 - int(draw.textlength(back, font=F12))
    text(draw, (back_x, DETAIL_FOOTER_TOP + 11), back, F12, 255)
    return img


# ===========================================================================
# Page 2 — Lab
# ===========================================================================

def render_lab(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    header(draw, "实验室", "LAB")
    lab_plugin_drawer(draw, data)
    return img


def lab_console(draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
    lab_plugin_drawer(draw, data)


def lab_plugin_drawer(draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
    lab_tool_drawer(draw, data)


def lab_tool_drawer(draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
    """MakeLabFeatureStage parity: open plugin shelf with one primary entry."""
    """Plugin drawer: meeting assistant coexists with the original sticky-note home."""
    rows = data.get("lab_features", [])
    x, y, w, h = MARGIN, HEADER_H + SP_8, W - 2 * MARGIN, H - HEADER_H - SP_16
    filled_block(draw, (x, y + SP_4, 12, h - SP_8))
    text(draw, (x + SP_24, y + SP_12), "额外功能", F10)
    text(draw, (x + w - 90, y + SP_12), "本地 RTC", F10)

    lab_hero_card(draw, rows[0] if rows else {}, True)
    drawer_feature_row(draw, rows[1] if len(rows) > 1 else {}, "02", y + 112, False)
    drawer_feature_row(draw, rows[2] if len(rows) > 2 else {}, "03", y + 158, False)
    drawer_feature_row(draw, rows[3] if len(rows) > 3 else {}, "04", y + 204, False)



def lab_feature_stage(draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
    lab_tool_drawer(draw, data)

def lab_hero_card(draw: ImageDraw.ImageDraw, row: dict[str, str], selected: bool) -> None:
    x, y, w, h = MARGIN + 34, HEADER_H + SP_8 + 28, W - 2 * MARGIN - 46, 76
    if selected:
        filled_block(draw, (x, y + SP_8, 8, h - SP_16))
        fill = 0
    else:
        soft_card(draw, (x, y, w, h))
        fill = 0
    ix, iy = x + SP_20, y + SP_12
    text(draw, (ix, iy), row.get("title", "会议助手"), F18, fill)
    multiline(draw, (ix, iy + SP_24), row.get("subtitle", ""), F12, fill, w - SP_32 - 92, 2, 3)
    filled_block(draw, (x + w - 88, y + SP_16, 64, 24))
    text(draw, (x + w - 78, y + SP_16 + 5), "进入", F12, 255)
    text(draw, (x + w - 88, y + SP_16 + 30), "AI / QR", F10, 0)


def drawer_feature_row(draw: ImageDraw.ImageDraw, row: dict[str, str], number: str, y: int, selected: bool) -> None:
    x, w, h = MARGIN + 34, W - 2 * MARGIN - 46, 34
    if selected:
        filled_block(draw, (x, y, w, h))
        fill = 255
    else:
        fill = 0
        thin_rule(draw, (x, y + h - 1), w)
    text(draw, (x + SP_12, y + 7), number, F10, fill)
    text(draw, (x + 48, y + 5), row.get("title", ""), F14, fill)
    text(draw, (x + 158, y + 7), fit_text(row.get("subtitle", ""), 18), F10, fill)


def capability_tile(draw: ImageDraw.ImageDraw, row: dict[str, str], number: int, xy, selected: bool) -> None:
    x, y = xy
    w, h = 182, 68
    if selected:
        filled_block(draw, (x, y, w, h))
        fill = 255
    else:
        soft_card(draw, (x, y, w, h))
        draw.rectangle((x, y, x + w - 1, y + h - 1), outline=0, width=1)
        fill = 0
    ix, iy = x + SP_12, y + SP_12
    text(draw, (ix, iy), f"{number:02d}", F10, fill)
    text(draw, (ix, iy + SP_12), row.get("title", ""), F14, fill)
    text(draw, (ix, iy + SP_12 + F14.size + SP_4), fit_text(row.get("subtitle", ""), 16), F12, fill)


# ===========================================================================
# Page 3 — Meeting agenda
# ===========================================================================

def render_agenda(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    header(draw, "会议助手", "1/4")
    meeting_scroll_canvas(draw, "议程", "上下滚动")
    clean_agenda_page(draw, data)
    return img


def meeting_scroll_canvas(draw: ImageDraw.ImageDraw, section: str, hint: str) -> None:
    """Shared meeting canvas with a visible scroll affordance and quiet content area."""
    y = HEADER_H + SP_8
    text(draw, (MARGIN, y), section, F12)
    text(draw, (W - MARGIN - int(draw.textlength(hint, font=F10)), y + 1), hint, F10)
    dotted_rule(draw, (MARGIN, y + 18), W - 2 * MARGIN)


def clean_agenda_page(draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
    live_briefing_page(draw, data)


def metric_strip(draw: ImageDraw.ImageDraw, metrics: list[dict[str, Any]], xywh) -> None:
    x, y, w, h = xywh
    cell_w = w // 3
    for i, item in enumerate(metrics[:3]):
        cx = x + i * cell_w
        if i > 0:
            vertical_rule(draw, (cx - SP_8, y + 4), h - SP_8)
        text(draw, (cx, y), fit_text(item.get("label", "数据"), 8), F10)
        text(draw, (cx, y + 14), fit_text(item.get("value", "--"), 7), F18)
        text(draw, (cx, y + 38), fit_text(item.get("delta", ""), 8), F10)


def live_briefing_page(draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
    current_idx = int(data.get("current_agenda_index", 0))
    items = agenda_items(data)
    current = items[current_idx] if 0 <= current_idx < len(items) else (items[0] if items else {})
    live = data.get("live", {})
    metrics = data.get("summary", {}).get("metrics", [])

    x, y, w = MARGIN, HEADER_H + 34, W - 2 * MARGIN
    filled_block(draw, (x, y, 72, 28))
    text(draw, (x + SP_8, y + 7), "LIVE", F12, 255)
    text(draw, (x + 86, y + 2), fit_text(live.get("speaker", "发言者"), 14), F18)
    text(draw, (x + 86, y + 28), fit_text(live.get("topic", "关键主题"), 22), F12)
    text(draw, (x, y + 54), fit_text(live.get("status", "实时发言"), 18), F10)
    text(draw, (x + 160, y + 54), fit_text(live.get("remote_update", "母机同步"), 18), F10)
    thin_rule(draw, (x, y + 72), w)

    text(draw, (x, y + 86), "当前议程", F10)
    text(draw, (x + 68, y + 80), current.get("time", "--:--"), F12)
    text(draw, (x + 124, y + 78), fit_text(current.get("title", ""), 18), F14)

    metric_strip(draw, metrics, (x, y + 126, w, 58))
    text(draw, (MARGIN, H - BOTTOM_SAFE_H - F10.size - SP_4), "长按返回便利贴，短按翻页", F10, 0)


# ===========================================================================
# Page 4 — Materials / QR
# ===========================================================================

def render_materials(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    materials = data.get("materials", {})
    interaction = data.get("interaction", {})
    header(draw, "会议助手", "2/4")
    meeting_scroll_canvas(draw, "资料", "扫码")
    clean_materials_page(img, draw, materials, interaction)
    return img


def clean_materials_page(img: Image.Image, draw: ImageDraw.ImageDraw, materials: dict[str, Any], interaction: dict[str, Any]) -> None:
    # Two equal QR cards, each with a minimum 12px quiet-zone envelope for e-paper residue.
    BuildQrTicket(img, draw, (TEXT_SAFE_PAD, HEADER_H + 28, QR_CARD_W, QR_CARD_H),
                  "资料下载", materials.get("label", "PPT / PDF"), materials.get("url", "https://msh.cn/m"))
    BuildQrTicket(img, draw, (W - TEXT_SAFE_PAD - QR_CARD_W, HEADER_H + 28, QR_CARD_W, QR_CARD_H),
                  "现场提问", interaction.get("label", "提交问题"), interaction.get("url", "https://msh.cn/q"))


# ===========================================================================
# Page 5 — Insight / Summary
# ===========================================================================

def render_summary(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    header(draw, "会议助手", "3/4")
    meeting_scroll_canvas(draw, "要点", "核心数据")
    key_points_page(draw, data)
    return img


def clean_insight_page(draw: ImageDraw.ImageDraw, summary: dict[str, Any]) -> None:
    summary_receipt_page(draw, summary)


def key_points_page(draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
    summary = data.get("summary", {})
    summary_receipt_page(draw, summary)
    metric_strip(draw, summary.get("metrics", []), (MARGIN, HEADER_H + 184, W - 2 * MARGIN, 58))


def summary_receipt_page(draw: ImageDraw.ImageDraw, summary: dict[str, Any]) -> None:
    # Receipt-style summary: open body, compact keyword chips, no full-width black wall.
    mx, my, mw, mh = MARGIN, HEADER_H + 34, W - 2 * MARGIN, 140
    soft_card(draw, (mx, my, mw, mh))
    ix, iy = mx, my
    text(draw, (ix, iy), summary.get("title", "AI 摘要"), F14, 0)
    filled_block(draw, (ix, iy + 28, 54, 4))
    thin_rule(draw, (ix + 64, iy + 30), mw - 84, fill=0)
    y = iy + 36
    for line in summary.get("bullets", [])[:5]:
        wrapped = wrap_text(draw, line, F12, mw - 2 * SP_8, 1)
        for w in wrapped:
            text(draw, (ix, y), w, F12, 0)
            y += F12.size + SP_4



# ===========================================================================
# Page 6 — Reminder
# ===========================================================================

def render_reminder(data: dict[str, Any]) -> Image.Image:
    img, draw = canvas()
    header(draw, "会议助手", "4/4")
    meeting_scroll_canvas(draw, "Badge", "任务 / 健康")
    badge_reminder_page(img, draw, data)
    return img


def clean_reminder_page(img: Image.Image, draw: ImageDraw.ImageDraw, user: dict[str, Any], reminder: dict[str, Any], active_index: int) -> None:
    # Reminder list — soft card, no border
    lx, ly, lw, lh = MARGIN, HEADER_H + 34, 180, 166
    soft_card(draw, (lx, ly, lw, lh))
    ix, iy = lx + SP_12, ly + SP_12
    text(draw, (ix, iy), f"{user.get('name', '参会者')} 的提醒", F14, 0)
    thin_rule(draw, (ix, iy + SP_20), lw - 2 * SP_12, fill=0)

    for i, item in enumerate(reminder.get("items", [])[:3]):
        row_y = iy + SP_20 + SP_8 + i * 36
        active = i == active_index
        time_pill(draw, (ix, row_y, 56, 24), item.get("time", "--:--"), active)
        title_fill = 255 if active else 0
        if active:
            # Extend the filled emphasis across the row
            filled_block(draw, (ix + 60, row_y - 2, lw - 2 * SP_12 - 60 - 4, 28))
        text(draw, (ix + 68, row_y + 4), fit_text(item.get("title", ""), 8), F14, title_fill)

    # Kiosk QR on the right with the same scan target as the materials page.
    BuildQrTicket(img, draw, (208, HEADER_H + 28, QR_CARD_W, QR_CARD_H),
                  "提醒设置", "扫码修改", reminder.get("url", "https://msh.cn/r"), QR_CODE_SIZE, F12)


def identity_badge(draw: ImageDraw.ImageDraw, user: dict[str, Any], badge: dict[str, Any], xywh) -> None:
    x, y, w, h = xywh
    filled_block(draw, (x, y, w, 24))
    text(draw, (x + SP_8, y + 6), badge.get("label", "会后身份 Badge"), F10, 255)
    text(draw, (x + SP_12, y + 38), fit_text(user.get("name", "参会者"), 10), F18)
    identity_meta = f"{user.get('role', '嘉宾')} · {user.get('id', 'guest')}".strip(" ·")
    text(draw, (x + SP_12, y + 66), fit_text(identity_meta, 24), F10)


def task_list(draw: ImageDraw.ImageDraw, tasks: list[dict[str, Any]], xy) -> None:
    x, y = xy
    text(draw, (x, y), "桌面任务", F10)
    for i, item in enumerate(tasks[:2]):
        row_y = y + 18 + i * 26
        text(draw, (x, row_y), item.get("time", "--"), F10)
        text(draw, (x + 48, row_y - 2), fit_text(item.get("title", ""), 10), F12)


def health_reminder_list(draw: ImageDraw.ImageDraw, items: list[dict[str, Any]], xy) -> None:
    x, y = xy
    text(draw, (x, y), "健康提醒", F10)
    for i, item in enumerate(items[:2]):
        row_y = y + 18 + i * 24
        text(draw, (x, row_y), item.get("time", "--"), F10)
        text(draw, (x + 48, row_y - 2), fit_text(item.get("title", ""), 10), F12)


def badge_reminder_page(img: Image.Image, draw: ImageDraw.ImageDraw, data: dict[str, Any]) -> None:
    user = data.get("attendee", {})
    badge = data.get("badge", {})
    reminder = data.get("reminder", {})
    identity_badge(draw, user, badge, (MARGIN, HEADER_H + 34, 176, 90))
    task_list(draw, data.get("desktop_tasks", []), (MARGIN, HEADER_H + 132))
    health_reminder_list(draw, data.get("health_reminders", []), (MARGIN, HEADER_H + 188))
    BuildQrTicket(img, draw, (208, HEADER_H + 28, QR_CARD_W, QR_CARD_H),
                  "提醒设置", "扫码修改", reminder.get("url", "https://msh.cn/r"), QR_CODE_SIZE, F12)


# ===========================================================================
# Render + verify
# ===========================================================================

def render_pages(data: dict[str, Any], out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    pages = {
        "01_home.png": render_home(data),
        "02_note_detail.png": render_note_detail(data),
        "03_lab.png": render_lab(data),
        "04_meeting_agenda.png": render_agenda(data),
        "05_meeting_materials.png": render_materials(data),
        "06_meeting_summary.png": render_summary(data),
        "07_meeting_reminder.png": render_reminder(data),
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
                img.getpixel((200, 78)),
                img.getpixel((200, 220)),
                img.getpixel((392, 38)),
            ]
            if any(pixel == 0 for pixel in quiet_samples):
                warnings.append(f"{path.name}: QR quiet-zone guard samples are not white")
        if "reminder" in path.name:
            quiet_samples = [
                img.getpixel((8, 78)),
                img.getpixel((198, 78)),
                img.getpixel((198, 220)),
                img.getpixel((392, 38)),
            ]
            if any(pixel == 0 for pixel in quiet_samples):
                warnings.append(f"{path.name}: QR quiet-zone guard samples are not white")
    return warnings


def decode_qr_payloads(path: Path) -> list[str]:
    return [item.text for item in decode_qr_items(path)]


def decode_qr_items(path: Path):
    try:
        import zxingcpp
    except ModuleNotFoundError:
        return []
    return zxingcpp.read_barcodes(Image.open(path).convert("RGB"))


def verify_qr(paths: list[Path]) -> None:
    for path in paths:
        decoded = decode_qr_payloads(path)
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
