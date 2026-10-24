# Glass Translator

**A lightweight floating English-to-Persian screen translator for Windows.**

Glass Translator lets you select an area of your screen, recognize its English text with OCR, and display a Persian translation in a compact glass-style overlay. The project is designed for desktop use, including games and other applications; compatibility can vary by application and display mode.

[راهنمای فارسی](README_FA.md) · [Release notes](RELEASE_NOTES_v0.2.6.md)

## Features

- Floating toolbar and glass-style translation panel, with light and dark themes.
- Select a screen region and extract text using EasyOCR.
- Three translation backends:
  - **Online:** Google Translate via an unofficial web endpoint, or a compatible LibreTranslate API.
  - **Local AI:** LM Studio using its OpenAI-compatible local API.
  - **Offline:** Argos Translate English-to-Persian package.
- Translation history, search, copy, bookmarks, export, glossary, and translation cache.
- Global shortcuts for opening the panel, OCR selection, and history.

## Current release scope

This is a **source-code release**. It does not include a prebuilt Windows executable, Python runtime, OCR model weights, or the Argos language package. Required packages and models must be installed separately by following the setup steps below. A Python-free installer or fully self-contained portable build is not included in this release.

## Requirements

- Windows 10 or Windows 11, 64-bit.
- Python 3.11, 64-bit, to run the source or build an executable.
- Internet access for installing Python dependencies and downloading the initial language/OCR models.
- Optional: LM Studio with a model loaded and its local server enabled, for the Local AI backend.

After installation, the Argos Offline backend can translate without an internet connection. The Online backend requires internet access; the Local AI backend requires LM Studio to be running locally.

## Run from source

1. Download or clone this repository.
2. Install Python 3.11 x64.
3. Run `setup_windows.bat` and wait for the environment and dependencies to finish installing.
4. Run `install_offline_model.bat` to download and install the English-to-Persian Argos package.
5. Run `check_offline_model.bat` and confirm that the offline model is detected.
6. Run `run_windows.bat` to start Glass Translator.

The app stores its user settings, history, and Argos package under the current Windows user profile (typically `%APPDATA%\GlassTranslator`). OCR model files may also be downloaded by EasyOCR on first use.

## Build a Windows executable

After confirming that the source runs correctly, execute `build_windows_exe.bat`. Build output and packaging details are documented in [README_BUILD_EXE_FA.md](README_BUILD_EXE_FA.md).

The existing build script is not a promise of a fully portable, model-inclusive distribution: the Argos and OCR model files are not automatically bundled into the executable by the current source build. The build must be performed and tested on Windows.

## Tests

Run `test_windows.bat`, or from the project directory use:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Automated tests cover selected translation logic and error handling. Live access to translation services, LM Studio, OCR downloads, and the Argos installation should be tested on the target computer separately.

## Shortcuts

- `Ctrl+Shift+T` — toggle the translation panel
- `Ctrl+Shift+R` — start screen-region OCR
- `Ctrl+Shift+H` — open history

## Limitations and privacy notes

- Screen text is sent to the selected online translation provider when an online backend is used. Do not use the online backend for sensitive information.
- Google Translate uses an unofficial web endpoint in this project; service behavior or rate limits may change without notice.
- Local AI processing depends on the model and server configured in LM Studio.
- Some games or applications, particularly those using exclusive fullscreen, may not work reliably with overlays.

## Contributing and license

Bug reports and pull requests are welcome. Please include Windows version, selected translation backend, and reproducible steps when reporting issues. No license has been selected for this source release yet; until a license is added, standard copyright restrictions apply. Public availability on GitHub alone does not grant permission to redistribute or reuse the code.
