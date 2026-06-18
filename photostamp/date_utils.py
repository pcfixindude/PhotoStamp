"""Date extraction, parsing, and display formatting for PhotoStamp."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ExifTags

from photostamp.config import DateDisplayFormat, DateSource, StampSettings
from photostamp.filename import stamp_text_from_filename


_EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}
_DATETIME_ORIGINAL = _EXIF_TAGS.get("DateTimeOriginal")
_DATETIME_DIGITIZED = _EXIF_TAGS.get("DateTimeDigitized")

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass
class StampText:
    """Resolved text for a single stamped image."""

    name: str
    date_text: str = ""
    warning: str | None = None
    suggested_name: str = ""
    suggested_date_text: str = ""


@dataclass
class FilenameDate:
    """A detected date at the end of a filename stem."""

    taken_date: date
    name_without_date: str


def resolve_stamp_text(
    image_path: Path,
    image: Image.Image,
    settings: StampSettings,
    manual_overrides: dict[str, dict[str, object]] | None = None,
) -> StampText:
    """Return the name and optional date line for *image_path*."""
    filename_result = extract_date_from_filename(image_path.name)
    suggested_name = (
        filename_result.name_without_date
        if filename_result and settings.remove_detected_date
        else stamp_text_from_filename(image_path.name, title_case=settings.title_case)
    )
    if settings.title_case:
        suggested_name = suggested_name.title()

    override = (manual_overrides or {}).get(str(image_path), {})
    name_override = str(override.get("name_override", "")).strip()
    name = name_override or suggested_name

    if not settings.enable_date_line or settings.date_source == DateSource.NONE:
        return StampText(name=name, suggested_name=suggested_name)

    if bool(override.get("second_line_intentionally_blank", False)):
        return StampText(name=name, suggested_name=suggested_name)

    if "second_line_override" in override:
        # The user-edited second line is treated as display text, not reparsed,
        # so it can be any custom wording they want.
        second = str(override.get("second_line_override", "")).strip()
        return StampText(
            name=name,
            date_text=second,
            suggested_name=suggested_name,
            suggested_date_text=second,
        )

    resolved: date | None = None
    warning: str | None = None

    if settings.date_source == DateSource.BATCH:
        resolved = parse_user_date(settings.batch_date)
        if not resolved:
            warning = f"{image_path.name}: batch date is blank or invalid"
    elif settings.date_source == DateSource.MANUAL:
        warning = f"{image_path.name}: no manual date entered"
    elif settings.date_source == DateSource.FILENAME:
        if filename_result:
            resolved = filename_result.taken_date
        else:
            warning = f"{image_path.name}: no date found at filename ending"
    elif settings.date_source == DateSource.AUTO:
        # Auto-detect intentionally prefers filename endings first. Sponsor and
        # school-photo workflows often encode the intended date in the name, and
        # that should override EXIF/file timestamps when present.
        if filename_result:
            resolved = filename_result.taken_date
        if resolved is None:
            resolved = date_from_exif(image)
        if resolved is None:
            resolved = date_from_file_timestamp(image_path)
        if resolved is None:
            warning = f"{image_path.name}: no date could be detected"

    date_text = format_date(resolved, settings) if resolved else ""
    return StampText(
        name=name,
        date_text=date_text,
        warning=warning,
        suggested_name=suggested_name,
        suggested_date_text=date_text,
    )


def date_from_exif(image: Image.Image) -> date | None:
    """Read EXIF DateTimeOriginal, then DateTimeDigitized, without crashing."""
    try:
        exif = image.getexif()
    except Exception:
        return None
    if not exif:
        return None

    for tag in (_DATETIME_ORIGINAL, _DATETIME_DIGITIZED):
        if tag is None:
            continue
        raw = exif.get(tag)
        parsed = _parse_exif_datetime(raw)
        if parsed:
            return parsed
    return None


def date_from_file_timestamp(path: Path) -> date | None:
    """Return created timestamp when available, then modified timestamp.

    File creation time can vary after copies, downloads, exports, or sync tools,
    so it is only a fallback when embedded EXIF dates are not present.
    """
    try:
        stat = path.stat()
    except OSError:
        return None

    created_timestamp = getattr(stat, "st_birthtime", None)
    if created_timestamp is None and sys.platform == "win32":
        created_timestamp = stat.st_ctime

    for timestamp in (created_timestamp, stat.st_mtime):
        if timestamp:
            try:
                return datetime.fromtimestamp(timestamp).date()
            except (OSError, OverflowError, ValueError):
                continue
    return None


def extract_date_from_filename(filename: str) -> FilenameDate | None:
    """Conservatively detect supported date patterns at the end of a filename."""
    display_stem = stamp_text_from_filename(filename)

    patterns = [
        # January 31, 2026 / Jan 31 2026
        r"(?P<name>.+?)\s+(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),?\s+(?P<year>\d{2,4})$",
        # 2026-01-31 / 2026_01_31
        r"(?P<name>.+?)\s+(?P<year>\d{4})[\s_-]?(?P<month>\d{2})[\s_-]?(?P<day>\d{2})$",
        # 01-31-26 / 01_31_2026 / 01 31 2026
        r"(?P<name>.+?)\s+(?P<month>\d{1,2})[\s_-](?P<day>\d{1,2})[\s_-](?P<year>\d{2,4})$",
        # 013126 (MMDDYY) / 01312026 (MMDDYYYY)
        r"(?P<name>.+?)\s+(?P<digits>\d{6}|\d{8})$",
    ]

    for pattern in patterns:
        match = re.match(pattern, display_stem)
        if not match:
            continue
        parsed = _date_from_match(match)
        if parsed:
            clean_name = re.sub(r"\s+", " ", match.group("name")).strip()
            if clean_name:
                return FilenameDate(parsed, clean_name)
    return None


def parse_user_date(value: str) -> date | None:
    """Parse simple user-entered dates for batch/manual date fields."""
    text = value.strip()
    if not text:
        return None

    for fmt in (
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y-%m-%d",
        "%b %d, %Y",
        "%b %d %Y",
        "%B %d, %Y",
        "%B %d %Y",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    # Reuse filename-ending logic by prefixing a dummy name.
    detected = extract_date_from_filename(f"x {text}.jpg")
    return detected.taken_date if detected else None


def format_date(value: date | None, settings: StampSettings) -> str:
    """Format *value* using the selected display format."""
    if value is None:
        return ""

    fmt = {
        DateDisplayFormat.LONG: "%B %d, %Y",
        DateDisplayFormat.SHORT_MONTH: "%b %d, %Y",
        DateDisplayFormat.NUMERIC: "%m/%d/%Y",
        DateDisplayFormat.NUMERIC_SHORT: "%-m/%-d/%y",
        DateDisplayFormat.ISO: "%Y-%m-%d",
        DateDisplayFormat.DAY_MONTH: "%d %b %Y",
    }.get(settings.date_display_format)

    if settings.date_display_format == DateDisplayFormat.CUSTOM:
        fmt = settings.custom_date_format.strip() or "%B %d, %Y"

    try:
        return _portable_strftime(value, fmt or "%B %d, %Y")
    except (TypeError, ValueError):
        return value.strftime("%B %d, %Y")


def _portable_strftime(value: date, fmt: str) -> str:
    """Handle no-leading-zero day/month formats on Windows and macOS."""
    if sys.platform == "win32":
        # Windows does not support %-m / %-d; use %#m / %#d there.
        fmt = fmt.replace("%-m", "%#m").replace("%-d", "%#d")
    return value.strftime(fmt)


def _parse_exif_datetime(raw: object) -> date | None:
    if not isinstance(raw, str):
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _date_from_match(match: re.Match[str]) -> date | None:
    groups = match.groupdict()
    try:
        if groups.get("digits"):
            digits = groups["digits"]
            # Six digits are MMDDYY. For two-digit years, 00-69 map to
            # 2000-2069 and 70-99 map to 1970-1999.
            if len(digits) == 6:
                month = int(digits[:2])
                day = int(digits[2:4])
                year = _expand_two_digit_year(int(digits[4:]))
            elif digits.startswith(("19", "20")):
                # YYYYMMDD for values like 20260131.
                year = int(digits[:4])
                month = int(digits[4:6])
                day = int(digits[6:])
            else:
                # MMDDYYYY for values like 01312026.
                month = int(digits[:2])
                day = int(digits[2:4])
                year = int(digits[4:])
        else:
            month_raw = groups["month"]
            month = (
                _MONTHS[month_raw.lower()]
                if month_raw.isalpha()
                else int(month_raw)
            )
            day = int(groups["day"])
            year_raw = groups["year"]
            year = (
                _expand_two_digit_year(int(year_raw))
                if len(year_raw) == 2
                else int(year_raw)
            )
        return date(year, month, day)
    except (KeyError, TypeError, ValueError):
        return None


def _expand_two_digit_year(value: int) -> int:
    """Map 00-69 to 2000-2069, and 70-99 to 1970-1999."""
    return 2000 + value if value <= 69 else 1900 + value
