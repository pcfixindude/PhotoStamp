"""Load and save user preferences to a local settings.json file.

Only UI preferences and folder paths are stored — never image data or file
contents. If the file is missing, unreadable, or contains invalid values,
defaults are used and the app continues normally.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from photostamp.config import DEFAULT_FONT_FAMILY


# Stored next to the project root (same directory as app.py).
_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"

_VALID_ALIGNMENTS = {"left", "center", "right"}
_VALID_BAND_POSITIONS = {"top", "bottom", "left", "right"}


@dataclass
class UserSettings:
    """Persisted user preferences."""

    input_folder: Optional[str] = None
    output_folder: Optional[str] = None
    title_case: bool = False
    font_family: str = DEFAULT_FONT_FAMILY
    font_size_auto: bool = True
    font_size: int = 32
    text_color: str = "#000000"
    text_alignment: str = "center"
    band_enabled: bool = True
    band_position: str = "bottom"
    band_size: int = 15
    band_color: str = "#ffffff"
    band_opacity: int = 100


def settings_path() -> Path:
    """Return the path to the settings JSON file."""
    return _SETTINGS_PATH


def load_settings() -> UserSettings:
    """Load settings from disk, falling back to defaults on any error."""
    defaults = UserSettings()

    try:
        if not _SETTINGS_PATH.exists():
            return defaults

        with _SETTINGS_PATH.open(encoding="utf-8") as fh:
            raw = json.load(fh)

        if not isinstance(raw, dict):
            return defaults

        return _parse_settings(raw, defaults)

    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        # Corrupt or unreadable file — use defaults without crashing.
        return defaults


def save_settings(settings: UserSettings) -> None:
    """Write *settings* to disk. Failures are swallowed so the app never crashes."""
    try:
        data = asdict(settings)
        with _SETTINGS_PATH.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
    except OSError:
        pass


def _parse_settings(raw: dict[str, Any], defaults: UserSettings) -> UserSettings:
    """Merge *raw* JSON values into a UserSettings, validating each field."""
    return UserSettings(
        input_folder=_optional_folder(raw.get("input_folder")),
        output_folder=_optional_folder(raw.get("output_folder")),
        title_case=_bool(raw.get("title_case"), defaults.title_case),
        font_family=_str(raw.get("font_family"), defaults.font_family),
        font_size_auto=_bool(raw.get("font_size_auto"), defaults.font_size_auto),
        font_size=_int_in_range(raw.get("font_size"), 6, 300, defaults.font_size),
        text_color=_hex_color(raw.get("text_color"), defaults.text_color),
        text_alignment=_choice(
            raw.get("text_alignment"), _VALID_ALIGNMENTS, defaults.text_alignment
        ),
        band_enabled=_bool(raw.get("band_enabled"), defaults.band_enabled),
        band_position=_choice(
            raw.get("band_position"), _VALID_BAND_POSITIONS, defaults.band_position
        ),
        band_size=_int_in_range(raw.get("band_size"), 3, 50, defaults.band_size),
        band_color=_hex_color(raw.get("band_color"), defaults.band_color),
        band_opacity=_int_in_range(raw.get("band_opacity"), 0, 100, defaults.band_opacity),
    )


def _optional_folder(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    return str(path) if path.is_dir() else None


def _bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _str(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value.strip() else default


def _int_in_range(value: Any, lo: int, hi: int, default: int) -> int:
    if not isinstance(value, (int, float)):
        return default
    iv = int(value)
    return iv if lo <= iv <= hi else default


def _choice(value: Any, valid: set[str], default: str) -> str:
    return value if isinstance(value, str) and value in valid else default


def _hex_color(value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    v = value.strip()
    if len(v) == 7 and v.startswith("#"):
        try:
            int(v[1:], 16)
            return v.lower()
        except ValueError:
            pass
    return default
