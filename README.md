# Glass Translator 0.2.7

Glass Translator is a floating Windows screen translator that uses OCR to read English text from a selected screen region and displays a Persian translation.

## Features

- Persian-first right-to-left interface with right-aligned Persian labels and inputs.
- IRANSans / IRANSansX / IRANSansWeb font detection from Windows-installed fonts or `assets/fonts`.
- EasyOCR screen-region recognition.
- Online translation through Google Translate's unofficial web endpoint or a LibreTranslate-compatible API.
- Local AI translation through LM Studio's OpenAI-compatible local server.
- Offline English-to-Persian translation through Argos Translate.
- Translation history, search, glossary, themes, and global hotkeys.

## Run from source

- Windows 10/11 x64
- Python 3.11 x64

Run `setup_windows.bat`, install the offline model with `install_offline_model.bat` if required, and start the app with `run_windows.bat`.

## Build Windows EXE

Run `build_windows_exe.bat` on Windows. It creates `dist/GlassTranslator/GlassTranslator.exe` and a ZIP of the complete application folder. If Inno Setup 6 is installed, it also generates a Windows setup executable with a standard uninstaller. Python is needed on the build machine, not on the computer running the packaged EXE.

The build script bundles locally available Argos and EasyOCR model files when found. To ensure IRANSans works on machines without that font installed, place a font file licensed for redistribution in `assets/fonts` before building. This source package does not contain the font file itself.

See `README_FA.md` for the full Persian guide and `README_BUILD_EXE_FA.md` for build details.
