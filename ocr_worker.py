from __future__ import annotations

import threading
import time
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal


class OCRWorker(QThread):
    text_detected = Signal(str)
    status_changed = Signal(str)
    fatal_error = Signal(str)

    def __init__(self, region: dict[str, int], settings: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.region = region.copy()
        self.settings = settings.copy()
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    @staticmethod
    def _sort_and_join(results: list[Any]) -> str:
        entries = []
        for result in results:
            try:
                box, text, confidence = result
                if not str(text).strip() or float(confidence) < 0.18:
                    continue
                xs = [float(point[0]) for point in box]
                ys = [float(point[1]) for point in box]
                entries.append({
                    "x": min(xs), "y": min(ys), "h": max(ys) - min(ys),
                    "cy": (min(ys) + max(ys)) / 2.0, "text": str(text).strip(),
                })
            except (TypeError, ValueError, IndexError):
                continue

        if not entries:
            return ""

        # Group adjacent detections into lines before ordering left-to-right.
        entries.sort(key=lambda item: item["cy"])
        lines: list[list[dict[str, Any]]] = []
        for entry in entries:
            tolerance = max(8.0, entry["h"] * 0.65)
            placed = False
            for line in reversed(lines[-3:]):
                line_cy = sum(item["cy"] for item in line) / len(line)
                if abs(entry["cy"] - line_cy) <= tolerance:
                    line.append(entry)
                    placed = True
                    break
            if not placed:
                lines.append([entry])

        lines.sort(key=lambda line: min(item["y"] for item in line))
        output = []
        for line in lines:
            line.sort(key=lambda item: item["x"])
            text = " ".join(item["text"] for item in line)
            if text:
                output.append(text)
        return "\n".join(output).strip()

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().split()).strip()

    def run(self) -> None:
        try:
            import easyocr
            import numpy as np
            from PIL import Image
            import mss
            import torch
        except ImportError as exc:
            self.fatal_error.emit(
                "یکی از وابستگی‌های OCR نصب نیست. طبق README_FA.md وابستگی‌ها را نصب کن. "
                f"جزئیات: {exc}"
            )
            return

        try:
            use_gpu = bool(torch.cuda.is_available())
            self.status_changed.emit(
                "آماده‌سازی OCR روی GPU…" if use_gpu else "آماده‌سازی OCR روی CPU… (اولین اجرا ممکن است مدل را دریافت کند)"
            )
            runtime_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            bundled_ocr_dir = runtime_root / "assets" / "easyocr-models"
            detector_weights = bundled_ocr_dir / "craft_mlt_25k.pth"
            recognizer_weights = bundled_ocr_dir / "english_g2.pth"
            if detector_weights.is_file() and recognizer_weights.is_file():
                reader = easyocr.Reader(
                    ["en"], gpu=use_gpu, verbose=False,
                    model_storage_directory=str(bundled_ocr_dir), download_enabled=False,
                )
            else:
                reader = easyocr.Reader(["en"], gpu=use_gpu, verbose=False)
        except Exception as exc:
            self.fatal_error.emit(f"راه‌اندازی EasyOCR ناموفق بود: {exc}")
            return

        try:
            with mss.mss() as screen_capture:
                last_candidate = ""
                stable_count = 0
                last_emitted = ""
                interval = max(300, int(self.settings.get("scan_interval_ms", 700)))
                needed_stable_reads = max(1, min(5, int(self.settings.get("stable_reads", 2))))
                self.status_changed.emit("OCR فعال است؛ اسکن پیوسته با تأیید پایداری متن")

                while not self._stop_event.is_set():
                    started = time.monotonic()
                    try:
                        shot = screen_capture.grab(self.region)
                        image = Image.frombytes("RGB", shot.size, shot.rgb)
                        image_array = np.asarray(image)
                        profile = str(self.settings.get("quality_profile", "balanced")).lower()
                        profile_options = {
                            "fast": {
                                "mag_ratio": 1.0, "text_threshold": 0.75,
                                "low_text": 0.40, "link_threshold": 0.40,
                                "contrast_ths": 0.15, "adjust_contrast": 0.50,
                            },
                            "balanced": {
                                "mag_ratio": 1.2, "text_threshold": 0.70,
                                "low_text": 0.35, "link_threshold": 0.40,
                                "contrast_ths": 0.10, "adjust_contrast": 0.60,
                            },
                            "accurate": {
                                "mag_ratio": 1.5, "text_threshold": 0.65,
                                "low_text": 0.30, "link_threshold": 0.35,
                                "contrast_ths": 0.08, "adjust_contrast": 0.70,
                            },
                        }
                        read_options = profile_options.get(profile, profile_options["balanced"]).copy()

                        # Tiny subtitle regions benefit from a modest upscale, but avoid
                        # enlarging already large captures or making every CPU scan expensive.
                        if profile == "accurate" and min(image_array.shape[:2]) < 260:
                            scale = min(1.4, 2400 / max(image_array.shape[:2]))
                            if scale > 1.05:
                                resized = image.resize(
                                    (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
                                    Image.Resampling.LANCZOS,
                                )
                                image_array = np.asarray(resized)

                        results = reader.readtext(
                            image_array, detail=1, paragraph=False,
                            decoder="greedy", batch_size=1, workers=0,
                            **read_options,
                        )
                        text = self._sort_and_join(results)
                        normalized = self._normalize(text)

                        if not normalized:
                            last_candidate = ""
                            stable_count = 0
                            # Permit the same subtitle to be emitted again after it
                            # genuinely disappears and later reappears on screen.
                            last_emitted = ""
                        elif normalized == last_candidate:
                            stable_count += 1
                        else:
                            last_candidate = normalized
                            stable_count = 1

                        if text and stable_count >= needed_stable_reads and normalized != last_emitted:
                            last_emitted = normalized
                            self.text_detected.emit(text)
                    except Exception as exc:
                        self.status_changed.emit(f"خطا هنگام خواندن محدوده: {exc}")
                        self._stop_event.wait(0.3)

                    elapsed_ms = int((time.monotonic() - started) * 1000)
                    remaining_ms = max(50, interval - elapsed_ms)
                    # Wait in short increments so Stop reacts promptly.
                    self._stop_event.wait(remaining_ms / 1000.0)
        except Exception as exc:
            self.fatal_error.emit(f"دسترسی به تصویر صفحه ناموفق بود: {exc}")
        finally:
            self.status_changed.emit("OCR متوقف شد")
