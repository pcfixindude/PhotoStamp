"""Pillow-based image stamping."""

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from photostamp.config import BandPosition, StampSettings, TextAlignment
from photostamp.fonts import load_font


# ---------------------------------------------------------------------------
# Auto font-size calculation
# ---------------------------------------------------------------------------

def _auto_font_size(
    band_h: int,
    band_w: int,
    name_text: str,
    family: str,
    date_text: str = "",
) -> int:
    """Return the largest name font size where one/two lines fit in the band.

    The optional date line is measured at 80% of the name size unless a manual
    date size is supplied later. Binary search avoids assuming font metrics are
    perfectly linear across sizes.
    """
    if not name_text:
        return max(8, int(band_h * 0.65))

    available_w = int(band_w * 0.92)
    max_by_height = max(8, int(band_h * (0.65 if not date_text else 0.48)))
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)

    lo, hi, best = 8, max_by_height, 8
    while lo <= hi:
        mid = (lo + hi) // 2
        date_size = max(8, int(mid * 0.8))
        layout = _measure_lines(draw, family, name_text, mid, date_text, date_size)
        if layout["width"] <= available_w and layout["height"] <= int(band_h * 0.9):
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1

    return best


def _measure_lines(
    draw: ImageDraw.ImageDraw,
    family: str,
    name_text: str,
    name_size: int,
    date_text: str,
    date_size: int,
) -> dict[str, object]:
    """Return font metrics for the name line and optional date line."""
    lines: list[dict[str, object]] = []
    for text, size in ((name_text, name_size), (date_text, date_size)):
        if not text:
            continue
        font = load_font(family, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        x0, y0 = bbox[0], bbox[1]
        lines.append(
            {
                "text": text,
                "font": font,
                "x0": x0,
                "y0": y0,
                "width": bbox[2] - x0,
                "height": bbox[3] - y0,
            }
        )

    gap = max(2, int(name_size * 0.18)) if len(lines) == 2 else 0
    width = max((int(line["width"]) for line in lines), default=0)
    height = sum(int(line["height"]) for line in lines) + gap
    return {"lines": lines, "gap": gap, "width": width, "height": height}


def _fit_font_sizes(
    draw: ImageDraw.ImageDraw,
    family: str,
    text: str,
    date_text: str,
    name_size: int,
    date_size: int,
    band_w: int,
    band_h: int,
) -> tuple[int, int]:
    """Shrink manual font sizes if they would overflow the band."""
    available_w = int(band_w * 0.92)
    available_h = int(band_h * 0.9)

    while name_size > 8 or date_size > 8:
        layout = _measure_lines(draw, family, text, name_size, date_text, date_size)
        if int(layout["width"]) <= available_w and int(layout["height"]) <= available_h:
            break
        name_size = max(8, name_size - 1)
        date_size = max(8, date_size - 1)
    return name_size, date_size


# ---------------------------------------------------------------------------
# Core stamping
# ---------------------------------------------------------------------------

def stamp_image(
    image: Image.Image,
    text: str,
    settings: StampSettings,
    *,
    date_text: str = "",
) -> Image.Image:
    """Return a stamped copy of *image*; the original is never modified."""
    img = image.copy()

    date_text = date_text.strip()
    text = text.strip()
    if not text and not date_text:
        return img

    w, h = img.size

    # --- Compute band rectangle ---
    pos = settings.band_position
    if pos in (BandPosition.TOP, BandPosition.BOTTOM):
        band_thick = max(1, int(h * settings.band_size_ratio))
        band_box = (0, h - band_thick, w, h) if pos == BandPosition.BOTTOM \
                   else (0, 0, w, band_thick)
        text_area_w, text_area_h = w, band_thick
    else:  # LEFT or RIGHT
        band_thick = max(1, int(w * settings.band_size_ratio))
        band_box = (w - band_thick, 0, w, h) if pos == BandPosition.RIGHT \
                   else (0, 0, band_thick, h)
        text_area_w, text_area_h = band_thick, h

    bx1, by1, _bx2, _by2 = band_box

    # --- Prepare RGBA drawing surface ---
    # Converting to RGBA lets us paint a partially-transparent rectangle
    # cleanly over any source mode (RGB, P, L, etc.).
    original_mode = img.mode
    img_rgba = img.convert("RGBA")

    if settings.show_background_band:
        band_alpha = int(settings.band_opacity * 255)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rectangle(
            band_box, fill=(*settings.band_color, band_alpha)
        )
        img_rgba = Image.alpha_composite(img_rgba, overlay)

    # --- Resolve font and size ---
    font_size = settings.font_size
    if font_size is None:
        font_size = _auto_font_size(
            text_area_h, text_area_w, text, settings.font_family, date_text
        )

    date_font_size = settings.date_font_size or max(8, int(font_size * 0.8))

    # --- Measure text precisely ---
    # textbbox returns offsets relative to the anchor. Accounting for x0/y0 is
    # necessary for accurate centering with TrueType fonts.
    draw = ImageDraw.Draw(img_rgba)
    font_size, date_font_size = _fit_font_sizes(
        draw,
        settings.font_family,
        text,
        date_text,
        font_size,
        date_font_size,
        text_area_w,
        text_area_h,
    )
    layout = _measure_lines(
        draw,
        settings.font_family,
        text,
        font_size,
        date_text,
        date_font_size,
    )
    lines = layout["lines"]
    gap = int(layout["gap"])
    total_h = int(layout["height"])

    # --- Horizontal position ---
    padding = max(8, int(text_area_w * 0.02))
    y = by1 + (text_area_h - total_h) // 2

    for index, line in enumerate(lines):
        line_w = int(line["width"])
        line_h = int(line["height"])
        x0 = int(line["x0"])
        y0 = int(line["y0"])

        if settings.text_alignment == TextAlignment.LEFT:
            tx = bx1 + padding - x0
        elif settings.text_alignment == TextAlignment.RIGHT:
            tx = bx1 + text_area_w - line_w - padding - x0
        else:  # CENTER
            tx = bx1 + (text_area_w - line_w) // 2 - x0

        color = (
            settings.date_color
            if index == 1 and settings.date_color is not None
            else settings.text_color
        )
        draw.text((tx, y - y0), str(line["text"]), font=line["font"], fill=(*color, 255))
        y += line_h + gap

    # --- Restore original color mode ---
    if original_mode == "RGB":
        return img_rgba.convert("RGB")
    if original_mode == "RGBA":
        return img_rgba
    return img_rgba.convert(original_mode)


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

def save_stamped_image(
    image: Image.Image,
    output_path: Path,
    *,
    source_format: Optional[str] = None,
) -> None:
    """Write *image* to *output_path*, choosing the best options per format."""
    ext = output_path.suffix.lower()

    if ext in (".jpg", ".jpeg"):
        # JPEG does not support an alpha channel.
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGB")
        image.save(output_path, "JPEG", quality=95, optimize=True)
    elif ext == ".png":
        image.save(output_path, "PNG", optimize=True)
    elif ext == ".webp":
        image.save(output_path, "WEBP", quality=95)
    elif ext == ".bmp":
        if image.mode in ("RGBA", "LA"):
            image = image.convert("RGB")
        image.save(output_path, "BMP")
    else:
        image.save(output_path)
