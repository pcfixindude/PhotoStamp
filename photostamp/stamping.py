"""Pillow-based image stamping."""

from pathlib import Path

from PIL import Image

from photostamp.config import StampSettings


def stamp_image(image: Image.Image, text: str, settings: StampSettings) -> Image.Image:
    """Return a new stamped copy of *image*; never modifies the input."""
    raise NotImplementedError


def save_stamped_image(
    image: Image.Image,
    output_path: Path,
    *,
    source_format: str | None = None,
) -> None:
    """Write a stamped image to *output_path*, preserving format when possible."""
    raise NotImplementedError
