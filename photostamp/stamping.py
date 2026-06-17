"""Pillow-based image stamping."""

import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from photostamp.config import BandPosition, StampSettings, TextAlignment


# ---------------------------------------------------------------------------
# Font loading
# ---------------------------------------------------------------------------

def _find_font_file(family: str) -> Optional[str]:
    """Search OS font directories for a TTF/OTF file matching *family*."""
    name_key = family.lower().replace(" ", "")

    if sys.platform == "win32":
        import os
        dirs = [Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"]
    elif sys.platform == "darwin":
        dirs = [
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path("/System/Library/Fonts/Supplemental"),
            Path.home() / "Library/Fonts",
        ]
    else:
        dirs = [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".fonts",
        ]

    candidates: list[Path] = []
    for d in dirs:
        if not d.exists():
            continue
        try:
            for f in d.rglob("*"):
                if f.suffix.lower() not in (".ttf", ".otf"):
                    continue
                stem_key = (
                    f.stem.lower().replace(" ", "").replace("-", "").replace("_", "")
                )
                if stem_key == name_key or stem_key.startswith(name_key):
                    candidates.append(f)
        except PermissionError:
            continue

    if not candidates:
        return None
    # Prefer the shortest stem name (most likely the "regular" variant)
    candidates.sort(key=lambda p: len(p.stem))
    return str(candidates[0])


def _find_any_font() -> Optional[str]:
    """Return the path to any available TrueType font on the system."""
    if sys.platform == "win32":
        dirs = [Path("C:/Windows/Fonts")]
    elif sys.platform == "darwin":
        dirs = [Path("/Library/Fonts"), Path("/System/Library/Fonts")]
    else:
        dirs = [Path("/usr/share/fonts")]

    for d in dirs:
        if not d.exists():
            continue
        for f in d.rglob("*.ttf"):
            return str(f)
    return None


def load_font(family: str, size: int) -> ImageFont.ImageFont:
    """Load a font by family name and size, falling back gracefully."""
    font_path = _find_font_file(family)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except (IOError, OSError):
            pass

    # Try any available font on the system
    any_font = _find_any_font()
    if any_font:
        try:
            return ImageFont.truetype(any_font, size)
        except (IOError, OSError):
            pass

    # Absolute last resort: Pillow's built-in bitmap font
    try:
        return ImageFont.load_default(size=size)   # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Auto font-size calculation
# ---------------------------------------------------------------------------

def _auto_font_size(band_h: int, band_w: int, text: str, family: str) -> int:
    """Return the largest font size that fits *text* inside the band."""
    if not text:
        return max(8, int(band_h * 0.65))

    target = max(8, int(band_h * 0.65))
    font = load_font(family, target)

    # Measure at target size
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]

    available_w = band_w * 0.92  # 4 % padding per side
    if text_w <= available_w:
        return target

    # Scale down proportionally so text fits width
    scale = available_w / text_w
    return max(8, int(target * scale))


# ---------------------------------------------------------------------------
# Core stamping
# ---------------------------------------------------------------------------

def stamp_image(image: Image.Image, text: str, settings: StampSettings) -> Image.Image:
    """Return a stamped copy of *image*; the original is never modified."""
    img = image.copy()

    if not settings.band_enabled or not text.strip():
        return img

    w, h = img.size

    # --- Band rectangle ---
    pos = settings.band_position
    if pos in (BandPosition.TOP, BandPosition.BOTTOM):
        band_thick = max(1, int(h * settings.band_size_ratio))
        if pos == BandPosition.BOTTOM:
            band_box = (0, h - band_thick, w, h)
        else:
            band_box = (0, 0, w, band_thick)
        text_area_w, text_area_h = w, band_thick
    else:  # LEFT or RIGHT
        band_thick = max(1, int(w * settings.band_size_ratio))
        if pos == BandPosition.LEFT:
            band_box = (0, 0, band_thick, h)
        else:
            band_box = (w - band_thick, 0, w, h)
        text_area_w, text_area_h = band_thick, h

    bx1, by1, bx2, by2 = band_box

    # --- Draw band via RGBA alpha-composite (handles opacity) ---
    original_mode = img.mode
    img_rgba = img.convert("RGBA")

    band_alpha = int(settings.band_opacity * 255)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle(
        band_box, fill=(*settings.band_color, band_alpha)
    )
    img_rgba = Image.alpha_composite(img_rgba, overlay)

    # --- Draw text ---
    draw = ImageDraw.Draw(img_rgba)

    font_size = settings.font_size
    if font_size is None:
        font_size = _auto_font_size(
            text_area_h, text_area_w, text, settings.font_family
        )

    font = load_font(settings.font_family, font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Horizontal alignment within band
    padding = max(8, int(text_area_w * 0.02))
    if settings.text_alignment == TextAlignment.LEFT:
        tx = bx1 + padding
    elif settings.text_alignment == TextAlignment.RIGHT:
        tx = bx2 - text_w - padding
    else:  # CENTER
        tx = bx1 + (text_area_w - text_w) // 2

    # Vertical: center in band
    ty = by1 + (text_area_h - text_h) // 2

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
    """Write *image* to *output_path*, choosing the best save options per format."""
    ext = output_path.suffix.lower()

    if ext in (".jpg", ".jpeg"):
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
