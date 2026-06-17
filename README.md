# PhotoStamp

Local batch photo-stamping utility. Select a folder of images, derive stamp text from each filename, and save stamped copies — originals are never modified.

Works fully offline. No cloud APIs, no internet required.

---

## Requirements

- Python 3.10 or later
- macOS or Windows

---

## Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows (cmd)

# 2. Install dependencies
pip install -r requirements.txt
```

---

## Run

```bash
python app.py
```

---

## Basic usage

1. **Select Input Folder** — click *Browse…* next to "Input" and choose the folder containing your photos.
2. **Select Output Folder** *(optional)* — click *Browse…* next to "Output". If you skip this, stamped copies are saved to a `PhotoStamp Output` subfolder inside the input folder.
3. **Adjust settings** as needed (see below).
4. **Preview** — click *Preview First Image* to see how the stamp looks before committing.
5. **Stamp** — click *Stamp All Photos* to process the entire folder. A progress bar and status message track the run. Any errors are reported at the end without stopping the batch.

### Saved settings

PhotoStamp remembers your preferences in a local `settings.json` file in the project folder. Settings are loaded when the app starts and saved when you close the app or finish a batch stamp.

Saved items include last input/output folders, title-case preference, font, text options, and band options. Image data is never stored.

If `settings.json` is missing or corrupted, the app falls back to defaults and continues normally. The file is listed in `.gitignore` so it is not committed to Git.

### Settings at a glance

| Setting | What it does |
|---|---|
| Title Case | Capitalises the first letter of each word in the stamp text |
| Font | Font family for the stamp text (type or pick from the list) |
| Size / Auto | Font size in pt; leave *Auto* checked to fit the band automatically |
| Color (Text) | Colour of the stamp text |
| Align | Horizontal text alignment: Left / Center / Right |
| Band Enabled | Toggle the coloured band on or off |
| Position | Which edge the band sits on: bottom, top, left, or right |
| Size % | Band thickness as a percentage of the image dimension it spans |
| Color (Band) | Fill colour of the band |
| Opacity | 100 % = fully opaque; 0 % = fully transparent (text-only effect) |

### How stamp text is derived

The stamp text comes from the **filename** (no extension):

- Underscores `_` and dashes `-` are replaced with spaces.
- Extra spaces are trimmed.
- *Title Case* is applied if the checkbox is on.

Examples:

| Filename | Stamp text (default) | Stamp text (Title Case) |
|---|---|---|
| `emma_johnson.jpg` | `emma johnson` | `Emma Johnson` |
| `product-123-blue.png` | `product 123 blue` | `Product 123 Blue` |
| `IMG_0042.jpeg` | `IMG 0042` | `Img 0042` |

### Supported formats

`.jpg` · `.jpeg` · `.png` · `.webp` · `.bmp`

---

## Project layout

```
PhotoStamp/
├── app.py                     # Entry point
├── photostamp/
│   ├── config.py              # StampSettings dataclass + enums + defaults
│   ├── filename.py            # Filename → stamp text
│   ├── stamping.py            # Pillow: draw band + text, save
│   ├── batch.py               # Folder scan + batch loop
│   ├── settings_store.py      # Load/save settings.json
│   └── gui/
│       ├── main_window.py     # Main Tkinter window + all controls
│       └── preview.py         # Canvas-based preview panel widget
├── requirements.txt
└── README.md
```

---

## License

TBD
