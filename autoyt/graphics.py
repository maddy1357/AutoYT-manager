"""Thumbnails, intro title overlays and slides, drawn with Pillow."""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_BODY_FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int, body: bool = False) -> ImageFont.FreeTypeFont:
    for path in (_BODY_FONT_CANDIDATES if body else _FONT_CANDIDATES):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def hex_color(value: str, default: str = "#FFD400") -> tuple[int, int, int]:
    value = value.strip() if isinstance(value, str) else ""
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
        value = default
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def gradient(size: tuple[int, int], colors: list[str]) -> Image.Image:
    cols = [hex_color(c, "#1E3A8A") for c in (colors or [])] or [(30, 58, 138), (124, 58, 237)]
    if len(cols) == 1:
        cols.append(tuple(max(0, c - 70) for c in cols[0]))
    w, h = size
    # Diagonal blend between consecutive colours, built at low res then upscaled (smooth + fast).
    small = Image.new("RGB", (64, 36))
    px = small.load()
    for y in range(36):
        for x in range(64):
            t = (x / 63 * 0.7 + y / 35 * 0.3) * (len(cols) - 1)
            i = min(int(t), len(cols) - 2)
            f = t - i
            px[x, y] = tuple(round(cols[i][k] * (1 - f) + cols[i + 1][k] * f) for k in range(3))
    return small.resize(size, Image.BICUBIC)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fit_text(draw, text, max_width, max_height, max_lines, start, body=False):
    size = start
    while size > 18:
        font = _font(size, body)
        lines = _wrap(draw, text, font, max_width)
        line_h = font.getbbox("Ag")[3] * 1.12
        if len(lines) <= max_lines and line_h * len(lines) <= max_height and all(
            draw.textlength(l, font=font) <= max_width for l in lines
        ):
            return font, lines, line_h
        size -= 4
    font = _font(size, body)
    return font, _wrap(draw, text, font, max_width)[:max_lines], font.getbbox("Ag")[3] * 1.12


def make_thumbnail(out: Path, text: str, accent: str, frame: Path | None = None,
                   bg_colors: list[str] | None = None) -> Path:
    W, H = 1280, 720
    if frame and frame.exists():
        base = _cover(Image.open(frame).convert("RGB"), (W, H))
        base = ImageEnhance.Contrast(ImageEnhance.Color(base).enhance(1.25)).enhance(1.12)
    else:
        base = gradient((W, H), bg_colors or [])

    # Darken the left side so text stays readable on any frame.
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(190 * max(0.0, 1 - x / (W * 0.75))))
    base = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), base, shade)

    draw = ImageDraw.Draw(base)
    accent_rgb = hex_color(accent)
    text = (text or "").strip().upper() or "WATCH THIS"
    font, lines, line_h = _fit_text(draw, text, int(W * 0.62), int(H * 0.72), 3, 150)
    y = (H - line_h * len(lines)) / 2
    stroke = max(4, font.size // 14)
    for i, line in enumerate(lines):
        fill = accent_rgb if i == len(lines) - 1 and len(lines) > 1 else (255, 255, 255)
        draw.text((64, y), line, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += line_h
    draw.rectangle([(64, H - 58), (64 + 220, H - 46)], fill=accent_rgb)

    out.parent.mkdir(parents=True, exist_ok=True)
    quality = 92
    base.save(out, "JPEG", quality=quality, optimize=True)
    while out.stat().st_size > 2_000_000 and quality > 50:  # YouTube's 2 MB thumbnail limit
        quality -= 10
        base.save(out, "JPEG", quality=quality, optimize=True)
    return out


def make_title_overlay(out: Path, title: str, accent: str, size: tuple[int, int]) -> tuple[Path, int, int]:
    """Lower-third title card. Returns (png, x, y): only the card itself is stored, so ffmpeg
    blends a small image instead of a full-frame transparent layer."""
    W, H = size
    pad = int(W * 0.05)
    box_w = int(W * 0.9)
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    font, lines, line_h = _fit_text(measure, title, box_w - 2 * pad, int(H * 0.16), 2, int(min(W, H) * 0.075))
    box_h = int(line_h * len(lines) + pad)
    card = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle([(0, 0), (box_w - 1, box_h - 1)], radius=int(min(W, H) * 0.02), fill=(10, 10, 14, 185))
    draw.rectangle([(0, 0), (10, box_h)], fill=(*hex_color(accent), 255))
    y = pad / 2
    for line in lines:
        draw.text((pad, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h
    out.parent.mkdir(parents=True, exist_ok=True)
    card.save(out, "PNG")
    return out, (W - box_w) // 2, H - box_h - int(H * 0.08)


def make_slide(out: Path, heading: str, body: str, colors: list[str], accent: str,
               index: int, total: int, size: tuple[int, int] = (1920, 1080)) -> Path:
    W, H = size
    # Rotate the palette per slide so consecutive scenes feel distinct.
    shift = index % max(1, len(colors or [1]))
    img = gradient(size, (colors or [])[shift:] + (colors or [])[:shift]).filter(ImageFilter.GaussianBlur(2))
    draw = ImageDraw.Draw(img)
    accent_rgb = hex_color(accent)
    margin = int(W * 0.08)

    h_font, h_lines, h_lh = _fit_text(draw, heading.upper(), W - 2 * margin, int(H * 0.3), 2, 120)
    b_font, b_lines, b_lh = _fit_text(draw, body, W - 2 * margin, int(H * 0.32), 3, 64, body=True)
    total_h = h_lh * len(h_lines) + 50 + b_lh * len(b_lines)
    y = (H - total_h) / 2
    for line in h_lines:
        draw.text((margin, y), line, font=h_font, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
        y += h_lh
    draw.rectangle([(margin, y + 12), (margin + 160, y + 24)], fill=accent_rgb)
    y += 50
    for line in b_lines:
        draw.text((margin, y), line, font=b_font, fill=(235, 238, 245))
        y += b_lh
    # Progress dots.
    for i in range(total):
        cx = W - margin - (total - 1 - i) * 30
        current = i == index
        draw.ellipse([(cx - 7, H - 70), (cx + 7, H - 56)], fill=accent_rgb if current else None,
                     outline=accent_rgb if current else (255, 255, 255), width=2)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out
