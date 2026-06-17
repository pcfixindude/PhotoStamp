"""Preview panel widget — shows a Pillow image scaled to fit the available space."""

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk


_PLACEHOLDER = "Select an input folder, then click\n\"Preview First Image\""


class PreviewPanel(ttk.Frame):
    """Canvas-based widget that displays a stamped image preview."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._canvas = tk.Canvas(self, bg="#1e1e1e", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._photo: ImageTk.PhotoImage | None = None

        # Draw placeholder once the canvas has a real size
        self._canvas.bind("<Configure>", self._on_resize)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self, image: Image.Image) -> None:
        """Display *image* scaled to fit, preserving aspect ratio."""
        self.update_idletasks()
        cw = self._canvas.winfo_width() or 600
        ch = self._canvas.winfo_height() or 400

        ratio = min(cw / image.width, ch / image.height)
        new_w = max(1, int(image.width * ratio))
        new_h = max(1, int(image.height * ratio))

        scaled = image.resize((new_w, new_h), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(scaled)

        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, image=self._photo, anchor="center")

    def clear(self) -> None:
        """Remove the current image and show the placeholder text."""
        self._photo = None
        self._draw_placeholder()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_resize(self, _event: tk.Event) -> None:
        if self._photo is None:
            self._draw_placeholder()

    def _draw_placeholder(self) -> None:
        self._canvas.delete("all")
        cx = self._canvas.winfo_width() // 2
        cy = self._canvas.winfo_height() // 2
        if cx > 1 and cy > 1:
            self._canvas.create_text(
                cx, cy,
                text=_PLACEHOLDER,
                fill="#555555",
                justify="center",
                font=("", 11),
            )
