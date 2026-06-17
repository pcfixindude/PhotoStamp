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

    # Band
    band_enabled: bool = True
    band_position: BandPosition = BandPosition.BOTTOM
    band_size_ratio: float = 0.15  # fraction of image dimension along band axis
    band_color: Tuple[int, int, int] = (255, 255, 255)
    band_opacity: float = 1.0  # 0.0 = transparent, 1.0 = opaque
