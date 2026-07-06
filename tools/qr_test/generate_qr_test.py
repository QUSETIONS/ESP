#!/usr/bin/env python3
from pathlib import Path

import qrcode
import zxingcpp
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"

PAYLOADS = {
    "materials": "https://msh.cn/m",
    "questions": "https://msh.cn/q",
    "reminder": "https://msh.cn/r",
}


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


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


def decode(path: Path) -> list[str]:
    img = Image.open(path).convert("RGB")
    return [result.text for result in zxingcpp.read_barcodes(img)]


def draw_qr_card(draw: ImageDraw.ImageDraw, canvas: Image.Image, xywh, title: str, subtitle: str, payload: str, qr_size: int):
    x, y, w, h = xywh
    draw.rectangle((x, y, x + w, y + h), outline=0, width=1)
    draw.rectangle((x + 6, y + 6, x + w - 8, y + 33), fill=0)
    draw.text((x + 12, y + 9), title, fill=255, font=font(16))
    draw.text((x + 8, y + 40), subtitle, fill=0, font=font(13))
    qr = make_qr(payload, qr_size)
    canvas.paste(qr, (x + (w - qr_size) // 2, y + h - qr_size - 8))


def make_materials_preview() -> Image.Image:
    img = Image.new("1", (400, 300), 255)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 399, 35), fill=0)
    draw.text((12, 7), "会议资料与互动", fill=255, font=font(17))
    draw.text((334, 10), "2/4", fill=255, font=font(13))
    draw.rectangle((10, 46, 390, 74), fill=0)
    draw.text((16, 50), "资料和互动入口", fill=255, font=font(16))
    draw_qr_card(draw, img, (12, 88, 180, 184), "资料下载", "PPT / PDF", PAYLOADS["materials"], 122)
    draw_qr_card(draw, img, (208, 88, 180, 184), "现场提问", "提交问题", PAYLOADS["questions"], 122)
    return img


def make_reminder_preview() -> Image.Image:
    img = Image.new("1", (400, 300), 255)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 399, 35), fill=0)
    draw.text((12, 7), "个人提醒", fill=255, font=font(17))
    draw.text((334, 10), "4/4", fill=255, font=font(13))
    draw.rectangle((10, 46, 224, 74), fill=0)
    draw.text((16, 50), "张军先生  个人提醒", fill=255, font=font(16))
    draw.rectangle((10, 88, 224, 262), outline=0, width=1)
    for idx, (t, label) in enumerate((("11:30", "午餐与交流"), ("14:00", "分论坛"), ("15:30", "集体合影"))):
        y = 100 + idx * 54
        draw.rectangle((20, y, 74, y + 24), fill=0)
        draw.text((25, y + 4), t, fill=255, font=font(12))
        draw.text((86, y + 2), label, fill=0, font=font(16))
    draw_qr_card(draw, img, (242, 78, 146, 194), "自定义提醒", "微信扫码修改", PAYLOADS["reminder"], 120)
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    expected = set(PAYLOADS.values())
    generated = []
    for name, payload in PAYLOADS.items():
        size = 120 if name == "reminder" else 122
        path = OUT / f"{name}_{size}px.png"
        make_qr(payload, size).save(path)
        generated.append(path)

    preview_paths = [
        OUT / "materials_page_400x300.png",
        OUT / "reminder_page_400x300.png",
    ]
    make_materials_preview().save(preview_paths[0])
    make_reminder_preview().save(preview_paths[1])
    generated.extend(preview_paths)

    ok = True
    for path in generated:
        decoded = decode(path)
        print(f"{path.relative_to(ROOT)} -> {decoded}")
        if path.name.endswith("_400x300.png"):
            if not set(decoded).issubset(expected) or not decoded:
                ok = False
        else:
            payload = PAYLOADS[path.stem.split("_")[0]]
            if decoded != [payload]:
                ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
