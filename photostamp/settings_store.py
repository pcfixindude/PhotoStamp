"""Load and save user preferences to a local settings.json file.

Only UI preferences and folder paths are stored — never image data or file
contents. If the file is missing, unreadable, or contains invalid values,
defaults are used and the app continues normally.
"""

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from photostamp.config import (
    DEFAULT_FONT_FAMILY,
    DateDisplayFormat,
    DateSource,
    ExportFileType,
    ExportSizeMode,
)


def _settings_dir() -> Path:
    """Return the folder where settings.json should live.

    When running from source, that is the project root (next to app.py).
    When packaged with PyInstaller, it is the folder containing PhotoStamp.exe
    so settings persist after the app closes.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


_SETTINGS_PATH = _settings_dir() / "settings.json"

_VALID_ALIGNMENTS = {"left", "center", "right"}
_VALID_BAND_POSITIONS = {"top", "bottom", "left", "right"}
_VALID_DATE_SOURCES = {item.value for item in DateSource}
_VALID_DATE_FORMATS = {item.value for item in DateDisplayFormat}
_VALID_EXPORT_SIZE_MODES = {item.value for item in ExportSizeMode}
_VALID_EXPORT_FILE_TYPES = {item.value for item in ExportFileType}


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
    enable_date_line: bool = False
    date_source: str = DateSource.NONE.value
    batch_date: str = ""
    date_display_format: str = DateDisplayFormat.LONG.value
    custom_date_format: str = "%B %d, %Y"
    remove_detected_date: bool = True
    date_font_size_auto: bool = True
    date_font_size: int = 24
    date_color: str = "#000000"
    show_background_band: bool = True
    band_position: str = "bottom"
    band_size: int = 15
    band_color: str = "#ffffff"
    band_opacity: int = 100
    export_size_mode: str = ExportSizeMode.ORIGINAL.value
    export_width: int = 1600
    export_height: int = 1200
    export_file_type: str = ExportFileType.ORIGINAL.value


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
        enable_date_line=_bool(raw.get("enable_date_line"), defaults.enable_date_line),
        date_source=_choice(
            raw.get("date_source"), _VALID_DATE_SOURCES, defaults.date_source
        ),
        batch_date=_str_allow_blank(raw.get("batch_date"), defaults.batch_date),
        date_display_format=_choice(
            raw.get("date_display_format"),
            _VALID_DATE_FORMATS,
            defaults.date_display_format,
        ),
        custom_date_format=_str(
            raw.get("custom_date_format"), defaults.custom_date_format
        ),
        remove_detected_date=_bool(
            raw.get("remove_detected_date"), defaults.remove_detected_date
        ),
        date_font_size_auto=_bool(
            raw.get("date_font_size_auto"), defaults.date_font_size_auto
        ),
        date_font_size=_int_in_range(
            raw.get("date_font_size"), 6, 300, defaults.date_font_size
        ),
        date_color=_hex_color(raw.get("date_color"), defaults.date_color),
        show_background_band=_bool(
            raw.get("show_background_band", raw.get("band_enabled")),
            defaults.show_background_band,
        ),
        band_position=_choice(
            raw.get("band_position"), _VALID_BAND_POSITIONS, defaults.band_position
        ),
        band_size=_int_in_range(raw.get("band_size"), 3, 50, defaults.band_size),
        band_color=_hex_color(raw.get("band_color"), defaults.band_color),
        band_opacity=_int_in_range(raw.get("band_opacity"), 0, 100, defaults.band_opacity),
        export_size_mode=_choice(
            raw.get("export_size_mode"),
            _VALID_EXPORT_SIZE_MODES,
            defaults.export_size_mode,
        ),
        export_width=_int_in_range(raw.get("export_width"), 1, 50000, defaults.export_width),
        export_height=_int_in_range(raw.get("export_height"), 1, 50000, defaults.export_height),
        export_file_type=_choice(
            raw.get("export_file_type"),
            _VALID_EXPORT_FILE_TYPES,
            defaults.export_file_type,
        ),
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


def _str_allow_blank(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


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
