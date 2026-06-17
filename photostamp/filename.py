"""Derive stamp text from image filenames."""

import os
import re


def stamp_text_from_filename(filename: str, *, title_case: bool = False) -> str:
    """Return display text from a filename.

    Strips the extension, replaces underscores and dashes with spaces,
    and collapses extra whitespace.

    Example:
        "emma_johnson-sponsor.jpg" -> "emma johnson sponsor"
        with title_case=True       -> "Emma Johnson Sponsor"
    """
    stem = os.path.splitext(filename)[0]
    text = stem.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if title_case:
        text = text.title()
    return text
