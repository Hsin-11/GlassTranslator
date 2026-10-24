from __future__ import annotations

import sys
import re
from typing import Any
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, QTimer, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from config import MODE_NAMES, load_settings, save_settings, ensure_app_dir
from history import HistoryManager
from ocr_worker import OCRWorker
from translator import TranslationError, translate_text
from ui import FloatingToolbar, HistoryDialog, RegionSelector, SettingsDialog, TranslationOverlay


def app_resource_path(relative_path: str) -> Path:
    """Resolve bundled resources in source and PyInstaller builds."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    base = Path(frozen_root) if frozen_root else Path(__file__).resolve().parent
    return base / relative_path


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
        self.pending_translation: tuple[str, dict[str, Any], str] | None = None
        self.translation_cache: dict[tuple[str, str], str] = {}
        for entry in self.history.items:
            self.translation_cache[(str(entry.get("mode", "local")), normalize(str(entry.get("original", ""))))] = str(entry.get("translated", ""))
        self.overlay_enabled = False
        self.history_dialog: HistoryDialog | None = None
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
        selector = RegionSelector(screen.geometry())
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

    def cycle_mode(self) -> None:
        modes = ["online", "local", "offline"]
        current = self.settings.get("mode", "local")
        index = modes.index(current) if current in modes else 0
        self.settings["mode"] = modes[(index + 1) % len(modes)]
        save_settings(self.settings)
        self.toolbar.apply_settings(self.settings)
        self._refresh_overlay_after_mode_change()
        self._refresh_mode_tooltip()

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.toolbar)
        dialog.settings_saved.connect(self._apply_settings)
        dialog.glossary_changed.connect(self._apply_glossary)
        dialog.test_connection_requested.connect(lambda settings, target=dialog: self._test_connection(settings, target))
        dialog.exec()

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
        self.settings.update(settings)
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
        self.settings["glossary"] = dict(glossary)
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

    def _on_text_detected(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        mode = str(self.settings.get("mode", "local"))
        key = (mode, normalize(text))
        if self.translation_busy:
            # Keep the newest changed subtitle, even when it is already cached; it must be shown after the current request.
            self.pending_translation = (text, self.settings.copy(), self._context_for_translation())
            return

        if key in self.translation_cache:
            self.overlay.set_translation(text, self.translation_cache[key], "از حافظه ترجمه")
            if self.overlay_enabled:
                self.overlay.show()
                self.overlay.raise_()
            return
        self._start_translation(text, self.settings.copy(), self._context_for_translation())

    def _start_translation(self, text: str, settings: dict[str, Any], context: str) -> None:
        self.translation_busy = True
        mode = str(settings.get("mode", "local"))
        self.overlay.set_translation(text, "در حال ترجمه…", f"{MODE_NAMES.get(mode, mode)} · در حال پردازش")
        if self.overlay_enabled:
            self.overlay.show()
            self.overlay.raise_()
        thread = TranslationThread(text, settings, context, self)
        thread.result_ready.connect(self._on_translation_result)
        thread.finished.connect(lambda current=thread: self._cleanup_translation_thread(current))
        self.translation_threads.append(thread)
        thread.start()

    def _on_translation_result(self, original: str, translated: str, mode: str, error_flag: str) -> None:
        if error_flag:
            self.overlay.set_translation(original, translated, f"خطا · {MODE_NAMES.get(mode, mode)}")
            # Do not persist operational errors as translations.
        else:
            self.translation_cache[(mode, normalize(original))] = translated
            self.history.add(original, translated, mode)
            self.overlay.set_translation(original, translated, f"ترجمه آماده · {MODE_NAMES.get(mode, mode)}")
            if self.history_dialog is not None and self.history_dialog.isVisible():
                self.history_dialog.refresh()
        if self.overlay_enabled:
            self.overlay.show()
            self.overlay.raise_()
        self.translation_busy = False
        pending = self.pending_translation
        self.pending_translation = None
        if pending is not None and normalize(pending[0]) != normalize(original):
            pending_key = (pending[1].get("mode", "local"), normalize(pending[0]))
            if pending_key in self.translation_cache:
                self.overlay.set_translation(pending[0], self.translation_cache[pending_key], "از حافظه ترجمه")
            else:
                self._start_translation(*pending)

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
    app.setFont(QFont("Segoe UI", 10))
    controller = AppController(app)
    # Keep a strong reference while the tool-style windows are active.
    app._glass_translator_controller = controller  # type: ignore[attr-defined]
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
