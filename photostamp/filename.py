"""Derive stamp text from image filenames."""


def stamp_text_from_filename(filename: str, *, title_case: bool = False) -> str:
    """Return display text from a filename (no extension).

    Strips the extension, replaces underscores and dashes with spaces,
    and collapses extra whitespace.
    """
    raise NotImplementedError
