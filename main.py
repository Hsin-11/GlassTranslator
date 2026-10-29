from __future__ import annotations

import sys
import re
import json
import hashlib
from collections import deque
from typing import Any
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, QTimer, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from config import MODE_NAMES, THEMES, load_settings, save_settings, ensure_app_dir
from history import HistoryManager
from ocr_worker import OCRWorker
from translator import TranslationError, translate_text
from ui import FloatingToolbar, HistoryDialog, RegionSelector, SettingsDialog, TranslationOverlay


def app_resource_path(relative_path: str) -> Path:
    """Resolve bundled resources in source and PyInstaller builds."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    base = Path(frozen_root) if frozen_root else Path(__file__).resolve().parent
    return base / relative_path




def apply_application_palette(app: QApplication, settings: dict[str, Any] | None = None) -> None:
    """Apply one consistent light/dark palette to native Qt controls and menus."""
    from PySide6.QtGui import QPalette, QColor

    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    selected_theme = (settings or {}).get("theme", "روشن")
    theme = THEMES.get(selected_theme, THEMES["روشن"])
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme["background"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme["panel"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme["background"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(theme["panel"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF" if selected_theme == "روشن" else "#171A20"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme["panel"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme["text"]))
    app.setPalette(palette)
    # Native controls and message boxes inherit the same theme as custom windows.
    app.setStyleSheet(f"""
        QMessageBox {{ background: {theme['background']}; color: {theme['text']}; }}
        QMessageBox QLabel {{ color: {theme['text']}; qproperty-alignment: AlignRight | AlignVCenter; }}
        QMenu {{ background: {theme['panel']}; color: {theme['text']}; border: 1px solid {theme['border']}; }}
        QMenu::item:selected {{ background: {theme['separator']}; }}
    """)


def configure_application_appearance(app: QApplication, settings: dict[str, Any] | None = None) -> str:
    """Configure a Persian-first RTL interface and load the preferred Persian font."""
    apply_application_palette(app, settings)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    fonts_dir = app_resource_path("assets/fonts")
    loaded_families: list[str] = []
    if fonts_dir.is_dir():
        for font_path in sorted(fonts_dir.iterdir()):
            if font_path.suffix.lower() not in {".ttf", ".otf", ".ttc"}:
                continue
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id >= 0:
                loaded_families.extend(QFontDatabase.applicationFontFamilies(font_id))

    font_database = QFontDatabase()
    available_families = list(font_database.families())
    preferred_tokens = ("iransansx", "iransansweb", "iransans")

    def normalized(name: str) -> str:
        return "".join(ch for ch in name.casefold() if ch.isalnum())

    font_family = ""
    for token in preferred_tokens:
        match = next((family for family in loaded_families if token in normalized(family)), None)
        if match:
            font_family = match
            break
    if not font_family:
        for token in preferred_tokens:
            match = next((family for family in available_families if token in normalized(family)), None)
            if match:
                font_family = match
                break
    if not font_family:
        font_family = next((family for family in available_families if normalized(family) == "tahoma"), "")
    if not font_family:
        font_family = next((family for family in available_families if normalized(family) == "segoeui"), "Segoe UI")

    app.setFont(QFont(font_family, 10))
    return font_family


def enable_windows_dpi_awareness() -> None:
    """Keep mouse-selected region coordinates aligned with physical screenshots on Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # PER_MONITOR_AWARE_V2. Older Windows versions may not support this call.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


class TranslationThread(QThread):
    result_ready = Signal(str, str, str, str)
    # original, translated-or-error, mode, error flag

    def __init__(self, original: str, settings: dict[str, Any], context: str = "", parent=None) -> None:
        super().__init__(parent)
        self.original = original
        self.settings = settings.copy()
        self.context = context

    def run(self) -> None:
        mode = str(self.settings.get("mode", "local"))
        try:
            result = translate_text(self.original, self.settings, self.context)
            self.result_ready.emit(self.original, result, mode, "")
        except TranslationError as exc:
            self.result_ready.emit(self.original, str(exc), mode, "error")
        except Exception as exc:
            self.result_ready.emit(self.original, f"خطای پیش‌بینی‌نشده هنگام ترجمه: {exc}", mode, "error")


class ConnectionTestThread(QThread):
    result_ready = Signal(str, bool)

    def __init__(self, settings: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.settings = settings.copy()

    def run(self) -> None:
        mode = str(self.settings.get("mode", "local"))
        try:
            sample = translate_text("Hello. This is a short connection test.", self.settings)
            self.result_ready.emit(
                f"اتصال {MODE_NAMES.get(mode, mode)} برقرار است. نمونه ترجمه: {sample}", True
            )
        except TranslationError as exc:
            self.result_ready.emit(str(exc), False)
        except Exception as exc:
            self.result_ready.emit(f"آزمایش اتصال ناموفق بود: {exc}", False)


class HotkeyBridge(QObject):
    action = Signal(str)


class AppController(QObject):
    MAX_TRANSLATION_QUEUE = 16

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.settings = load_settings()
        ensure_app_dir()
        self.history = HistoryManager(bool(self.settings.get("history_persistent", False)))
        self.toolbar = FloatingToolbar(self.settings)
        self.overlay = TranslationOverlay(self.settings)
        self.region_selector: RegionSelector | None = None
        self.region: dict[str, int] | None = self._valid_region(self.settings.get("region"))
        self.ocr_worker: OCRWorker | None = None
        self.ocr_workers: list[OCRWorker] = []
        self.translation_threads: list[TranslationThread] = []
        self.connection_test_threads: list[ConnectionTestThread] = []
        self.translation_busy = False
        self.translation_queue: deque[tuple[str, dict[str, Any], str]] = deque()
        self.queued_translation_keys: set[tuple[str, str]] = set()
        self.active_translation: tuple[str, dict[str, Any], str] | None = None
        self.active_translation_key: tuple[str, str] | None = None
        self.latest_requested_key: tuple[str, str] | None = None
        # Runtime cache keys include the engine/profile to avoid returning a translation
        # produced by a different online provider or local model for the same source text.
        self.translation_cache: dict[tuple[str, str], str] = {}
        self.overlay_enabled = False
        self.history_dialog: HistoryDialog | None = None
        self.settings_dialog: SettingsDialog | None = None
        self.hotkey_listener = None
        self.hotkey_bridge = HotkeyBridge(self)
        self.hotkey_bridge.action.connect(self._handle_hotkey)
        self._connect_ui()
        self.toolbar.show()
        self._start_global_hotkeys()
        self._refresh_mode_tooltip()

    @staticmethod
    def _valid_region(value: Any) -> dict[str, int] | None:
        if not isinstance(value, dict):
            return None
        try:
            region = {key: int(value[key]) for key in ("left", "top", "width", "height")}
            if region["width"] >= 40 and region["height"] >= 18 and region["left"] >= 0 and region["top"] >= 0:
                return region
        except (KeyError, TypeError, ValueError):
            pass
        return None

    def _connect_ui(self) -> None:
        self.toolbar.region_requested.connect(self.select_region)
        self.toolbar.capture_toggled.connect(self.toggle_capture)
        self.toolbar.overlay_toggled.connect(self.toggle_overlay)
        self.toolbar.history_requested.connect(self.show_history)
        self.toolbar.mode_cycle_requested.connect(self.cycle_mode)
        self.toolbar.theme_toggled.connect(self.toggle_theme)
        self.toolbar.settings_requested.connect(self.show_settings)
        self.toolbar.quit_requested.connect(self.quit_app)
        self.overlay.hide_button.clicked.connect(self._overlay_hidden_from_panel)
        self.app.aboutToQuit.connect(self.shutdown)

    def _start_global_hotkeys(self) -> None:
        try:
            from pynput import keyboard
            self.hotkey_listener = keyboard.GlobalHotKeys({
                "<ctrl>+<shift>+t": lambda: self.hotkey_bridge.action.emit("overlay"),
                "<ctrl>+<shift>+r": lambda: self.hotkey_bridge.action.emit("capture"),
                "<ctrl>+<shift>+h": lambda: self.hotkey_bridge.action.emit("history"),
                "<ctrl>+<shift>+d": lambda: self.hotkey_bridge.action.emit("theme"),
            })
            self.hotkey_listener.start()
        except Exception:
            self.hotkey_listener = None

    def _handle_hotkey(self, action: str) -> None:
        if action == "overlay":
            self.toggle_overlay()
        elif action == "capture":
            self.toggle_capture()
        elif action == "history":
            self.show_history()
        elif action == "theme":
            self.toggle_theme()

    def _refresh_mode_tooltip(self) -> None:
        self.toolbar.apply_settings(self.settings)

    def _set_status(self, text: str) -> None:
        self.overlay.set_status(text)
        self.toolbar.setToolTip(text)

    def select_region(self) -> None:
        if self.region_selector is not None and self.region_selector.isVisible():
            return
        screen = self.app.primaryScreen()
        if screen is None:
            QMessageBox.warning(None, "انتخاب محدوده", "صفحه‌نمایش قابل دسترسی نیست.")
            return
        self.toolbar.hide()
        selector = RegionSelector(screen.geometry(), str(self.settings.get("theme", "روشن")))
        selector.region_selected.connect(self._region_selected)
        selector.cancelled.connect(self._region_cancelled)
        self.region_selector = selector
        selector.show()

    def _region_selected(self, region: dict[str, int]) -> None:
        self.region = self._valid_region(region)
        self.settings["region"] = self.region
        save_settings(self.settings)
        self.toolbar.show()
        self.toolbar.raise_()
        self.region_selector = None
        if self.region:
            self.start_capture()

    def _region_cancelled(self) -> None:
        self.toolbar.show()
        self.toolbar.raise_()
        self.region_selector = None

    def toggle_capture(self) -> None:
        if self.ocr_worker is not None and self.ocr_worker.isRunning():
            self.stop_capture()
        else:
            self.start_capture()

    def start_capture(self) -> None:
        if self.ocr_worker is not None and self.ocr_worker.isRunning():
            return
        if not self.region:
            self.select_region()
            return
        worker = OCRWorker(self.region, self.settings, self)
        worker.text_detected.connect(self._on_text_detected)
        worker.status_changed.connect(self._set_status)
        worker.fatal_error.connect(self._on_ocr_error)
        worker.finished.connect(lambda current=worker: self._cleanup_ocr_worker(current))
        self.ocr_workers.append(worker)
        self.ocr_worker = worker
        self.toolbar.set_capture_active(True)
        self.overlay_enabled = True
        self.overlay.show()
        self.overlay.raise_()
        self.toolbar.set_overlay_visible(True)
        self._set_status("راه‌اندازی OCR…")
        worker.start()

    def stop_capture(self) -> None:
        worker = self.ocr_worker
        self.ocr_worker = None
        if worker is not None and worker.isRunning():
            worker.stop()
        self.toolbar.set_capture_active(False)
        self._set_status("پردازش متوقف شد")

    def _cleanup_ocr_worker(self, worker: OCRWorker) -> None:
        if worker in self.ocr_workers:
            self.ocr_workers.remove(worker)
        if self.ocr_worker is worker:
            self.ocr_worker = None
            self.toolbar.set_capture_active(False)
        worker.deleteLater()

    def toggle_overlay(self) -> None:
        if self.overlay.isVisible():
            self.overlay_enabled = False
            self.overlay.hide()
            self.toolbar.set_overlay_visible(False)
        else:
            self.overlay_enabled = True
            self.overlay.show()
            self.overlay.raise_()
            self.toolbar.set_overlay_visible(True)

    def _overlay_hidden_from_panel(self) -> None:
        self.overlay_enabled = False
        self.toolbar.set_overlay_visible(False)

    def _refresh_overlay_after_mode_change(self) -> None:
        mode_name = MODE_NAMES.get(self.settings.get("mode", "local"), self.settings.get("mode", "local"))
        # Do not leave an error from the previous engine displayed after switching.
        if self.overlay.header_status.text().startswith("خطا"):
            self.overlay.set_translation(
                self.overlay.english_text,
                "موتور ترجمه تغییر کرد؛ برای دریافت ترجمهٔ جدید، متن را دوباره اسکن کن.",
                f"موتور: {mode_name}",
            )
        else:
            self.overlay.set_status(f"موتور: {mode_name}")

    def toggle_theme(self) -> None:
        """Switch the entire app between light and dark without restarting OCR."""
        self.settings["theme"] = "تاریک" if self.settings.get("theme", "روشن") == "روشن" else "روشن"
        apply_application_palette(self.app, self.settings)
        save_settings(self.settings)
        self.toolbar.apply_settings(self.settings)
        self.overlay.apply_settings(self.settings)
        if self.region_selector is not None:
            self.region_selector.theme = THEMES[self.settings["theme"]]
            self.region_selector.update()
        if self.history_dialog is not None:
            self.history_dialog.apply_settings(self.settings)
        if self.settings_dialog is not None and self.settings_dialog.isVisible():
            self.settings_dialog.settings["theme"] = self.settings["theme"]
            self.settings_dialog._apply_theme_style()

    def cycle_mode(self) -> None:
        modes = ["online", "local", "offline"]
        current = self.settings.get("mode", "local")
        index = modes.index(current) if current in modes else 0
        self.settings["mode"] = modes[(index + 1) % len(modes)]
        self.translation_queue.clear()
        self.queued_translation_keys.clear()
        self.latest_requested_key = None
        save_settings(self.settings)
        self.toolbar.apply_settings(self.settings)
        self._refresh_overlay_after_mode_change()
        self._refresh_mode_tooltip()

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.toolbar)
        self.settings_dialog = dialog
        dialog.settings_saved.connect(self._apply_settings)
        dialog.glossary_changed.connect(self._apply_glossary)
        dialog.test_connection_requested.connect(lambda settings, target=dialog: self._test_connection(settings, target))
        dialog.exec()
        self.settings_dialog = None

    def _test_connection(self, settings: dict[str, Any], dialog: SettingsDialog) -> None:
        thread = ConnectionTestThread(settings, self)
        thread.result_ready.connect(dialog.show_test_result)
        thread.finished.connect(lambda current=thread: self._cleanup_connection_test_thread(current))
        self.connection_test_threads.append(thread)
        thread.start()

    def _cleanup_connection_test_thread(self, thread: ConnectionTestThread) -> None:
        if thread in self.connection_test_threads:
            self.connection_test_threads.remove(thread)
        thread.deleteLater()

    def _apply_settings(self, settings: dict[str, Any]) -> None:
        previous_mode = self.settings.get("mode", "local")
        was_persistent = bool(self.settings.get("history_persistent", False))
        was_capturing = self.ocr_worker is not None and self.ocr_worker.isRunning()
        # Preserve geometry that the user may have changed since the last settings save.
        settings["toolbar_x"] = self.toolbar.x()
        settings["toolbar_y"] = self.toolbar.y()
        settings["overlay_x"] = self.overlay.x()
        settings["overlay_y"] = self.overlay.y()
        settings["overlay_width"] = self.overlay.width()
        settings["overlay_height"] = self.overlay.height()
        old_translation_profile = self._translation_profile(self.settings)
        self.settings.update(settings)
        if "theme" in settings:
            apply_application_palette(self.app, self.settings)
        if old_translation_profile != self._translation_profile(self.settings):
            self.translation_queue.clear()
            self.queued_translation_keys.clear()
            self.latest_requested_key = None
        save_settings(self.settings)
        if was_persistent != bool(self.settings.get("history_persistent", False)):
            self.history.set_persistent(bool(self.settings.get("history_persistent", False)))
        self.toolbar.apply_settings(self.settings)
        self.overlay.apply_settings(self.settings)
        if previous_mode != self.settings.get("mode", "local"):
            self._refresh_overlay_after_mode_change()
        if self.history_dialog is not None:
            self.history_dialog.apply_settings(self.settings)
        if was_capturing:
            self.stop_capture()
            # Avoid running two OCR loops at once while the previous scan finishes.
            QTimer.singleShot(250, self._restart_capture_when_ready)

    def _restart_capture_when_ready(self) -> None:
        if any(worker.isRunning() for worker in self.ocr_workers):
            QTimer.singleShot(250, self._restart_capture_when_ready)
            return
        if self.region:
            self.start_capture()

    def _apply_glossary(self, glossary: dict[str, str]) -> None:
        old_profile = self._translation_profile(self.settings)
        self.settings["glossary"] = dict(glossary)
        if old_profile != self._translation_profile(self.settings):
            self.translation_queue.clear()
            self.queued_translation_keys.clear()
            self.latest_requested_key = None
        save_settings(self.settings)

    def show_history(self) -> None:
        if self.history_dialog is None:
            self.history_dialog = HistoryDialog(self.history, self.settings, self.toolbar)
        else:
            self.history_dialog.refresh()
        self.history_dialog.show()
        self.history_dialog.raise_()
        self.history_dialog.activateWindow()

    def _context_for_translation(self) -> str:
        parts: list[str] = []
        glossary = self.settings.get("glossary", {})
        if isinstance(glossary, dict) and glossary:
            parts.append("PREFERRED GLOSSARY TERMS (English → Persian):")
            parts.extend(f"{english} → {persian}" for english, persian in glossary.items())
        recent = list(reversed(self.history.items[:3]))
        if recent:
            parts.append("RECENT DIALOGUE CONTEXT:")
            parts.extend(f"EN: {entry['original']}\nFA: {entry['translated']}" for entry in recent)
        return "\n".join(parts)

    @staticmethod
    def _translation_profile(settings: dict[str, Any]) -> str:
        """Stable, non-secret cache namespace for the selected translation configuration."""
        mode = str(settings.get("mode", "local"))
        profile: dict[str, Any] = {"mode": mode}
        if mode == "online":
            provider = str(settings.get("online_provider", "google")).lower()
            profile["provider"] = provider
            if provider in {"libre", "libretranslate", "libre_translate"}:
                profile["endpoint"] = str(settings.get("libretranslate_url", "")).strip().rstrip("/")
            elif provider in {"microsoft", "microsoft_translator", "azure_translator", "azure"}:
                profile["endpoint"] = str(settings.get("microsoft_translator_endpoint", "")).strip().rstrip("/")
                profile["region"] = str(settings.get("microsoft_translator_region", "")).strip().lower()
            profile["source"] = "en"
            profile["target"] = "fa"
        elif mode == "offline":
            profile["source"] = str(settings.get("offline_source", "en"))
            profile["target"] = str(settings.get("offline_target", "fa"))
        else:
            profile["endpoint"] = str(settings.get("lmstudio_base_url", "")).strip().rstrip("/")
            profile["model"] = str(settings.get("lmstudio_model", "")).strip()
            glossary = settings.get("glossary", {})
            if isinstance(glossary, dict):
                profile["glossary_hash"] = hashlib.sha256(
                    json.dumps(glossary, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest()[:16]
        return json.dumps(profile, ensure_ascii=False, sort_keys=True)

    @classmethod
    def _cache_key(cls, text: str, settings: dict[str, Any]) -> tuple[str, str]:
        return cls._translation_profile(settings), normalize(text)

    def _display_cached_translation(self, original: str, translated: str) -> None:
        self.overlay.set_translation(original, translated, "از حافظه ترجمه")
        if self.overlay_enabled:
            self.overlay.show()
            self.overlay.raise_()

    def _on_text_detected(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        settings = self.settings.copy()
        context = self._context_for_translation()
        key = self._cache_key(text, settings)
        self.latest_requested_key = key

        # If this exact item is being translated or is already queued, don't duplicate it.
        if key == self.active_translation_key or key in self.queued_translation_keys:
            return
        cached = self.translation_cache.get(key)
        if cached is not None:
            self._display_cached_translation(text, cached)
            return

        if len(self.translation_queue) >= self.MAX_TRANSLATION_QUEUE:
            dropped_text, dropped_settings, _dropped_context = self.translation_queue.popleft()
            self.queued_translation_keys.discard(self._cache_key(dropped_text, dropped_settings))

        self.translation_queue.append((text, settings, context))
        self.queued_translation_keys.add(key)
        if self.translation_busy:
            self.overlay.set_status(f"در حال ترجمه · {len(self.translation_queue)} متن در صف")
        else:
            self._process_translation_queue()

    def _process_translation_queue(self) -> None:
        if self.translation_busy:
            return
        while self.translation_queue:
            task = self.translation_queue.popleft()
            text, settings, context = task
            key = self._cache_key(text, settings)
            self.queued_translation_keys.discard(key)
            cached = self.translation_cache.get(key)
            if cached is not None:
                if key == self.latest_requested_key:
                    self._display_cached_translation(text, cached)
                continue
            self._start_translation(text, settings, context)
            return

    def _start_translation(self, text: str, settings: dict[str, Any], context: str) -> None:
        self.translation_busy = True
        self.active_translation = (text, settings.copy(), context)
        self.active_translation_key = self._cache_key(text, settings)
        mode = str(settings.get("mode", "local"))
        queued_count = len(self.translation_queue)
        status = f"{MODE_NAMES.get(mode, mode)} · در حال پردازش"
        if queued_count:
            status += f" · {queued_count} در صف"
        self.overlay.set_translation(text, "در حال ترجمه…", status)
        if self.overlay_enabled:
            self.overlay.show()
            self.overlay.raise_()
        thread = TranslationThread(text, settings, context, self)
        thread.result_ready.connect(self._on_translation_result)
        thread.finished.connect(lambda current=thread: self._cleanup_translation_thread(current))
        self.translation_threads.append(thread)
        thread.start()

    def _on_translation_result(self, original: str, translated: str, mode: str, error_flag: str) -> None:
        task = self.active_translation
        task_settings = task[1] if task is not None else self.settings.copy()
        key = self._cache_key(original, task_settings)
        is_latest = key == self.latest_requested_key
        if error_flag:
            if is_latest:
                self.overlay.set_translation(original, translated, f"خطا · {MODE_NAMES.get(mode, mode)}")
            # Never cache or persist transient service/network errors as translations.
        else:
            self.translation_cache[key] = translated
            if len(self.translation_cache) > 2000:
                self.translation_cache.pop(next(iter(self.translation_cache)))
            self.history.add(original, translated, mode)
            if is_latest:
                self.overlay.set_translation(original, translated, f"ترجمه آماده · {MODE_NAMES.get(mode, mode)}")
            if self.history_dialog is not None and self.history_dialog.isVisible():
                self.history_dialog.refresh()
        if is_latest and self.overlay_enabled:
            self.overlay.show()
            self.overlay.raise_()
        self.translation_busy = False
        self.active_translation = None
        self.active_translation_key = None
        # Schedule the next item after this worker has returned from its result signal.
        QTimer.singleShot(0, self._process_translation_queue)

    def _cleanup_translation_thread(self, thread: TranslationThread) -> None:
        if thread in self.translation_threads:
            self.translation_threads.remove(thread)
        thread.deleteLater()

    def _on_ocr_error(self, error: str) -> None:
        self.stop_capture()
        self._set_status("خطای OCR")
        QMessageBox.warning(self.toolbar, "خطای OCR", error)

    def quit_app(self) -> None:
        self.app.quit()

    def shutdown(self) -> None:
        try:
            if self.hotkey_listener is not None:
                self.hotkey_listener.stop()
        except Exception:
            pass
        for worker in list(self.ocr_workers):
            worker.stop()
        for worker in list(self.ocr_workers):
            worker.wait(2500)
        for thread in list(self.translation_threads):
            thread.wait(2500)
        for thread in list(self.connection_test_threads):
            thread.wait(2500)
        try:
            self.settings["toolbar_x"] = self.toolbar.x()
            self.settings["toolbar_y"] = self.toolbar.y()
            self.settings["overlay_x"] = self.overlay.x()
            self.settings["overlay_y"] = self.overlay.y()
            self.settings["overlay_width"] = self.overlay.width()
            self.settings["overlay_height"] = self.overlay.height()
            save_settings(self.settings)
        except Exception:
            pass


def main() -> int:
    enable_windows_dpi_awareness()
    app = QApplication(sys.argv)
    app.setApplicationName("Glass Translator")
    app.setOrganizationName("GlassTranslator")
    icon_path = app_resource_path("assets/glass_translator.ico")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setQuitOnLastWindowClosed(False)
    initial_settings = load_settings()
    configure_application_appearance(app, initial_settings)
    app.setApplicationVersion("0.2.10")
    controller = AppController(app)
    # Keep a strong reference while the tool-style windows are active.
    app._glass_translator_controller = controller  # type: ignore[attr-defined]
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
