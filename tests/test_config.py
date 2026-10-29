from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config


class ConfigThemeTests(unittest.TestCase):
    def test_loaded_settings_do_not_share_mutable_defaults(self):
        first = config.load_settings()
        first["glossary"]["example"] = "value"
        second = config.load_settings()
        self.assertNotIn("example", second["glossary"])
        self.assertNotIn("example", config.DEFAULT_SETTINGS["glossary"])

    def test_only_two_themes_are_exposed(self):
        self.assertEqual(set(config.THEMES), {"روشن", "تاریک"})

    def test_old_light_theme_is_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text(json.dumps({"theme": "Ivory Glass"}), encoding="utf-8")
            with patch("config.SETTINGS_PATH", settings_path):
                settings = config.load_settings()
            self.assertEqual(settings["theme"], "روشن")
            self.assertEqual(settings["toolbar_style"], "theme")

    def test_old_dark_theme_is_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text(json.dumps({"theme": "Obsidian"}), encoding="utf-8")
            with patch("config.SETTINGS_PATH", settings_path):
                settings = config.load_settings()
            self.assertEqual(settings["theme"], "تاریک")

    def test_online_provider_is_always_google_and_legacy_credentials_are_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text(json.dumps({
                "online_provider": "microsoft",
                "microsoft_translator_key": "legacy-secret",
                "libretranslate_url": "https://example.test",
            }), encoding="utf-8")
            with patch("config.SETTINGS_PATH", settings_path):
                settings = config.load_settings()
            self.assertEqual(settings["online_provider"], "google")
            self.assertNotIn("microsoft_translator_key", settings)
            self.assertNotIn("libretranslate_url", settings)

    def test_save_settings_persists_google_only_and_removes_legacy_provider_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / "settings.json"
            with patch("config.BASE_DIR", root), patch("config.SETTINGS_PATH", settings_path):
                config.save_settings({
                    "theme": "تاریک",
                    "online_provider": "microsoft",
                    "microsoft_translator_key": "legacy-secret",
                    "libretranslate_api_key": "legacy-secret-2",
                })
            saved = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["online_provider"], "google")
            self.assertNotIn("microsoft_translator_key", saved)
            self.assertNotIn("libretranslate_api_key", saved)


if __name__ == "__main__":
    unittest.main()
