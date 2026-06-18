"""Main application window for PhotoStamp."""

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Optional

from PIL import Image

from photostamp.batch import BatchResult, iter_images, process_folder
from photostamp.config import (
    BandPosition,
    DateDisplayFormat,
    DateSource,
    StampSettings,
    TextAlignment,
)
from photostamp.date_utils import resolve_stamp_text
from photostamp.fonts import list_available_fonts
from photostamp.gui.preview import PreviewPanel
from photostamp.settings_store import UserSettings, load_settings, save_settings
from photostamp.stamping import stamp_image


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Populated at import time by scanning known font paths on the current OS.
# Fonts that cannot be found are omitted; the user may still type any name.
_AVAILABLE_FONTS: list[str] = list_available_fonts()

CONTROLS_WIDTH = 300  # pixels

DATE_SOURCE_LABELS = {
    "No date line": DateSource.NONE.value,
    "Auto-detect per image": DateSource.AUTO.value,
    "Use one batch date": DateSource.BATCH.value,
    "Manually assign per image": DateSource.MANUAL.value,
    "Extract date from filename": DateSource.FILENAME.value,
}
DATE_SOURCE_VALUES = {v: k for k, v in DATE_SOURCE_LABELS.items()}

DATE_FORMAT_LABELS = {
    "January 31, 2026": DateDisplayFormat.LONG.value,
    "Jan 31, 2026": DateDisplayFormat.SHORT_MONTH.value,
    "01/31/2026": DateDisplayFormat.NUMERIC.value,
    "1/31/26": DateDisplayFormat.NUMERIC_SHORT.value,
    "2026-01-31": DateDisplayFormat.ISO.value,
    "31 Jan 2026": DateDisplayFormat.DAY_MONTH.value,
    "Custom format": DateDisplayFormat.CUSTOM.value,
}
DATE_FORMAT_VALUES = {v: k for k, v in DATE_FORMAT_LABELS.items()}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _short_path(path: Path, max_len: int = 38) -> str:
    s = str(path)
    return s if len(s) <= max_len else "…" + s[-(max_len - 1):]


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class PhotoStampApp(tk.Tk):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("PhotoStamp")
        self.minsize(860, 580)

        # Runtime state
        self._input_folder: Optional[Path] = None
        self._output_folder: Optional[Path] = None
        self._queue: queue.Queue = queue.Queue()
        self._preview_images: list[Path] = []
        self._preview_index = 0
        self._manual_dates: dict[str, str] = {}
        self._loading_manual_date = False

        self._init_vars()
        self._build_ui()
        self._load_saved_settings()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.geometry("1100x680")

    # ------------------------------------------------------------------
    # Variable initialisation
    # ------------------------------------------------------------------

    def _init_vars(self) -> None:
        """Create all tkinter variables with sensible defaults."""
        # Folder display strings
        self._input_display = tk.StringVar(value="No folder selected")
        self._output_display = tk.StringVar(value="Default (inside input folder)")

        # Text settings
        self._title_case = tk.BooleanVar(value=False)
        # Use the first detected font (Arial if available, else best alternative).
        default_font = _AVAILABLE_FONTS[0] if _AVAILABLE_FONTS else "Arial"
        self._font_family = tk.StringVar(value=default_font)
        self._font_size_auto = tk.BooleanVar(value=True)
        self._font_size = tk.IntVar(value=32)
        self._text_color = tk.StringVar(value="#000000")
        self._text_align = tk.StringVar(value="center")

        # Optional date line settings
        self._date_line_enabled = tk.BooleanVar(value=False)
        self._date_source = tk.StringVar(value=DATE_SOURCE_VALUES[DateSource.NONE.value])
        self._batch_date = tk.StringVar(value="")
        self._date_display_format = tk.StringVar(
            value=DATE_FORMAT_VALUES[DateDisplayFormat.LONG.value]
        )
        self._custom_date_format = tk.StringVar(value="%B %d, %Y")
        self._remove_detected_date = tk.BooleanVar(value=True)
        self._date_font_size_auto = tk.BooleanVar(value=True)
        self._date_font_size = tk.IntVar(value=24)
        self._date_color = tk.StringVar(value="#000000")
        self._manual_date = tk.StringVar(value="")

        # Band settings
        self._band_enabled = tk.BooleanVar(value=True)
        self._band_position = tk.StringVar(value="bottom")
        self._band_size = tk.IntVar(value=15)
        self._band_color = tk.StringVar(value="#ffffff")
        self._band_opacity = tk.IntVar(value=100)

        # Status / progress
        self._status_var = tk.StringVar(value="Ready.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Root grid: content row expands, bottom bar does not
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        content = ttk.Frame(self)
        content.grid(row=0, column=0, sticky="nsew")
        content.rowconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        # Left controls panel (fixed width)
        left_outer = ttk.Frame(content, width=CONTROLS_WIDTH)
        left_outer.grid(row=0, column=0, sticky="ns")
        left_outer.grid_propagate(False)
        self._build_controls(left_outer)

        ttk.Separator(content, orient="vertical").grid(row=0, column=0, sticky="nse")

        # Right preview panel (expands)
        right_outer = ttk.Frame(content)
        right_outer.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        right_outer.rowconfigure(1, weight=1)
        right_outer.columnconfigure(0, weight=1)
        self._build_preview_area(right_outer)

        # Bottom bar (progress + status)
        self._build_bottom_bar()

    def _build_controls(self, parent: ttk.Frame) -> None:
        """Scrollable left panel containing all settings controls."""
        inner = _make_scrollable_frame(parent)
        inner.columnconfigure(0, weight=1)

        sections = [
            ("Folders", self._build_folder_section),
            ("Text",    self._build_text_section),
            ("Date Line", self._build_date_section),
            ("Band",    self._build_band_section),
        ]
        for row, (label, builder) in enumerate(sections):
            frame = ttk.LabelFrame(inner, text=label, padding=8)
            frame.grid(row=row, column=0, sticky="ew", padx=6, pady=(6, 2))
            frame.columnconfigure(1, weight=1)
            builder(frame)

        # Action buttons
        btn_frame = ttk.Frame(inner, padding=(6, 4, 6, 8))
        btn_frame.grid(row=len(sections), column=0, sticky="ew")
        btn_frame.columnconfigure(0, weight=1)

        self._preview_btn = ttk.Button(
            btn_frame, text="Preview First Image",
            command=self._preview_first_image,
        )
        self._preview_btn.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self._run_btn = ttk.Button(
            btn_frame, text="Stamp All Photos",
            command=self._start_batch,
        )
        self._run_btn.grid(row=1, column=0, sticky="ew")

    # --- Section builders ---

    def _build_folder_section(self, parent: ttk.Frame) -> None:
        r = 0
        ttk.Label(parent, text="Input:").grid(row=r, column=0, sticky="w")
        ttk.Label(
            parent, textvariable=self._input_display,
            anchor="w", foreground="gray", wraplength=160,
        ).grid(row=r, column=1, sticky="ew", padx=(4, 0))
        r += 1
        ttk.Button(
            parent, text="Browse…", command=self._browse_input,
        ).grid(row=r, column=0, columnspan=2, sticky="w", pady=(2, 8))
        r += 1

        ttk.Label(parent, text="Output:").grid(row=r, column=0, sticky="w")
        ttk.Label(
            parent, textvariable=self._output_display,
            anchor="w", foreground="gray", wraplength=160,
        ).grid(row=r, column=1, sticky="ew", padx=(4, 0))
        r += 1
        btn_row = ttk.Frame(parent)
        btn_row.grid(row=r, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Button(btn_row, text="Browse…", command=self._browse_output).pack(side="left", padx=(0, 4))
        ttk.Button(btn_row, text="Clear",   command=self._clear_output).pack(side="left")

    def _build_text_section(self, parent: ttk.Frame) -> None:
        r = 0
        ttk.Checkbutton(
            parent, text="Title Case", variable=self._title_case,
        ).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        # Font family — values come from fonts actually detected on this system.
        # The user can also type any font name; load_font() falls back gracefully.
        ttk.Label(parent, text="Font:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            parent, textvariable=self._font_family,
            values=_AVAILABLE_FONTS, width=14,
        ).grid(row=r, column=1, sticky="ew", pady=(6, 0))
        r += 1

        # Font size with Auto toggle
        size_row = ttk.Frame(parent)
        size_row.grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(size_row, text="Size:").pack(side="left")
        ttk.Checkbutton(
            size_row, text="Auto", variable=self._font_size_auto,
        ).pack(side="left", padx=(6, 0))
        self._size_spin = ttk.Spinbox(
            size_row, from_=6, to=300, textvariable=self._font_size, width=5,
        )
        self._size_spin.pack(side="left", padx=(6, 0))

        def _toggle_size_spin(*_):
            self._size_spin.config(
                state="disabled" if self._font_size_auto.get() else "normal"
            )

        self._font_size_auto.trace_add("write", _toggle_size_spin)
        _toggle_size_spin()
        r += 1

        # Text color
        ttk.Label(parent, text="Color:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        _make_color_row(
            parent, self._text_color, "Text Color", self,
        ).grid(row=r, column=1, sticky="w", pady=(6, 0))
        r += 1

        # Alignment
        ttk.Label(parent, text="Align:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        align_frame = ttk.Frame(parent)
        align_frame.grid(row=r, column=1, sticky="w", pady=(6, 0))
        for val, lbl in [("left", "L"), ("center", "C"), ("right", "R")]:
            ttk.Radiobutton(
                align_frame, text=lbl, variable=self._text_align, value=val,
            ).pack(side="left")

    def _build_date_section(self, parent: ttk.Frame) -> None:
        r = 0
        ttk.Checkbutton(
            parent,
            text="Enable date line",
            variable=self._date_line_enabled,
            command=self._sync_date_controls,
        ).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        ttk.Label(parent, text="Source:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        self._date_source_combo = ttk.Combobox(
            parent,
            textvariable=self._date_source,
            values=list(DATE_SOURCE_LABELS.keys()),
            state="readonly",
            width=18,
        )
        self._date_source_combo.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        self._date_source_combo.bind("<<ComboboxSelected>>", lambda _e: self._sync_date_controls())
        r += 1

        ttk.Label(parent, text="Batch date:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        self._batch_date_entry = ttk.Entry(parent, textvariable=self._batch_date, width=18)
        self._batch_date_entry.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        r += 1

        ttk.Label(parent, text="Format:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        self._date_format_combo = ttk.Combobox(
            parent,
            textvariable=self._date_display_format,
            values=list(DATE_FORMAT_LABELS.keys()),
            state="readonly",
            width=18,
        )
        self._date_format_combo.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        self._date_format_combo.bind("<<ComboboxSelected>>", lambda _e: self._sync_date_controls())
        r += 1

        ttk.Label(parent, text="Custom:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        self._custom_date_entry = ttk.Entry(
            parent, textvariable=self._custom_date_format, width=18
        )
        self._custom_date_entry.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        r += 1

        ttk.Checkbutton(
            parent,
            text="Remove detected date from name",
            variable=self._remove_detected_date,
        ).grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
        r += 1

        date_size_row = ttk.Frame(parent)
        date_size_row.grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(date_size_row, text="Date size:").pack(side="left")
        ttk.Checkbutton(
            date_size_row,
            text="Auto",
            variable=self._date_font_size_auto,
            command=self._sync_date_controls,
        ).pack(side="left", padx=(6, 0))
        self._date_size_spin = ttk.Spinbox(
            date_size_row,
            from_=6,
            to=300,
            textvariable=self._date_font_size,
            width=5,
        )
        self._date_size_spin.pack(side="left", padx=(6, 0))
        r += 1

        ttk.Label(parent, text="Date color:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        _make_color_row(
            parent, self._date_color, "Date Text Color", self,
        ).grid(row=r, column=1, sticky="w", pady=(6, 0))
        r += 1

        ttk.Label(parent, text="This image:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        self._manual_date_entry = ttk.Entry(parent, textvariable=self._manual_date, width=18)
        self._manual_date_entry.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        self._manual_date.trace_add("write", self._on_manual_date_changed)
        r += 1

        nav = ttk.Frame(parent)
        nav.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        nav.columnconfigure(0, weight=1)
        nav.columnconfigure(1, weight=1)
        self._prev_btn = ttk.Button(nav, text="Previous", command=self._preview_previous_image)
        self._prev_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        self._next_btn = ttk.Button(nav, text="Next", command=self._preview_next_image)
        self._next_btn.grid(row=0, column=1, sticky="ew", padx=(2, 0))

        self._sync_date_controls()

    def _build_band_section(self, parent: ttk.Frame) -> None:
        r = 0
        ttk.Checkbutton(
            parent, text="Band Enabled", variable=self._band_enabled,
        ).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        # Position
        ttk.Label(parent, text="Position:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            parent, textvariable=self._band_position,
            values=["bottom", "top", "left", "right"],
            state="readonly", width=8,
        ).grid(row=r, column=1, sticky="w", pady=(6, 0))
        r += 1

        # Size slider
        ttk.Label(parent, text="Size:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        size_frame = ttk.Frame(parent)
        size_frame.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        self._band_size_lbl = ttk.Label(size_frame, text="15%", width=4, anchor="e")
        self._band_size_lbl.pack(side="right")
        ttk.Scale(
            size_frame, from_=3, to=50,
            variable=self._band_size, orient="horizontal",
            command=lambda _: self._band_size_lbl.config(
                text=f"{self._band_size.get()}%"
            ),
        ).pack(side="left", fill="x", expand=True)
        r += 1

        # Band color
        ttk.Label(parent, text="Color:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        _make_color_row(
            parent, self._band_color, "Band Color", self,
        ).grid(row=r, column=1, sticky="w", pady=(6, 0))
        r += 1

        # Opacity slider
        ttk.Label(parent, text="Opacity:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        op_frame = ttk.Frame(parent)
        op_frame.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        self._opacity_lbl = ttk.Label(op_frame, text="100%", width=4, anchor="e")
        self._opacity_lbl.pack(side="right")
        ttk.Scale(
            op_frame, from_=0, to=100,
            variable=self._band_opacity, orient="horizontal",
            command=lambda _: self._opacity_lbl.config(
                text=f"{self._band_opacity.get()}%"
            ),
        ).pack(side="left", fill="x", expand=True)

    def _build_preview_area(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent, text="Preview", anchor="center",
            font=("", 10, "bold"),
        ).grid(row=0, column=0, sticky="ew", pady=(2, 2))
        self._preview_panel = PreviewPanel(parent)
        self._preview_panel.grid(row=1, column=0, sticky="nsew")

    def _build_bottom_bar(self) -> None:
        bar = ttk.Frame(self, padding=(6, 2, 6, 6))
        bar.grid(row=1, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)

        self._progress_var = tk.IntVar(value=0)
        self._progress = ttk.Progressbar(bar, variable=self._progress_var, maximum=100)
        self._progress.grid(row=0, column=0, sticky="ew", pady=(0, 2))

        ttk.Label(bar, textvariable=self._status_var, anchor="w").grid(
            row=1, column=0, sticky="ew"
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _date_source_value(self) -> str:
        return DATE_SOURCE_LABELS.get(self._date_source.get(), DateSource.NONE.value)

    def _date_format_value(self) -> str:
        return DATE_FORMAT_LABELS.get(
            self._date_display_format.get(), DateDisplayFormat.LONG.value
        )

    def _sync_date_controls(self) -> None:
        """Enable/disable date inputs based on the selected mode."""
        enabled = self._date_line_enabled.get()
        source = self._date_source_value()
        fmt = self._date_format_value()

        if enabled and source == DateSource.NONE.value:
            self._date_source.set(DATE_SOURCE_VALUES[DateSource.AUTO.value])
            source = DateSource.AUTO.value
        elif not enabled:
            self._date_source.set(DATE_SOURCE_VALUES[DateSource.NONE.value])
            source = DateSource.NONE.value

        batch_state = "normal" if enabled and source == DateSource.BATCH.value else "disabled"
        # A manual value for the current preview image overrides any source,
        # so keep this field available whenever the date line is enabled.
        manual_state = "normal" if enabled and source != DateSource.NONE.value else "disabled"
        custom_state = (
            "normal"
            if enabled and fmt == DateDisplayFormat.CUSTOM.value
            else "disabled"
        )
        date_size_state = "disabled" if self._date_font_size_auto.get() else "normal"

        for widget, state in (
            (getattr(self, "_batch_date_entry", None), batch_state),
            (getattr(self, "_manual_date_entry", None), manual_state),
            (getattr(self, "_custom_date_entry", None), custom_state),
            (getattr(self, "_date_size_spin", None), date_size_state),
        ):
            if widget is not None:
                widget.config(state=state)

    def _on_manual_date_changed(self, *_args: object) -> None:
        if self._loading_manual_date or not self._preview_images:
            return
        current = self._preview_images[self._preview_index]
        value = self._manual_date.get().strip()
        if value:
            self._manual_dates[str(current)] = value
        else:
            self._manual_dates.pop(str(current), None)

    def _collect_user_settings(self) -> UserSettings:
        """Snapshot current UI state for persistence."""
        return UserSettings(
            input_folder=str(self._input_folder) if self._input_folder else None,
            output_folder=str(self._output_folder) if self._output_folder else None,
            title_case=self._title_case.get(),
            font_family=self._font_family.get(),
            font_size_auto=self._font_size_auto.get(),
            font_size=self._font_size.get(),
            text_color=self._text_color.get(),
            text_alignment=self._text_align.get(),
            enable_date_line=self._date_line_enabled.get(),
            date_source=self._date_source_value(),
            batch_date=self._batch_date.get(),
            date_display_format=self._date_format_value(),
            custom_date_format=self._custom_date_format.get(),
            remove_detected_date=self._remove_detected_date.get(),
            date_font_size_auto=self._date_font_size_auto.get(),
            date_font_size=self._date_font_size.get(),
            date_color=self._date_color.get(),
            band_enabled=self._band_enabled.get(),
            band_position=self._band_position.get(),
            band_size=self._band_size.get(),
            band_color=self._band_color.get(),
            band_opacity=self._band_opacity.get(),
        )

    def _apply_user_settings(self, saved: UserSettings) -> None:
        """Restore UI controls from *saved*."""
        if saved.input_folder:
            self._input_folder = Path(saved.input_folder)
            self._input_display.set(_short_path(self._input_folder))
        else:
            self._input_folder = None
            self._input_display.set("No folder selected")

        if saved.output_folder:
            self._output_folder = Path(saved.output_folder)
            self._output_display.set(_short_path(self._output_folder))
        else:
            self._output_folder = None
            self._output_display.set("Default (inside input folder)")

        self._title_case.set(saved.title_case)
        self._font_family.set(saved.font_family)
        self._font_size_auto.set(saved.font_size_auto)
        self._font_size.set(saved.font_size)
        self._text_color.set(saved.text_color)
        self._text_align.set(saved.text_alignment)
        self._date_line_enabled.set(saved.enable_date_line)
        self._date_source.set(DATE_SOURCE_VALUES.get(saved.date_source, "No date line"))
        self._batch_date.set(saved.batch_date)
        self._date_display_format.set(
            DATE_FORMAT_VALUES.get(saved.date_display_format, "January 31, 2026")
        )
        self._custom_date_format.set(saved.custom_date_format)
        self._remove_detected_date.set(saved.remove_detected_date)
        self._date_font_size_auto.set(saved.date_font_size_auto)
        self._date_font_size.set(saved.date_font_size)
        self._date_color.set(saved.date_color)
        self._band_enabled.set(saved.band_enabled)
        self._band_position.set(saved.band_position)
        self._band_size.set(saved.band_size)
        self._band_color.set(saved.band_color)
        self._band_opacity.set(saved.band_opacity)

        # Keep slider labels in sync with restored values.
        if hasattr(self, "_band_size_lbl"):
            self._band_size_lbl.config(text=f"{saved.band_size}%")
        if hasattr(self, "_opacity_lbl"):
            self._opacity_lbl.config(text=f"{saved.band_opacity}%")
        if hasattr(self, "_date_size_spin"):
            self._sync_date_controls()

    def _load_saved_settings(self) -> None:
        """Load preferences from settings.json, using defaults on any error."""
        self._apply_user_settings(load_settings())

    def _persist_settings(self) -> None:
        """Write current preferences to settings.json (best-effort)."""
        save_settings(self._collect_user_settings())

    def _on_close(self) -> None:
        """Save settings and exit."""
        self._persist_settings()
        self.destroy()

    def _get_settings(self) -> StampSettings:
        """Read all control variables and return a StampSettings instance."""
        return StampSettings(
            font_family=self._font_family.get(),
            font_size=None if self._font_size_auto.get() else self._font_size.get(),
            text_color=_hex_to_rgb(self._text_color.get()),
            text_alignment=TextAlignment(self._text_align.get()),
            title_case=self._title_case.get(),
            enable_date_line=self._date_line_enabled.get(),
            date_source=DateSource(self._date_source_value()),
            batch_date=self._batch_date.get(),
            date_display_format=DateDisplayFormat(self._date_format_value()),
            custom_date_format=self._custom_date_format.get(),
            remove_detected_date=self._remove_detected_date.get(),
            date_font_size=None
            if self._date_font_size_auto.get()
            else self._date_font_size.get(),
            date_color=_hex_to_rgb(self._date_color.get()),
            band_enabled=self._band_enabled.get(),
            band_position=BandPosition(self._band_position.get()),
            band_size_ratio=self._band_size.get() / 100,
            band_color=_hex_to_rgb(self._band_color.get()),
            band_opacity=self._band_opacity.get() / 100,
        )

    # ------------------------------------------------------------------
    # Folder browsing
    # ------------------------------------------------------------------

    def _browse_input(self) -> None:
        folder = filedialog.askdirectory(title="Select Input Folder", parent=self)
        if folder:
            self._input_folder = Path(folder)
            self._input_display.set(_short_path(self._input_folder))
            self._preview_images = []
            self._preview_index = 0
            self._status_var.set("Input folder selected.")

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(title="Select Output Folder", parent=self)
        if folder:
            self._output_folder = Path(folder)
            self._output_display.set(_short_path(self._output_folder))

    def _clear_output(self) -> None:
        self._output_folder = None
        self._output_display.set("Default (inside input folder)")

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _preview_first_image(self) -> None:
        if self._load_preview_images():
            self._preview_index = 0
            self._show_current_preview()

    def _preview_previous_image(self) -> None:
        if not self._load_preview_images():
            return
        self._preview_index = max(0, self._preview_index - 1)
        self._show_current_preview()

    def _preview_next_image(self) -> None:
        if not self._load_preview_images():
            return
        self._preview_index = min(len(self._preview_images) - 1, self._preview_index + 1)
        self._show_current_preview()

    def _load_preview_images(self) -> bool:
        if not self._input_folder or not self._input_folder.is_dir():
            messagebox.showwarning(
                "No Input Folder", "Please select an input folder first.", parent=self
            )
            return False

        self._preview_images = list(iter_images(self._input_folder))
        if not self._preview_images:
            messagebox.showinfo(
                "No Images",
                "No supported images were found in the selected folder.",
                parent=self,
            )
            return False

        self._preview_index = min(self._preview_index, len(self._preview_images) - 1)
        return True

    def _show_current_preview(self) -> None:
        current = self._preview_images[self._preview_index]
        self._loading_manual_date = True
        self._manual_date.set(self._manual_dates.get(str(current), ""))
        self._loading_manual_date = False
        settings = self._get_settings()

        try:
            with Image.open(current) as img:
                img.load()
                stamp_text = resolve_stamp_text(
                    current, img, settings, manual_dates=self._manual_dates
                )
                stamped = stamp_image(
                    img,
                    stamp_text.name,
                    settings,
                    date_text=stamp_text.date_text,
                )

            self._preview_panel.show(stamped)
            status = f"Preview {self._preview_index + 1}/{len(self._preview_images)}: {current.name}"
            if stamp_text.warning:
                status += f" ({stamp_text.warning})"
            self._status_var.set(status)
        except Exception as exc:
            messagebox.showerror("Preview Error", str(exc), parent=self)

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def _start_batch(self) -> None:
        if not self._input_folder or not self._input_folder.is_dir():
            messagebox.showwarning(
                "No Input Folder", "Please select an input folder first.", parent=self
            )
            return

        images = list(iter_images(self._input_folder))
        if not images:
            messagebox.showinfo(
                "No Images",
                "No supported images were found in the selected folder.",
                parent=self,
            )
            return

        self._run_btn.config(state="disabled")
        self._preview_btn.config(state="disabled")
        self._progress_var.set(0)
        self._status_var.set("Starting…")

        settings = self._get_settings()
        input_folder = self._input_folder
        output_folder = self._output_folder
        manual_dates = dict(self._manual_dates)

        def worker() -> None:
            def on_progress(current: int, total: int, message: str) -> None:
                pct = int(current / total * 100) if total else 0
                self._queue.put(("progress", pct, message))

            result = process_folder(
                input_folder,
                output_folder,
                settings,
                manual_dates=manual_dates,
                on_progress=on_progress,
            )
            self._queue.put(("done", result))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_queue()

    def _poll_queue(self) -> None:
        """Drain the progress queue and schedule the next poll."""
        try:
            while True:
                item = self._queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, pct, msg = item
                    self._progress_var.set(pct)
                    self._status_var.set(msg)
                elif kind == "done":
                    self._on_batch_done(item[1])
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _on_batch_done(self, result: BatchResult) -> None:
        self._progress_var.set(100)
        self._run_btn.config(state="normal")
        self._preview_btn.config(state="normal")

        summary = f"Done — {result.processed} photo(s) stamped."
        if result.errors:
            summary += f"  {len(result.errors)} error(s)."
        if result.warnings:
            summary += f"  {len(result.warnings)} warning(s)."
        self._status_var.set(summary)

        if result.errors or result.warnings:
            issues = result.errors + result.warnings
            error_text = "\n".join(issues[:10])
            if len(issues) > 10:
                error_text += f"\n…and {len(issues) - 10} more."
            messagebox.showwarning(
                "Completed with Notes",
                f"{result.processed} photo(s) stamped.\n\nNotes:\n{error_text}",
                parent=self,
            )
        else:
            messagebox.showinfo(
                "Batch Complete",
                f"{result.processed} photo(s) stamped successfully.",
                parent=self,
            )

        self._persist_settings()


# ---------------------------------------------------------------------------
# Reusable widget helpers (module-level, not methods)
# ---------------------------------------------------------------------------

def _make_color_row(
    parent: ttk.Frame,
    color_var: tk.StringVar,
    title: str,
    root: tk.Tk,
) -> ttk.Frame:
    """Return a frame with a color swatch label and a 'Choose…' button."""
    frame = ttk.Frame(parent)

    swatch = tk.Label(frame, width=3, relief="groove", cursor="hand2")
    swatch.pack(side="left", padx=(0, 4))

    def _pick() -> None:
        result = colorchooser.askcolor(color=color_var.get(), title=title, parent=root)
        if result and result[1]:
            color_var.set(result[1])

    ttk.Button(frame, text="Choose…", command=_pick).pack(side="left")

    def _update_swatch(*_) -> None:
        try:
            swatch.config(bg=color_var.get())
        except tk.TclError:
            pass

    color_var.trace_add("write", _update_swatch)
    _update_swatch()
    return frame


def _make_scrollable_frame(parent: tk.Widget) -> ttk.Frame:
    """Wrap *parent* with a Canvas + Scrollbar and return the scrollable inner frame."""
    canvas = tk.Canvas(parent, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)

    inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_inner_configure(_e: tk.Event) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(e: tk.Event) -> None:
        canvas.itemconfig(inner_id, width=e.width)

    inner.bind("<Configure>", _on_inner_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    def _on_mousewheel(e: tk.Event) -> None:
        if sys.platform == "darwin":
            canvas.yview_scroll(-1 * int(e.delta), "units")
        else:
            canvas.yview_scroll(-1 * (e.delta // 120), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)

    return inner
