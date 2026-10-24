# Glass Translator v0.2.6 — Source Release

This is the initial public source release of Glass Translator v0.2.6.

## Included

- Floating Windows UI with light/dark appearance and glass-style translation panel.
- Screen-region capture and EasyOCR-based text recognition.
- Online translation backend, LM Studio local AI backend, and Argos English-to-Persian offline backend.
- Translation history, glossary, cache, setup scripts, offline-model installer/checker, and automated tests.

## Before running

- Windows 10/11 x64 and Python 3.11 x64 are required to run this source package.
- Run `setup_windows.bat`, then `install_offline_model.bat`, `check_offline_model.bat`, and `run_windows.bat` in that order.
- The first setup requires internet access to install dependencies and download required models.
- An executable, bundled model files, and a Python-free installer are not included in this source release.

## Notes

- Google Translate integration relies on an unofficial web endpoint and may be affected by rate limits or service changes.
- The Local AI backend requires LM Studio and a model running locally.
- The Offline backend requires the Argos English-to-Persian package to be installed first.
