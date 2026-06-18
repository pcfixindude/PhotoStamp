"""Export resizing and output-format helpers."""

from pathlib import Path

from PIL import Image

from photostamp.config import ExportFileType, ExportSizeMode, StampSettings


_EXTENSIONS = {
    ExportFileType.JPEG: ".jpg",
    ExportFileType.PNG: ".png",
    ExportFileType.WEBP: ".webp",
}


def prepare_for_export(image: Image.Image, settings: StampSettings) -> Image.Image:
    """Resize *image* for export before stamping.

    Resizing happens before stamping so the band thickness, auto font size, and
    text placement are all calculated against the final output dimensions.
    """
    mode = settings.export_size_mode
    width = max(1, int(settings.export_width))
    height = max(1, int(settings.export_height))

    if mode == ExportSizeMode.ORIGINAL:
        return image.copy()

    src_w, src_h = image.size
    if mode == ExportSizeMode.WIDTH:
        ratio = width / src_w
        size = (width, max(1, round(src_h * ratio)))
    elif mode == ExportSizeMode.HEIGHT:
        ratio = height / src_h
        size = (max(1, round(src_w * ratio)), height)
    elif mode == ExportSizeMode.FIT_BOX:
        ratio = min(width / src_w, height / src_h)
        size = (max(1, round(src_w * ratio)), max(1, round(src_h * ratio)))
    else:  # ExportSizeMode.EXACT
        # Exact dimensions intentionally may change aspect ratio.
        size = (width, height)

    return image.resize(size, Image.LANCZOS)


def output_path_for(source_path: Path, output_dir: Path, settings: StampSettings) -> Path:
    """Return a duplicate-safe output path with the configured extension."""
    ext = source_path.suffix
    if settings.export_file_type != ExportFileType.ORIGINAL:
        ext = _EXTENSIONS[settings.export_file_type]

    candidate = output_dir / f"{source_path.stem}{ext}"
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = output_dir / f"{source_path.stem} ({index}){ext}"
        if not candidate.exists():
            return candidate
        index += 1


def save_exported_image(
    image: Image.Image,
    output_path: Path,
    settings: StampSettings,
) -> None:
    """Save *image* using the requested export file type/extension."""
    file_type = settings.export_file_type
    if file_type == ExportFileType.ORIGINAL:
        ext = output_path.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            file_type = ExportFileType.JPEG
        elif ext == ".png":
            file_type = ExportFileType.PNG
        elif ext == ".webp":
            file_type = ExportFileType.WEBP
        else:
            image.save(output_path)
            return

    if file_type == ExportFileType.JPEG:
        # JPEG cannot store alpha; flatten/convert to RGB before saving.
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGB")
        image.save(output_path, "JPEG", quality=95, optimize=True)
    elif file_type == ExportFileType.PNG:
        image.save(output_path, "PNG", optimize=True)
    elif file_type == ExportFileType.WEBP:
        image.save(output_path, "WEBP", quality=95)
