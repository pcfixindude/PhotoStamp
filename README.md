# PhotoStamp

Local batch photo-stamping utility. Select a folder of images, derive stamp text from each filename, and save stamped copies without modifying the originals.

Works offline — no cloud APIs or internet services.

## Requirements

- Python 3.10+
- macOS or Windows

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run (once implemented)

```bash
python app.py
```

## Project structure

```
PhotoStamp/
├── app.py                  # Entry point
├── photostamp/
│   ├── config.py           # StampSettings, defaults, enums
│   ├── filename.py         # Filename → stamp text
│   ├── stamping.py         # Pillow draw band + text
│   ├── batch.py            # Folder scan, output path, batch loop
│   └── gui/
│       ├── main_window.py  # Folder pickers, settings, run controls
│       └── preview.py      # Live preview of one image
├── requirements.txt
└── README.md
```

## Version 1 features

| Feature | Module |
|--------|--------|
| Select input / output folders | `gui/main_window.py` |
| Default output: `PhotoStamp Output` inside input | `batch.resolve_output_folder` |
| Formats: jpg, jpeg, png, webp, bmp | `config.SUPPORTED_EXTENSIONS` |
| Stamp text from filename (no extension) | `filename.stamp_text_from_filename` |
| `_` and `-` → spaces, trim whitespace | `filename` |
| Optional title case | `StampSettings.title_case` |
| Never modify originals | `stamping` + `batch` (write copies only) |
| Progress / status | `gui/main_window.py` + `batch.on_progress` |
| Preview one image | `gui/preview.py` |

### Default stamp look

- White band along the bottom (~15% of image height)
- Black Arial text, centered in the band
- Band fully opaque

### Customization (settings panel)

**Text:** font, size, color, alignment (left / center / right), title case

**Band:** enabled, position (top / bottom / left / right), size, color, opacity

## Implementation plan

Build in this order so each step is testable before the GUI wires everything together.

### Phase 1 — Core logic (no GUI)

1. **`filename.py`** — `stamp_text_from_filename("emma_johnson-sponsor.jpg")` → `"emma johnson sponsor"`; optional title case → `"Emma Johnson Sponsor"`.
2. **`stamping.py`** — Given a Pillow `Image` and `StampSettings`:
   - Compute band rectangle from position + `band_size_ratio`
   - Draw semi-opaque band (RGBA overlay when opacity &lt; 1)
   - Load font (Arial with fallback), auto-size if `font_size` is `None`
   - Draw text with alignment inside the band
   - Return a new image object
3. **`batch.py`** — Scan folder, resolve output path, loop: open → stamp → save. Report progress via callback. Skip unsupported files; collect errors without stopping the whole batch.

### Phase 2 — GUI shell

4. **`gui/main_window.py`** — Tkinter window with:
   - Input folder button + path label
   - Output folder button + path label (optional; show resolved default)
   - Settings grouped into Text and Band sections (bound to `StampSettings`)
   - Status label + indeterminate/determinate progress during batch
   - **Preview** button and **Run** button
5. **`gui/preview.py`** — Pick first image in input folder (or let user choose one file), render stamped preview in a `Label` / `Canvas`, update when settings change.

### Phase 3 — Polish

6. Persist last-used folders and settings to a local JSON file (optional, v1.1).
7. Error dialogs for empty folders, missing fonts, write failures.
8. Manual test on macOS; note any Windows font-path differences for Arial.

### Phase 4 — Packaging (later)

9. PyInstaller spec for a single-folder Windows build.
10. Smoke-test on Windows.

## Design notes

- **Generic naming** — UI strings say “stamp text” / “label”, not “child name”, so the same app works for inventory, events, missions, etc.
- **Non-destructive** — Originals are only read; all writes go to the output folder.
- **No sample data required** — The app runs with any user-selected folders; no bundled sample photos.

## License

TBD
