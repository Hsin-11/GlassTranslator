from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

APP_NAME = "GlassTranslator"

if os.environ.get("GLASSTRANSLATOR_PORTABLE", "").strip() == "1":
    # Portable launcher sets this flag so settings/history stay beside the executable.
    if getattr(sys, "frozen", False):
        _portable_root = Path(sys.executable).resolve().parent
    else:
        _portable_root = Path(__file__).resolve().parent
    BASE_DIR = _portable_root / "data"
elif sys.platform == "win32":
    BASE_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
else:
    BASE_DIR = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / APP_NAME

SETTINGS_PATH = BASE_DIR / "settings.json"
HISTORY_DB_PATH = BASE_DIR / "history.sqlite3"

DEFAULT_SETTINGS: dict[str, Any] = {
    "mode": "local",
    "theme": "Ivory Glass",
    "toolbar_orientation": "horizontal",
    "toolbar_style": "light",
    "toolbar_x": 60,
    "toolbar_y": 70,
    "overlay_x": None,
    "overlay_y": None,
    "overlay_width": 650,
    "overlay_height": 210,
    "opacity": 88,
    "corner_radius": 18,
    "font_size": 17,
    "scan_interval_ms": 700,
    "stable_reads": 2,
    "quality_profile": "balanced",
    "glossary": {},
    "history_persistent": False,
    "online_provider": "google",
    "libretranslate_url": "",
    "online_proxy": "",
    "libretranslate_api_key": "",
    "lmstudio_base_url": "http://127.0.0.1:1234/v1",
    "lmstudio_model": "",
    "offline_source": "en",
    "offline_target": "fa",
}

THEMES: dict[str, dict[str, str]] = {
    "Ivory Glass": {
        "background": "#F0F0ED", "panel": "#FFFFFF", "text": "#171717",
        "muted": "#646464", "border": "#292929", "separator": "#D8D8D4",
        "toolbar": "#FFFFFF", "accent": "#343434",
    },
    "Obsidian": {
        "background": "#141619", "panel": "#202328", "text": "#F3F3F3",
        "muted": "#B0B5BD", "border": "#60656D", "separator": "#41464E",
        "toolbar": "#202328", "accent": "#E5E5E5",
    },
    "Arctic Glass": {
        "background": "#E8EDF0", "panel": "#F6F9FA", "text": "#203443",
        "muted": "#647987", "border": "#526C7C", "separator": "#CFD9DF",
        "toolbar": "#F6F9FA", "accent": "#315064",
    },
    "Forest Glass": {
        "background": "#17201E", "panel": "#222E29", "text": "#E1E9E3",
        "muted": "#A8C3B2", "border": "#6B8C79", "separator": "#46594E",
        "toolbar": "#222E29", "accent": "#B6D1C0",
    },
    "Amethyst Glass": {
        "background": "#F1EAF3", "panel": "#F8F3FA", "text": "#3D2B47",
        "muted": "#856D90", "border": "#72547F", "separator": "#D9C8E0",
        "toolbar": "#F8F3FA", "accent": "#72547F",
    },
    "Warm Sand": {
        "background": "#EDE7DD", "panel": "#F7F2EA", "text": "#3D342C",
        "muted": "#837466", "border": "#766859", "separator": "#D8CEC0",
        "toolbar": "#F7F2EA", "accent": "#766859",
    },
}

MODE_NAMES = {
    "online": "Online",
    "local": "Local AI",
    "offline": "Offline",
}


def load_settings() -> dict[str, Any]:
    settings = DEFAULT_SETTINGS.copy()
    try:
        if SETTINGS_PATH.exists():
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass

    if settings.get("theme") not in THEMES:
        settings["theme"] = DEFAULT_SETTINGS["theme"]
    if settings.get("mode") not in MODE_NAMES:
        settings["mode"] = DEFAULT_SETTINGS["mode"]
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = SETTINGS_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(SETTINGS_PATH)


def ensure_app_dir() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
