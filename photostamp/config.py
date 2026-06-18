"""Stamp settings and defaults."""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class BandPosition(Enum):
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


class TextAlignment(Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class DateSource(Enum):
    AUTO = "auto"
    BATCH = "batch"
    MANUAL = "manual"
    FILENAME = "filename"
    NONE = "none"


class DateDisplayFormat(Enum):
    LONG = "long"
    SHORT_MONTH = "short_month"
    NUMERIC = "numeric"
    NUMERIC_SHORT = "numeric_short"
    ISO = "iso"
    DAY_MONTH = "day_month"
    CUSTOM = "custom"


class ExportSizeMode(Enum):
    ORIGINAL = "original"
    WIDTH = "width"
    HEIGHT = "height"
    FIT_BOX = "fit_box"
    EXACT = "exact"


class ExportFileType(Enum):
    ORIGINAL = "original"
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
DEFAULT_OUTPUT_FOLDER_NAME = "PhotoStamp Output"
DEFAULT_FONT_FAMILY = "Arial"


@dataclass
class StampSettings:
    """User-configurable stamp appearance."""

    # Text
    font_family: str = DEFAULT_FONT_FAMILY
    font_size: int | None = None  # None = auto-fit to band
    text_color: Tuple[int, int, int] = (0, 0, 0)
    text_alignment: TextAlignment = TextAlignment.CENTER
    title_case: bool = False

    # Optional second line
    enable_date_line: bool = False
    date_source: DateSource = DateSource.NONE
    batch_date: str = ""
    date_display_format: DateDisplayFormat = DateDisplayFormat.LONG
    custom_date_format: str = "%B %d, %Y"
    remove_detected_date: bool = True
    date_font_size: int | None = None  # None = 80% of name font size
    date_color: Tuple[int, int, int] | None = None  # None = text_color

    # Stamp area / background band. The area controls placement even when the
    # background rectangle is hidden.
    show_background_band: bool = True
    band_position: BandPosition = BandPosition.BOTTOM
    band_size_ratio: float = 0.15  # fraction of image dimension along band axis
    band_color: Tuple[int, int, int] = (255, 255, 255)
    band_opacity: float = 1.0  # 0.0 = transparent, 1.0 = opaque

    # Export
    export_size_mode: ExportSizeMode = ExportSizeMode.ORIGINAL
    export_width: int = 1600
    export_height: int = 1200
    export_file_type: ExportFileType = ExportFileType.ORIGINAL
