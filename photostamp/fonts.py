"""Cross-platform font discovery and loading for PhotoStamp.

Font-loading strategy (applied in order):
  1. Check a curated dict of known absolute paths for the requested family.
     These are platform-specific and verified with Path.exists(), which is fast
     (~microseconds). No directory walking occurs if a known path resolves.
  2. If no known path exists, fall back to a directory scan of standard OS font
     folders. This is slower (~milliseconds) but catches fonts installed in
     non-standard locations or families not in the known-paths dict.
  3. If the requested family still cannot be found, try finding *any* TrueType
     font on the system so text rendering is never completely broken.
  4. As an absolute last resort, use Pillow's built-in bitmap font. It always
     works but ignores the requested size, so large text will appear tiny.

The find_font_file() result is cached per family name so repeated calls
(e.g. during auto-size binary search) skip the disk operations.
"""

import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PIL import ImageFont


# ---------------------------------------------------------------------------
# Known font file paths per platform
# ---------------------------------------------------------------------------
# Maps lowercase family name → ordered list of candidate absolute paths.
# First existing path wins. Keeping explicit paths avoids slow directory scans
# for the common case.

def _build_known_paths() -> dict[str, list[str]]:
    if sys.platform == "win32":
        import os
        f = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
        return {
            "arial":           [str(f / "arial.ttf")],
            "arial bold":      [str(f / "arialbd.ttf")],
            "times new roman": [str(f / "times.ttf")],
            "georgia":         [str(f / "georgia.ttf")],
            "verdana":         [str(f / "verdana.ttf")],
            "trebuchet ms":    [str(f / "trebuc.ttf")],
            "impact":          [str(f / "impact.ttf")],
            "courier new":     [str(f / "cour.ttf")],
            "tahoma":          [str(f / "tahoma.ttf")],
            "comic sans ms":   [str(f / "comic.ttf")],
            "calibri":         [str(f / "calibri.ttf")],
            "segoe ui":        [str(f / "segoeui.ttf")],
        }

    if sys.platform == "darwin":
        # Office fonts land in /Library/Fonts/ when MS Office is installed.
        # On macOS 13+ many also appear under /System/Library/Fonts/Supplemental/.
        lib   = "/Library/Fonts"
        supp  = "/System/Library/Fonts/Supplemental"
        sys_f = "/System/Library/Fonts"
        return {
            "arial":           [f"{lib}/Arial.ttf",         f"{supp}/Arial.ttf"],
            "arial bold":      [f"{lib}/Arial Bold.ttf",    f"{supp}/Arial Bold.ttf"],
            "times new roman": [f"{lib}/Times New Roman.ttf", f"{supp}/Times New Roman.ttf"],
            "georgia":         [f"{lib}/Georgia.ttf",       f"{supp}/Georgia.ttf"],
            "verdana":         [f"{lib}/Verdana.ttf",       f"{supp}/Verdana.ttf"],
            "trebuchet ms":    [f"{lib}/Trebuchet MS.ttf",  f"{supp}/Trebuchet MS.ttf"],
            "impact":          [f"{lib}/Impact.ttf",        f"{supp}/Impact.ttf"],
            "courier new":     [f"{lib}/Courier New.ttf",   f"{supp}/Courier New.ttf"],
            "tahoma":          [f"{lib}/Tahoma.ttf",        f"{supp}/Tahoma.ttf"],
            "comic sans ms":   [f"{lib}/Comic Sans MS.ttf", f"{supp}/Comic Sans MS.ttf"],
            # Helvetica is always present on macOS as a TrueType Collection (.ttc).
            # Pillow opens .ttc files at index 0 (Regular) by default.
            "helvetica":       [f"{sys_f}/Helvetica.ttc"],
            "helvetica neue":  [f"{sys_f}/HelveticaNeue.ttc"],
        }

    # Linux / other — no reliable hardcoded paths; rely on directory scan only.
    return {}


_KNOWN_PATHS: dict[str, list[str]] = _build_known_paths()


# ---------------------------------------------------------------------------
# Font names offered in the GUI dropdown
# ---------------------------------------------------------------------------

COMMON_FONTS = [
    "Arial",
    "Helvetica",
    "Helvetica Neue",
    "Times New Roman",
    "Georgia",
    "Verdana",
    "Trebuchet MS",
    "Impact",
    "Tahoma",
    "Courier New",
    "Comic Sans MS",
    "Calibri",
    "Segoe UI",
]


# ---------------------------------------------------------------------------
# Font file discovery
# ---------------------------------------------------------------------------

@lru_cache(maxsize=64)
def find_font_file(family: str) -> Optional[str]:
    """Return the absolute path of a font file for *family*, or None.

    Checks platform-specific known paths first (fast), then falls back to
    scanning standard OS font directories (slower but catches unusual installs).
    Results are cached so repeated calls for the same family are free.
    """
    key = family.lower().strip()

    # --- 1. Check known paths ---
    for candidate in _KNOWN_PATHS.get(key, []):
        if Path(candidate).exists():
            return candidate

    # --- 2. Directory scan fallback ---
    # Only reached for fonts not in the known-paths dict or if no known path
    # existed on this system (e.g. Office not installed on macOS).
    name_key = key.replace(" ", "")
    scan_dirs = _scan_dirs()
    candidates: list[Path] = []

    for d in scan_dirs:
        if not d.exists():
            continue
        try:
            for f in d.rglob("*"):
                if f.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                    continue
                stem_key = f.stem.lower().replace(" ", "").replace("-", "").replace("_", "")
                if stem_key == name_key or stem_key.startswith(name_key):
                    candidates.append(f)
        except PermissionError:
            continue

    if not candidates:
        return None

    # Prefer shorter stem names — they are usually the Regular variant.
    candidates.sort(key=lambda p: len(p.stem))
    return str(candidates[0])


def _scan_dirs() -> list[Path]:
    if sys.platform == "win32":
        import os
        return [Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"]
    if sys.platform == "darwin":
        return [
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path("/System/Library/Fonts/Supplemental"),
            Path.home() / "Library/Fonts",
        ]
    return [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
    ]


def _find_any_font_file() -> Optional[str]:
    """Return the path to *any* loadable TrueType font as a final fallback."""
    for d in _scan_dirs():
        if not d.exists():
            continue
        for f in d.rglob("*.ttf"):
            return str(f)
    return None


# ---------------------------------------------------------------------------
# Font loading
# ---------------------------------------------------------------------------

def load_font(family: str, size: int) -> ImageFont.ImageFont:
    """Load *family* at *size* points, falling back gracefully if unavailable.

    Fallback chain:
      1. Requested family  (via find_font_file)
      2. Any available TrueType font on the system
      3. Pillow's built-in bitmap font (always succeeds; ignores size)
    """
    # --- 1. Requested family ---
    path = find_font_file(family)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            pass  # corrupted or unreadable file; try next option

    # --- 2. Any TrueType font on the system ---
    # This ensures we always get a scalable font even if the chosen family is
    # missing (e.g. Arial not installed on a fresh macOS without Office).
    fallback_path = _find_any_font_file()
    if fallback_path:
        try:
            return ImageFont.truetype(fallback_path, size)
        except (IOError, OSError):
            pass

    # --- 3. Pillow built-in bitmap font ---
    # Last resort: always works, but the size argument is ignored by Pillow < 10.1
    # and the font will appear very small on large images.
    try:
        return ImageFont.load_default(size=size)   # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Available-font detection (for the GUI dropdown)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def list_available_fonts() -> list[str]:
    """Return fonts from COMMON_FONTS that are loadable as TrueType on this system.

    Checks only the fast known-paths table — no directory scanning — so this is
    safe to call at application startup. Fonts that are not installed simply
    won't appear in the list; the user may still type any name manually.

    Arial (or Helvetica on macOS) is always placed first.
    """
    available: list[str] = []
    for name in COMMON_FONTS:
        path = find_font_file(name)
        if path and Path(path).exists():
            available.append(name)

    if not available:
        # Nothing detected (e.g. Linux with no known paths set up); return the
        # full list so the user has something to choose from.
        return list(COMMON_FONTS)

    # Promote Arial to the top; fall back to Helvetica on macOS-only systems.
    for preferred in ("Arial", "Helvetica", "Helvetica Neue"):
        if preferred in available:
            available.remove(preferred)
            available.insert(0, preferred)
            break  # only one at the top

    return available
