# Z-Library Wrapper

A simple desktop app to search and download books from Z-Library. Type in the
search bar, filter by **author, title, publish year, publisher, and format**,
and download with one click. Runs on **Windows and macOS**.

Built on the open-source [`zlibrary`](https://github.com/sertraline/zlibrary)
library (GPL-3.0).

---

## Quick start (run from source)

You need **Python 3.10+**.

```bash
pip install -r requirements.txt
cd src
python run.py            # or:  python -m zlibgui
```

On first run it creates a config file and tells you where — fill in your
Z-Library email and password, then start it again.

---

## Configuration

Credentials live in a plain `config.ini` you edit **once**. The app looks for it at:

| OS       | Location                                                        |
|----------|-----------------------------------------------------------------|
| Windows  | `%APPDATA%\ZLibraryWrapper\config.ini`                          |
| macOS    | `~/Library/Application Support/ZLibraryWrapper/config.ini`       |

(You can override the location with the `Z_LIBRARY_CONFIG` environment variable.)

```ini
[credentials]
email = you@example.com
password = your_password

[settings]
download_dir =            ; blank = your OS Downloads folder
default_count = 25        ; results per search (1-100)
default_format =          ; blank | PDF | EPUB | MOBI | ...
```

The password is stored in plain text on disk (only readable by your user
account). **Do not commit your real `config.ini`** — it's git-ignored, and
`config.ini.example` is only a template. Keep real credentials out of the
example file.

---

## Building a desktop app + installer

PyInstaller is **not** a cross-compiler — build on the OS you're targeting.

### One command (recommended)

`build.py` detects your OS and does the right thing:

```bash
python build.py            # Windows: build exe | macOS: build the DMG
python build.py --install  # Windows: also install + add a Desktop shortcut
python build.py --clean    # rebuild from scratch
```

Or just double-click **`build.bat`** (Windows, builds + installs) / run
**`bash build.sh`** (macOS, builds the DMG). On Windows the build runs in a temp
folder outside OneDrive to avoid sync file-locks, then moves the result into
`dist/`.

The per-OS details below are equivalent to what `build.py` runs.

### Windows

```powershell
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File packaging\install.ps1
```

This builds `dist\ZLibraryWrapper\`, copies it to
`%LOCALAPPDATA%\Programs\ZLibraryWrapper`, and creates a **Desktop** and
**Start Menu** shortcut called *Z-Library*. (You can also just double-click
`packaging\install.bat`.)

### macOS

You must run this **on a Mac** (PyInstaller can't build a macOS app from
Windows). Copy the project folder over, then:

```bash
python3 -m pip install -r requirements.txt
bash packaging/install.sh
```

That script:
1. regenerates a crisp macOS icon (`assets/icon.icns`) via `iconutil`,
2. builds `dist/ZLibraryWrapper.app`,
3. copies it to `/Applications` (or `~/Applications` without admin rights),
4. clears the Gatekeeper quarantine flag, and
5. puts a *Z-Library* alias on your Desktop.

Then edit `~/Library/Application Support/ZLibraryWrapper/config.ini` with your
credentials and launch it.

> **Gatekeeper note:** the app is unsigned, so the first time you may still need
> to right-click it → **Open** → **Open**. Signing/notarization would be needed
> for wider distribution (out of scope here).

To build the `.app` without installing: `python3 -m PyInstaller packaging/app.spec`.

### One-click DMG (recommended for macOS)

To produce a drag-to-Applications installer disk image:

```bash
python3 -m pip install -r requirements.txt
bash packaging/build_dmg.sh
```

This builds the app (if needed) and packages it into **`dist/ZLibraryWrapper.dmg`**.
Open the DMG and drag **Z-Library** into the **Applications** shortcut — that's
the whole install. Then set your credentials in
`~/Library/Application Support/ZLibraryWrapper/config.ini`.

For a nicely laid-out DMG window (app icon on the left, Applications on the
right), install `create-dmg` first: `brew install create-dmg`. Without it the
script falls back to a plain but fully working DMG via `hdiutil`.

> First launch of the unsigned app may need a right-click → **Open** → **Open**.

### The app icon

`assets/icon.png/.ico/.icns` are committed and already wired into the build. To
change the design, edit and re-run `python packaging/make_icon.py` (and, on a
Mac, `bash packaging/make_icns.sh` for the sharpest `.icns`).

---

## How the filters work

- **Author / Title** — combined into the Z-Library search query.
- **Publish year (from / to)** and **Format** — sent as native search filters.
- **Publisher / Edition** — Z-Library doesn't expose these in search results,
  so when you fill them in the app fetches each result's detail page and filters
  locally. That's a bit slower (throttled to 5 at a time) but keeps the UI
  responsive; results stream in as they're found. Leave those two blank for the
  fastest searches.

## Notes & limits

- Z-Library enforces a **daily download limit** per account; the status bar
  shows how many you've used.
- Searching and downloading require a valid Z-Library account (set in the config).
- Scientific-articles search is intentionally not included.

## How it handles Z-Library's quirks

Z-Library changes its frontend often and gates pages behind a "Checking your
browser…" interstitial, so the raw `zlibrary` library alone can't search or
download against the current site. This app adds a thin resilience layer on top
of it (all in `src/zlibgui/`):

- **`challenge.py`** solves the site's proof-of-work "browser check" and injects
  the resulting cookies into the session; it re-solves automatically if the
  check reappears mid-session.
- **`detail.py`** parses book detail pages (author, year, publisher, edition,
  format, download link) directly, so we don't depend on the library's
  detail parser keeping up with the site.
- **`patches.py`** neutralises a crash in the library's search parser on
  non-Latin book titles (Windows).
- **`net.py`** forces the reliable stdlib DNS resolver (the async one fails on
  some Windows setups).

If Z-Library changes its markup again, the selectors in `detail.py` and the
challenge logic in `challenge.py` are where you'd adjust.

## Project layout

```
src/zlibgui/        the app (config, backend async engine, UI, downloader)
packaging/          PyInstaller spec + install scripts (Windows & macOS)
config.ini.example  config template
```
