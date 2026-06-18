"""Batch folder processing."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Optional

from PIL import Image

from photostamp.config import DEFAULT_OUTPUT_FOLDER_NAME, SUPPORTED_EXTENSIONS, StampSettings
from photostamp.date_utils import resolve_stamp_text
from photostamp.exporting import output_path_for, prepare_for_export, save_exported_image
from photostamp.stamping import stamp_image


@dataclass
class BatchResult:
    """Summary of a completed batch run."""

    processed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def iter_images(folder: Path) -> Iterator[Path]:
    """Yield supported image files in *folder* (non-recursive, sorted by name)."""
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def resolve_output_folder(
    input_folder: Path,
    output_folder: Optional[Path],
) -> Path:
    """Return the output folder, creating it if it does not already exist."""
    out = output_folder if output_folder else input_folder / DEFAULT_OUTPUT_FOLDER_NAME
    out.mkdir(parents=True, exist_ok=True)
    return out


def process_folder(
    input_folder: Path,
    output_folder: Optional[Path],
    settings: StampSettings,
    *,
    manual_overrides: Optional[dict[str, dict[str, object]]] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> BatchResult:
    """Stamp every supported image in *input_folder* and save copies to *output_folder*.

    *on_progress* is called as ``on_progress(current, total, message)`` after
    each image so callers can update a progress bar or status label.
    Errors on individual images are collected; the batch always continues.
    """
    result = BatchResult()
    images = list(iter_images(input_folder))
    total = len(images)

    if total == 0:
        return result

    out_dir = resolve_output_folder(input_folder, output_folder)

    for i, img_path in enumerate(images, 1):
        if on_progress:
            on_progress(i, total, f"Processing {img_path.name}  ({i}/{total})")

        try:
            with Image.open(img_path) as img:
                img.load()  # force full decode while file is open
                export_img = prepare_for_export(img, settings)
                stamp_text = resolve_stamp_text(
                    img_path, export_img, settings, manual_overrides=manual_overrides
                )
                if stamp_text.warning:
                    result.warnings.append(stamp_text.warning)
                stamped = stamp_image(
                    export_img,
                    stamp_text.name,
                    settings,
                    date_text=stamp_text.date_text,
                )

            save_exported_image(stamped, output_path_for(img_path, out_dir, settings), settings)
            result.processed += 1

        except Exception as exc:
            result.errors.append(f"{img_path.name}: {exc}")

    if on_progress:
        summary = f"Done — {result.processed} stamped"
        if result.errors:
            summary += f", {len(result.errors)} error(s)"
        if result.warnings:
            summary += f", {len(result.warnings)} warning(s)"
        on_progress(total, total, summary)

    return result
