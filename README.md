# PhotoStamp

Local batch photo-stamping utility. Select a folder of images, derive stamp text from each filename, and save stamped copies — originals are never modified.

Works fully offline. No cloud APIs, no internet required.

---

## Requirements

- Python 3.10 or later
- macOS or Windows
- Tkinter (included with the standard Python installer on Windows and macOS)

---

## Setup and run (macOS)

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py
```

---

## Setup and run (Windows)

These steps assume you are using **Command Prompt** or **PowerShell** in the project folder.

### 1. Install Python on Windows

1. Download Python from [python.org/downloads](https://www.python.org/downloads/).
2. Run the installer.
3. On the first screen, check **“Add python.exe to PATH”**.
4. Click **“Customize installation”** and make sure **tcl/tk and IDLE** is enabled (needed for the GUI).
5. Finish the install.

To confirm Python is available, open a new Command Prompt and run:

```bat
python --version
```

You should see something like `Python 3.12.x`.

### 2. Create a virtual environment

Open Command Prompt in the PhotoStamp project folder:

```bat
python -m venv .venv
.venv\Scripts\activate
```

Your prompt should now start with `(.venv)`.

### 3. Install requirements

```bat
pip install -r requirements.txt
```

### 4. Run the app

```bat
python app.py
```

The PhotoStamp window should open. If it does not, see [Troubleshooting](#troubleshooting) below.

---

## Basic usage

1. **Select Input Folder** — click *Browse…* next to "Input" and choose the folder containing your photos.
2. **Select Output Folder** *(optional)* — click *Browse…* next to "Output". If you skip this, stamped copies are saved to a `PhotoStamp Output` subfolder inside the input folder.
3. **Adjust settings** as needed (see below).
4. **Preview** — click *Preview First Image* to see how the stamp looks before committing.
5. **Stamp** — click *Stamp All Photos* to process the entire folder. A progress bar and status message track the run. Any errors are reported at the end without stopping the batch.

### Saved settings

PhotoStamp remembers your preferences in a local `settings.json` file.

- **Running from source:** `settings.json` is saved in the project folder (next to `app.py`).
- **Running the built `.exe`:** `settings.json` is saved in the same folder as `PhotoStamp.exe`.

Settings are loaded when the app starts and saved when you close the app or finish a batch stamp.

Saved items include last input/output folders, title-case preference, font, text options, date-line options, and band options. Image data is never stored.

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

### Optional date line

PhotoStamp can add a second line under the name with the date the picture was taken.

In the **Date Line** section:

1. Check **Enable date line**.
2. Choose a **Source**.
3. Choose a **Format**.
4. Click **Preview First Image** to confirm the layout before stamping.

The date line uses the same font family by default, with an automatically smaller size. You can set a separate date font size and date color if needed. Automatic sizing shrinks both lines so they fit inside the existing band when possible.

#### Date sources

| Source | What it does |
|---|---|
| Auto-detect per image | Reads EXIF `DateTimeOriginal`, then EXIF `DateTimeDigitized`; falls back to file created timestamp when available, then modified timestamp |
| Use one batch date | Uses the same date for every photo |
| Manually assign per image | Uses the editable **This image** date field while previewing; use Previous / Next to move through images |
| Extract date from filename | Detects a date at the end of the filename and uses it as the date line |
| No date line | Disables the second line |

File created timestamps are not always the true photo-taken date. They can change when photos are copied, downloaded, exported, or synced. EXIF dates are preferred when available.

#### Batch/manual date entry

The batch date and manual per-image date fields accept common formats such as:

- `01/31/2026`
- `2026-01-31`
- `Jan 31, 2026`
- `January 31, 2026`

Manual per-image dates are stored in memory for the current app session and are not written to `settings.json`.

#### Filename date examples

When **Extract date from filename** is selected, PhotoStamp looks for conservative date patterns at the end of the name:

| Filename | Name line | Date line |
|---|---|---|
| `Joe Smith 013126.jpg` | `Joe Smith` | `January 31, 2026` |
| `Joe Smith 01-31-26.jpg` | `Joe Smith` | `January 31, 2026` |
| `Joe Smith 01_31_2026.jpg` | `Joe Smith` | `January 31, 2026` |
| `Joe Smith 2026-01-31.jpg` | `Joe Smith` | `January 31, 2026` |
| `Joe Smith 20260131.jpg` | `Joe Smith` | `January 31, 2026` |
| `Joe Smith Jan 31 2026.jpg` | `Joe Smith` | `January 31, 2026` |
| `Joe Smith January 31, 2026.jpg` | `Joe Smith` | `January 31, 2026` |

The option **Remove detected date from displayed name** is on by default. Two-digit years use this cutoff: `00`-`69` means `2000`-`2069`, and `70`-`99` means `1970`-`1999`.

#### Date display formats

Available date display formats:

- `January 31, 2026`
- `Jan 31, 2026`
- `01/31/2026`
- `1/31/26`
- `2026-01-31`
- `31 Jan 2026`
- Custom Python `strftime` format, such as `%B %d, %Y`, `%m/%d/%Y`, or `%Y-%m-%d`

If the custom format is blank or invalid, PhotoStamp falls back to `January 31, 2026`.

### Supported formats

`.jpg` · `.jpeg` · `.png` · `.webp` · `.bmp`

---

## Building a Windows executable (PyInstaller)

These steps create a single `PhotoStamp.exe` you can share with other Windows users. They do not need Python installed to run the `.exe`.

PhotoStamp does not bundle any extra image or font files. It uses system fonts already on the computer (Arial on Windows when available). PyInstaller automatically includes the `photostamp` Python package through normal imports.

### 1. Prepare the build environment

On Windows, in the project folder with the virtual environment activated:

```bat
pip install -r requirements-build.txt
```

This installs Pillow (runtime) and PyInstaller (build tool only).

### 2. Build the executable

```bat
pyinstaller --onefile --windowed --name "PhotoStamp" app.py
```

What the flags mean:

| Flag | Purpose |
|---|---|
| `--onefile` | Bundle everything into one `PhotoStamp.exe` |
| `--windowed` | No black console window behind the GUI |
| `--name "PhotoStamp"` | Name the output executable `PhotoStamp.exe` |
| `app.py` | Entry point |

### 3. Find the built app

After a successful build:

```
dist\PhotoStamp.exe
```

You can copy `PhotoStamp.exe` to any folder and double-click it to run. A `settings.json` file will appear next to the `.exe` the first time settings are saved.

Build artifacts also appear in:

- `build\` — temporary build files (safe to delete)
- `PhotoStamp.spec` — PyInstaller spec file (created automatically; listed in `.gitignore`)

### 4. Rebuild after code changes

```bat
pyinstaller --onefile --windowed --name "PhotoStamp" app.py
```

Or, once `PhotoStamp.spec` exists:

```bat
pyinstaller PhotoStamp.spec
```

---

## Troubleshooting

### The app does not open

**Running from source**

1. Make sure the virtual environment is activated: `.venv\Scripts\activate`
2. Run from the project folder: `python app.py`
3. If nothing appears, run without `--windowed` to see error messages:

   ```bat
   python app.py
   ```

   Any Python traceback will print in the terminal.

**Running the built `.exe`**

1. Try running `PhotoStamp.exe` from Command Prompt so errors are visible:

   ```bat
   dist\PhotoStamp.exe
   ```

2. Rebuild on the same Windows machine where you plan to use the app.
3. Make sure antivirus did not quarantine the file (see below).

### Missing Pillow / `ModuleNotFoundError: No module named 'PIL'`

Install dependencies inside the activated virtual environment:

```bat
.venv\Scripts\activate
pip install -r requirements.txt
```

Then run again with `python app.py`.

If this happens during a PyInstaller build, install build requirements first:

```bat
pip install -r requirements-build.txt
```

### Font fallback / stamp text looks wrong

PhotoStamp prefers **Arial** on Windows (`C:\Windows\Fonts\arial.ttf`). If Arial is missing, the app falls back to another system font automatically. It should not crash.

- On Windows, Arial is normally pre-installed.
- You can pick a different font from the **Font** dropdown in the app.
- If text looks too small, turn off **Auto** font size and set a manual size.

### Windows Defender warning on unsigned `.exe`

PyInstaller builds are not code-signed by default. Windows may show **“Windows protected your PC”** or **SmartScreen** the first time you run `PhotoStamp.exe`.

This is common for small/local apps that are not signed with a commercial certificate. To run the app:

1. Click **More info**
2. Click **Run anyway**

Only run `.exe` files from sources you trust. For development, building the `.exe` yourself on your own machine is the safest option.

### Tkinter / GUI not available

If you see an error about `_tkinter` or `No module named 'tkinter'`, reinstall Python and enable **tcl/tk and IDLE** during setup. Tkinter is required for the desktop window.

---

## Project layout

```
PhotoStamp/
├── app.py                     # Entry point
├── photostamp/
│   ├── config.py              # StampSettings dataclass + enums + defaults
│   ├── filename.py            # Filename → stamp text
│   ├── date_utils.py          # Date detection, parsing, and formatting
│   ├── fonts.py               # Cross-platform font discovery
│   ├── stamping.py            # Pillow: draw band + text, save
│   ├── batch.py               # Folder scan + batch loop
│   ├── settings_store.py      # Load/save settings.json
│   └── gui/
│       ├── main_window.py     # Main Tkinter window + all controls
│       └── preview.py         # Canvas-based preview panel widget
├── requirements.txt           # Runtime dependencies (Pillow)
├── requirements-build.txt     # Build dependencies (adds PyInstaller)
└── README.md
```

---

## License

TBD
