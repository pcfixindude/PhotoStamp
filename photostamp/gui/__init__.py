"""Tkinter GUI for PhotoStamp."""


def run_app() -> None:
    """Launch the main application window."""
    from photostamp.gui.main_window import PhotoStampApp

    app = PhotoStampApp()
    app.mainloop()
