"""Batch folder processing."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from photostamp.config import SUPPORTED_EXTENSIONS, StampSettings


@dataclass
class BatchResult:
    """Summary of a batch run."""

    processed: int = 0
    skipped: int = 0
    errors: list[str] | None = None


def iter_images(folder: Path) -> Iterator[Path]:
    """Yield supported image files in *folder* (non-recursive)."""
    raise NotImplementedError


def resolve_output_folder(input_folder: Path, output_folder: Path | None) -> Path:
    """Return the output folder, creating the default subfolder if needed."""
    raise NotImplementedError


def process_folder(
    input_folder: Path,
    output_folder: Path | None,
    settings: StampSettings,
    *,
    on_progress: Callable[[str], None] | None = None,
) -> BatchResult:
    """Stamp every supported image in *input_folder* and write copies to output."""
    raise NotImplementedError
