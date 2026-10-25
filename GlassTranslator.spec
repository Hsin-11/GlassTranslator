# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build for Glass Translator on Windows x64.

Build with the project's active .venv using: python -m PyInstaller --clean --noconfirm GlassTranslator.spec
Model packages are staged by build_windows_exe.bat and bundled when found.
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = Path(SPECPATH).resolve()
ICON = ROOT / "assets" / "glass_translator.ico"

datas = [(str(ROOT / "assets"), "assets")]
# The Windows build script stages model files separately so the source repository
# never needs to include large downloaded model weights.
STAGE = ROOT / "build_staging"
for staged_name, target_name in (
    ("easyocr-models", "assets/easyocr-models"),
    ("argos-packages", "assets/argos-packages"),
):
    staged_path = STAGE / staged_name
    if staged_path.is_dir() and any(staged_path.iterdir()):
        datas.append((str(staged_path), target_name))

binaries = []
hiddenimports = [
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtNetwork", "PySide6.QtSvg",
    "argostranslate", "argostranslate.package", "argostranslate.settings", "argostranslate.translate",
    "easyocr", "torch", "torchvision", "cv2", "numpy", "PIL",
    "mss", "mss.windows", "requests", "pynput", "pynput.keyboard._win32",
]

# Several dependencies are loaded dynamically by OCR, Qt, and keyboard hooks.
# Collect their package data and binary extensions to make a robust onedir build.
for package_name in (
    "easyocr", "torch", "torchvision", "argostranslate", "requests",
    "mss", "numpy", "PIL", "pynput", "cv2",
):
    try:
        package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
        datas.extend(package_datas)
        binaries.extend(package_binaries)
        hiddenimports.extend(package_hiddenimports)
        try:
            datas.extend(copy_metadata(package_name))
        except Exception:
            pass
    except Exception as exc:
        print(f"PyInstaller notice: skipping optional collection for {package_name}: {exc}")

# De-duplicate pairs collected via multiple hooks.
def dedupe_pairs(items):
    unique = []
    seen = set()
    for source, destination in items:
        key = (str(source), str(destination))
        if key not in seen:
            seen.add(key)
            unique.append((str(source), str(destination)))
    return unique

datas = dedupe_pairs(datas)
binaries = dedupe_pairs(binaries)
hiddenimports = sorted(set(hiddenimports))

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib.tests", "pytest", "IPython", "notebook"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GlassTranslator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GlassTranslator",
)
