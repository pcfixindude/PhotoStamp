"""Pillow-based image stamping."""

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from photostamp.config import BandPosition, StampSettings, TextAlignment
from photostamp.fonts import load_font


# ---------------------------------------------------------------------------
# Auto font-size calculation
# ---------------------------------------------------------------------------

def _auto_font_size(band_h: int, band_w: int, text: str, family: str) -> int:
    """Return the largest font size (pt) where *text* fits inside the band.

    The maximum size is capped at 65 % of the band's height so the text has
    vertical breathing room. Then a binary search narrows down the exact point
    size where the rendered width fits within 92 % of the band width (4 %
    padding each side). Binary search is used instead of simple proportional
    scaling because font metrics are not perfectly linear across sizes.
    """
    if not text:
        return max(8, int(band_h * 0.65))

    max_by_height = max(8, int(band_h * 0.65))
    available_w = int(band_w * 0.92)

    # Reuse a single tiny scratch image for all measurements — no pixels
    # are rendered, only metrics are queried.
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)

    lo, hi, best = 8, max_by_height, 8
    while lo <= hi:
        mid = (lo + hi) // 2
        font = load_font(family, mid)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        if tw <= available_w:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1

    return best


# ---------------------------------------------------------------------------
# Core stamping
# ---------------------------------------------------------------------------

def stamp_image(image: Image.Image, text: str, settings: StampSettings) -> Image.Image:
    """Return a stamped copy of *image*; the original is never modified."""
    img = image.copy()

    if not settings.band_enabled or not text.strip():
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

    # --- Draw band via RGBA alpha-composite ---
    # Converting to RGBA lets us paint a partially-transparent rectangle
    # cleanly over any source mode (RGB, P, L, etc.).
    original_mode = img.mode
    img_rgba = img.convert("RGBA")

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
            text_area_h, text_area_w, text, settings.font_family
        )

    font = load_font(settings.font_family, font_size)

    # --- Measure text precisely ---
    # textbbox returns (x0, y0, x1, y1) relative to the anchor (0, 0).
    # x0 / y0 are non-zero when the font has a left or top bearing (common in
    # TrueType fonts). Accounting for these offsets is necessary for accurate
    # centering; ignoring them causes text to drift slightly off-center.
    draw = ImageDraw.Draw(img_rgba)
    bbox = draw.textbbox((0, 0), text, font=font)
    x0, y0 = bbox[0], bbox[1]
    text_w = bbox[2] - x0
    text_h = bbox[3] - y0

    # --- Horizontal position ---
    padding = max(8, int(text_area_w * 0.02))
    if settings.text_alignment == TextAlignment.LEFT:
        tx = bx1 + padding - x0
    elif settings.text_alignment == TextAlignment.RIGHT:
        tx = bx1 + text_area_w - text_w - padding - x0
    else:  # CENTER
        tx = bx1 + (text_area_w - text_w) // 2 - x0

    # --- Vertical position: center in band ---
    ty = by1 + (text_area_h - text_h) // 2 - y0

    draw.text((tx, ty), text, font=font, fill=(*settings.text_color, 255))

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
