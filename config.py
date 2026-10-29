from __future__ import annotations

import json
import copy
import os
import sys
from pathlib import Path
from typing import Any

APP_NAME = "GlassTranslator"

if os.environ.get("GLASSTRANSLATOR_PORTABLE", "").strip() == "1":
    # Portable launcher keeps settings/history beside the executable.
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
    "theme": "روشن",
    "toolbar_orientation": "horizontal",
    # The toolbar follows the application theme; retained for migration compatibility.
    "toolbar_style": "theme",
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
    "online_proxy": "",
    "lmstudio_base_url": "http://127.0.0.1:1234/v1",
    "lmstudio_model": "",
    "offline_source": "en",
    "offline_target": "fa",
}

THEMES: dict[str, dict[str, str]] = {
    "روشن": {
        "background": "#F5F7FA",
        "panel": "#FFFFFF",
        "text": "#20242B",
        "muted": "#687180",
        "border": "#D7DDE5",
        "separator": "#E7EBF0",
        "toolbar": "#FFFFFF",
        "accent": "#356AE6",
    },
    "تاریک": {
        "background": "#171A20",
        "panel": "#222731",
        "text": "#F1F4F8",
        "muted": "#A6AFBD",
        "border": "#414957",
        "separator": "#333A46",
        "toolbar": "#222731",
        "accent": "#8BAEFF",
    },
}

# Old settings files used six theme names. Map them to the closest of the two supported modes.
_THEME_MIGRATIONS = {
    "light": "روشن",
    "dark": "تاریک",
    "ivory glass": "روشن",
    "arctic glass": "روشن",
    "amethyst glass": "روشن",
    "warm sand": "روشن",
    "obsidian": "تاریک",
    "forest glass": "تاریک",
}

MODE_NAMES = {
    "online": "Online",
    "local": "Local AI",
    "offline": "Offline",
}


def load_settings() -> dict[str, Any]:
    # Nested defaults (notably ``glossary``) must not be shared between calls.
    # Otherwise a caller mutating one loaded settings object can silently mutate
    # the defaults used by later loads in the same process.
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    try:
        if SETTINGS_PATH.exists():
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass

    theme = str(settings.get("theme", DEFAULT_SETTINGS["theme"])).strip()
    if theme not in THEMES:
        settings["theme"] = _THEME_MIGRATIONS.get(theme.casefold(), DEFAULT_SETTINGS["theme"])
    # Old installations used an independent toolbar appearance. The professional UI now
    # keeps the toolbar synchronized with the selected application theme.
    settings["toolbar_style"] = "theme"
    if settings.get("mode") not in MODE_NAMES:
        settings["mode"] = DEFAULT_SETTINGS["mode"]
    # This release intentionally exposes Google Translate as the only online provider.
    settings["online_provider"] = "google"
    for retired_key in (
        "libretranslate_url", "libretranslate_api_key",
        "microsoft_translator_endpoint", "microsoft_translator_key",
        "microsoft_translator_region",
    ):
        settings.pop(retired_key, None)
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    normalized = dict(settings)
    theme = str(normalized.get("theme", DEFAULT_SETTINGS["theme"])).strip()
    if theme not in THEMES:
        normalized["theme"] = _THEME_MIGRATIONS.get(theme.casefold(), DEFAULT_SETTINGS["theme"])
    normalized["toolbar_style"] = "theme"
    normalized["online_provider"] = "google"
    for retired_key in (
        "libretranslate_url", "libretranslate_api_key",
        "microsoft_translator_endpoint", "microsoft_translator_key",
        "microsoft_translator_region",
    ):
        normalized.pop(retired_key, None)
    temp_path = SETTINGS_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(SETTINGS_PATH)


def ensure_app_dir() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
