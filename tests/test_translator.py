from __future__ import annotations

import unittest
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import Mock, patch

from translator import (
    TranslationError,
    _normalize_lmstudio_url,
    _translate_google_web,
    _translate_libretranslate,
    _translate_microsoft_translator,
    _microsoft_translator_url,
    _translate_local_ai,
    _translate_offline,
    _refresh_argos_language_cache,
    _configure_argos_search_paths,
    translate_text,
)


class TranslatorTests(unittest.TestCase):
    def test_empty_text_is_rejected(self):
        with self.assertRaisesRegex(TranslationError, "خالی"):
            translate_text("   ", {"mode": "local"})

    def test_lmstudio_url_normalization(self):
        self.assertEqual(_normalize_lmstudio_url("localhost:1234"), "http://localhost:1234/v1")
        self.assertEqual(_normalize_lmstudio_url("http://127.0.0.1:1234/v1/"), "http://127.0.0.1:1234/v1")
        self.assertEqual(
            _normalize_lmstudio_url("http://127.0.0.1:1234/v1/chat/completions"),
            "http://127.0.0.1:1234/v1",
        )

    @patch("translator.requests.get")
    def test_google_web_response_is_joined(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = [[['سلام', 'Hello'], [' دنیا', ' world']], None, 'en']
        mock_get.return_value = response
        self.assertEqual(_translate_google_web("Hello world"), "سلام دنیا")
        self.assertEqual(mock_get.call_args.args[0], "https://translate.googleapis.com/translate_a/single")


    @patch("translator.requests.get")
    def test_google_429_has_clear_rate_limit_message(self, mock_get):
        import requests
        response = Mock()
        response.status_code = 429
        response.headers = {"Retry-After": "30"}
        response.raise_for_status.side_effect = requests.HTTPError("429 Client Error", response=response)
        mock_get.return_value = response
        with self.assertRaisesRegex(TranslationError, "HTTP 429") as caught:
            _translate_google_web("Hello")
        self.assertIn("30 ثانیه", str(caught.exception))
        self.assertIn("Local AI", str(caught.exception))

    @patch("translator.requests.get")
    def test_google_web_passes_optional_proxy(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = [[['سلام', 'Hello']], None, 'en']
        mock_get.return_value = response
        self.assertEqual(_translate_google_web("Hello", {"online_proxy": "127.0.0.1:7890"}), "سلام")
        self.assertEqual(
            mock_get.call_args.kwargs["proxies"],
            {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"},
        )

    @patch("translator._translate_microsoft_translator")
    def test_online_dispatches_to_microsoft_translator(self, mock_microsoft):
        from translator import _translate_online
        mock_microsoft.return_value = "سلام"
        self.assertEqual(
            _translate_online("Hello", {"online_provider": "microsoft", "microsoft_translator_key": "test"}),
            "سلام",
        )
        mock_microsoft.assert_called_once()

    @patch("translator.requests.post")
    def test_microsoft_translator_uses_v3_payload_and_global_endpoint(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = [{"translations": [{"text": "سلام دنیا", "to": "fa"}]}]
        mock_post.return_value = response
        settings = {
            "online_provider": "microsoft",
            "microsoft_translator_key": "test-secret",
            "microsoft_translator_endpoint": "https://api.cognitive.microsofttranslator.com",
        }
        self.assertEqual(_translate_microsoft_translator("Hello world", settings), "سلام دنیا")
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.cognitive.microsofttranslator.com/translate")
        self.assertEqual(kwargs["params"], {"api-version": "3.0", "from": "en", "to": "fa"})
        self.assertEqual(kwargs["json"], [{"Text": "Hello world"}])
        self.assertEqual(kwargs["headers"]["Ocp-Apim-Subscription-Key"], "test-secret")
        self.assertNotIn("Ocp-Apim-Subscription-Region", kwargs["headers"])

    @patch("translator.requests.post")
    def test_microsoft_translator_adds_region_and_supports_custom_resource_endpoint(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = [{"translations": [{"text": "سلام"}]}]
        mock_post.return_value = response
        settings = {
            "microsoft_translator_key": "test-secret",
            "microsoft_translator_endpoint": "https://sample.cognitiveservices.azure.com/translator/text/v3.0/translate?api-version=3.0&from=en&to=fa",
            "microsoft_translator_region": "westeurope",
        }
        self.assertEqual(_translate_microsoft_translator("Hello", settings), "سلام")
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://sample.cognitiveservices.azure.com/translator/text/v3.0/translate")
        self.assertEqual(kwargs["headers"]["Ocp-Apim-Subscription-Region"], "westeurope")

    def test_microsoft_translator_requires_key(self):
        with self.assertRaisesRegex(TranslationError, "کلید Azure"):
            _translate_microsoft_translator("Hello", {})

    def test_microsoft_custom_endpoint_requires_region(self):
        with self.assertRaisesRegex(TranslationError, "منطقه Azure"):
            _translate_microsoft_translator("Hello", {
                "microsoft_translator_key": "test-secret",
                "microsoft_translator_endpoint": "https://sample.cognitiveservices.azure.com",
            })

    def test_microsoft_translator_endpoint_normalization(self):
        self.assertEqual(
            _microsoft_translator_url("https://api.cognitive.microsofttranslator.com"),
            "https://api.cognitive.microsofttranslator.com/translate",
        )
        self.assertEqual(
            _microsoft_translator_url("https://sample.cognitiveservices.azure.com"),
            "https://sample.cognitiveservices.azure.com/translator/text/v3.0/translate",
        )

    @patch("translator.requests.post")
    def test_libretranslate_accepts_base_url(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"translatedText": "سلام"}
        mock_post.return_value = response
        result = _translate_libretranslate("Hello", {"libretranslate_url": "https://example.test"})
        self.assertEqual(result, "سلام")
        self.assertEqual(mock_post.call_args.args[0], "https://example.test/translate")

    def test_offline_translation_object_is_cached(self):
        import sys
        import types

        class FakeTranslation:
            def __init__(self):
                self.calls = 0

            def translate(self, text):
                self.calls += 1
                return "سلام" if text == "Hello" else "خداحافظ"

        fake_translation = FakeTranslation()
        source_language = types.SimpleNamespace(
            code="en", get_translation=lambda target_language: fake_translation
        )
        target_language = types.SimpleNamespace(code="fa")
        fake_translate_module = types.ModuleType("argostranslate.translate")
        discovery_calls = []
        def get_languages():
            discovery_calls.append(True)
            return [source_language, target_language]
        fake_translate_module.get_installed_languages = get_languages
        fake_package_module = types.ModuleType("argostranslate")
        fake_package_module.__path__ = []
        fake_package_module.translate = fake_translate_module

        with patch.dict(sys.modules, {
            "argostranslate": fake_package_module,
            "argostranslate.translate": fake_translate_module,
        }), patch("translator._OFFLINE_TRANSLATION_CACHE", {}):
            self.assertEqual(_translate_offline("Hello", {"offline_source": "en", "offline_target": "fa"}), "سلام")
            self.assertEqual(_translate_offline("Hello", {"offline_source": "en", "offline_target": "fa"}), "سلام")
            self.assertEqual(fake_translation.calls, 2)
            self.assertEqual(len(discovery_calls), 1, "Argos languages/model should only be discovered once per language pair")


    def test_argos_install_and_discovery_share_canonical_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "app-argos-packages"
            legacy = Path(temp_dir) / "old-argos-packages"
            legacy.mkdir()
            fake_settings = types.ModuleType("argostranslate.settings")
            fake_settings.package_data_dir = legacy
            fake_settings.legacy_package_data_dir = legacy
            fake_settings.package_dirs = [legacy]
            fake_argos = types.ModuleType("argostranslate")
            fake_argos.__path__ = []
            env = {
                "ARGOS_PACKAGES_DIR": str(root),
                "ARGOS_PACKAGE_DIR": str(root),
                "ARGOS_TRANSLATE_PACKAGE_DIR": str(root),
            }
            with patch.dict(os.environ, env), patch.dict(sys.modules, {
                "argostranslate": fake_argos,
                "argostranslate.settings": fake_settings,
            }):
                roots = _configure_argos_search_paths()
                self.assertEqual(fake_settings.package_data_dir, root)
                self.assertIn(root, roots)
                self.assertIn(legacy, roots)

    def test_argos_language_cache_refresh_is_supported(self):
        class CachedLanguageFinder:
            def __init__(self):
                self.cleared = 0
            def __call__(self):
                return []
            def cache_clear(self):
                self.cleared += 1
        finder = CachedLanguageFinder()
        argos_translate = type("FakeArgosTranslate", (), {"get_installed_languages": finder})()
        _refresh_argos_language_cache(argos_translate)
        self.assertEqual(finder.cleared, 1)

    @patch("translator.requests.post")
    @patch("translator.requests.get")
    def test_lmstudio_uses_first_loaded_model(self, mock_get, mock_post):
        models_response = Mock()
        models_response.raise_for_status.return_value = None
        models_response.json.return_value = {"data": [{"id": "my-model"}]}
        mock_get.return_value = models_response
        chat_response = Mock()
        chat_response.raise_for_status.return_value = None
        chat_response.json.return_value = {"choices": [{"message": {"content": "سلام"}}]}
        mock_post.return_value = chat_response
        result = _translate_local_ai("Hello", {"lmstudio_base_url": "localhost:1234"})
        self.assertEqual(result, "سلام")
        self.assertEqual(mock_get.call_args.args[0], "http://localhost:1234/v1/models")
        self.assertEqual(mock_post.call_args.args[0], "http://localhost:1234/v1/chat/completions")
        self.assertEqual(mock_post.call_args.kwargs["json"]["model"], "my-model")


if __name__ == "__main__":
    unittest.main()
