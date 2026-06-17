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
from photostamp.config import BandPosition, StampSettings, TextAlignment
from photostamp.filename import stamp_text_from_filename
from photostamp.gui.preview import PreviewPanel
from photostamp.stamping import stamp_image


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMMON_FONTS = [
    "Arial",
    "Helvetica",
    "Times New Roman",
    "Georgia",
    "Verdana",
    "Trebuchet MS",
    "Impact",
    "Courier New",
    "Tahoma",
    "Comic Sans MS",
]

CONTROLS_WIDTH = 300  # pixels


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

        self._init_vars()
        self._build_ui()
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
        self._font_family = tk.StringVar(value="Arial")
        self._font_size_auto = tk.BooleanVar(value=True)
        self._font_size = tk.IntVar(value=32)
        self._text_color = tk.StringVar(value="#000000")
        self._text_align = tk.StringVar(value="center")

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

        # Font family
        ttk.Label(parent, text="Font:").grid(row=r, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            parent, textvariable=self._font_family,
            values=COMMON_FONTS, width=14,
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

    def _get_settings(self) -> StampSettings:
        """Read all control variables and return a StampSettings instance."""
        return StampSettings(
            font_family=self._font_family.get(),
            font_size=None if self._font_size_auto.get() else self._font_size.get(),
            text_color=_hex_to_rgb(self._text_color.get()),
            text_alignment=TextAlignment(self._text_align.get()),
            title_case=self._title_case.get(),
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

        first = images[0]
        settings = self._get_settings()

        try:
            with Image.open(first) as img:
                img.load()
                text = stamp_text_from_filename(first.name, title_case=settings.title_case)
                stamped = stamp_image(img, text, settings)

            self._preview_panel.show(stamped)
            self._status_var.set(f"Preview: {first.name}")
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

        def worker() -> None:
            def on_progress(current: int, total: int, message: str) -> None:
                pct = int(current / total * 100) if total else 0
                self._queue.put(("progress", pct, message))

            result = process_folder(
                input_folder, output_folder, settings, on_progress=on_progress
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
        self._status_var.set(summary)

        if result.errors:
            error_text = "\n".join(result.errors[:10])
            if len(result.errors) > 10:
                error_text += f"\n…and {len(result.errors) - 10} more."
            messagebox.showwarning(
                "Completed with Errors",
                f"{result.processed} photo(s) stamped.\n\nErrors:\n{error_text}",
                parent=self,
            )
        else:
            messagebox.showinfo(
                "Batch Complete",
                f"{result.processed} photo(s) stamped successfully.",
                parent=self,
            )


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
