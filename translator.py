from __future__ import annotations

from typing import Any
import os
import sys
from pathlib import Path
import threading
import time
import requests

# Keep model installation and discovery on one persistent directory. Argos
# reads ARGOS_PACKAGES_DIR during import, so set it before importing Argos modules.
def _canonical_argos_package_dir() -> Path:
    home = Path.home()
    if os.name == "nt":
        appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
        preferred = appdata / "GlassTranslator" / "argos-packages"
    else:
        preferred = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local" / "share"))) / "argos-translate" / "packages"

    # Respect an explicitly configured packages root, then use the application default.
    raw = (os.environ.get("ARGOS_PACKAGES_DIR") or
           os.environ.get("ARGOS_TRANSLATE_PACKAGE_DIR") or
           os.environ.get("ARGOS_PACKAGE_DIR") or str(preferred))
    return Path(raw).expanduser()


def _set_default_argos_package_dir() -> Path:
    canonical = _canonical_argos_package_dir()
    canonical.mkdir(parents=True, exist_ok=True)
    # Argos versions differ in which variable they consult; unify all supported names.
    for env_name in ("ARGOS_PACKAGES_DIR", "ARGOS_TRANSLATE_PACKAGE_DIR", "ARGOS_PACKAGE_DIR"):
        os.environ[env_name] = str(canonical)
    return canonical


_ARGOS_CANONICAL_DIR = _set_default_argos_package_dir()


def _argos_candidate_package_dirs(argos_settings: Any | None = None) -> list[Path]:
    """Return the canonical model root plus likely legacy Argos model roots."""
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
    localappdata = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
    candidates: list[Path] = [_ARGOS_CANONICAL_DIR]
    for env_name in ("ARGOS_PACKAGES_DIR", "ARGOS_TRANSLATE_PACKAGE_DIR", "ARGOS_PACKAGE_DIR"):
        value = os.environ.get(env_name, "").strip()
        if value:
            candidates.append(Path(value).expanduser())
    runtime_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    bundled_argos_root = runtime_root / "assets" / "argos-packages"
    if bundled_argos_root.is_dir():
        candidates.append(bundled_argos_root)
    candidates.extend([
        appdata / "GlassTranslator" / "argos-packages",
        appdata / "argos-translate" / "packages",
        localappdata / "argos-translate" / "packages",
        appdata / "argos-translate" / "local" / "share" / "packages",
        localappdata / "argos-translate" / "local" / "share" / "packages",
        home / ".local" / "share" / "argos-translate" / "packages",
        home / ".argos-translate" / "local" / "share" / "packages",
        home / ".argos-translate" / "packages",
        Path(sys.prefix) / "share" / "argos-translate" / "packages",
        Path(sys.prefix) / ".local" / "share" / "argos-translate" / "packages",
        Path(sys.prefix) / "argos-translate" / "packages",
        Path(sys.prefix) / "Lib" / "site-packages" / "argostranslate" / "packages",
        Path(sys.prefix) / "Lib" / "site-packages" / "argostranslate" / "data" / "packages",
        Path(sys.prefix) / "Lib" / "site-packages" / "argostranslate" / "local" / "share" / "packages",
    ])
    if argos_settings is not None:
        for attr in ("package_data_dir", "legacy_package_data_dir", "package_dir"):
            value = getattr(argos_settings, attr, None)
            if value:
                try:
                    candidates.append(Path(value).expanduser())
                except TypeError:
                    pass
        package_dirs = getattr(argos_settings, "package_dirs", None)
        if package_dirs:
            for value in package_dirs:
                try:
                    candidates.append(Path(value).expanduser())
                except TypeError:
                    pass
    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = os.path.normcase(str(candidate.resolve()))
        except OSError:
            key = os.path.normcase(str(candidate.absolute()))
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _configure_argos_search_paths() -> list[Path]:
    """Use one stable installation path while still reading existing legacy installs."""
    try:
        import argostranslate.settings as argos_settings
    except ImportError:
        return []

    canonical = _set_default_argos_package_dir()
    candidates = _argos_candidate_package_dirs(argos_settings)
    # Argos installs into package_data_dir but discovers packages from package_dirs.
    # Set both explicitly; this also handles settings imported before app initialization.
    try:
        argos_settings.package_data_dir = canonical
    except Exception:
        pass
    current: list[Path] = [canonical]
    for candidate in candidates:
        try:
            if candidate.is_dir() and all(
                os.path.normcase(str(candidate.resolve())) != os.path.normcase(str(Path(existing).resolve()))
                for existing in current
            ):
                current.append(candidate)
        except OSError:
            continue
    try:
        argos_settings.package_dirs = current
    except Exception:
        pass
    return current


def _refresh_argos_language_cache(argos_translate: Any) -> None:
    # Argos caches the discovered language graph. Clear it before checking because
    # installation may have happened while this app process was already running.
    clear = getattr(getattr(argos_translate, "get_installed_languages", None), "cache_clear", None)
    if callable(clear):
        try:
            clear()
        except Exception:
            pass


class TranslationError(RuntimeError):
    """A user-displayable translation error."""


# Google web endpoint is unofficial and may throttle burst traffic. Serialize calls
# and keep at least 1.25 seconds between request starts to avoid needless bursts.
_GOOGLE_PACING_LOCK = threading.Lock()
_LAST_GOOGLE_REQUEST_AT = 0.0
_GOOGLE_MIN_REQUEST_GAP_SECONDS = 1.25


def _pace_google_request() -> None:
    global _LAST_GOOGLE_REQUEST_AT
    with _GOOGLE_PACING_LOCK:
        now = time.monotonic()
        wait_for = _GOOGLE_MIN_REQUEST_GAP_SECONDS - (now - _LAST_GOOGLE_REQUEST_AT)
        if wait_for > 0:
            time.sleep(wait_for)
        _LAST_GOOGLE_REQUEST_AT = time.monotonic()


def translate_text(text: str, settings: dict[str, Any], context: str = "") -> str:
    text = str(text or "").strip()
    if not text:
        raise TranslationError("متن ورودی خالی است؛ محدوده OCR را بررسی کن.")
    mode = settings.get("mode", "local")
    if mode == "online":
        return _translate_online(text, settings)
    if mode == "offline":
        return _translate_offline(text, settings)
    return _translate_local_ai(text, settings, context)


def _translate_online(text: str, settings: dict[str, Any]) -> str:
    provider = str(settings.get("online_provider", "google")).strip().lower()
    if provider in {"google", "google_translate", "google-translate"}:
        return _translate_google_web(text, settings)
    if provider in {"libre", "libretranslate", "libre_translate"}:
        return _translate_libretranslate(text, settings)
    raise TranslationError("سرویس آنلاین انتخاب‌شده شناخته‌شده نیست. تنظیمات موتور آنلاین را بررسی کن.")


def _proxy_kwargs(settings: dict[str, Any]) -> dict[str, Any]:
    proxy = str(settings.get("online_proxy", "")).strip()
    if not proxy:
        return {}
    if "://" not in proxy:
        proxy = "http://" + proxy
    return {"proxies": {"http": proxy, "https": proxy}}


def _translate_google_web(text: str, settings: dict[str, Any] | None = None) -> str:
    """Use Google's lightweight web translation endpoint (no API key; not a stable official API)."""
    settings = settings or {}
    try:
        _pace_google_request()
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": "fa", "dt": "t", "q": text},
            headers={"User-Agent": "Mozilla/5.0 GlassTranslator/0.2.7"},
            timeout=(5, 20),
            **_proxy_kwargs(settings),
        )
        response.raise_for_status()
        data = response.json()
    except requests.HTTPError as exc:
        response = exc.response
        status = response.status_code if response is not None else None
        if status == 429:
            retry_after = response.headers.get("Retry-After", "") if response is not None else ""
            retry_hint = f" سرویس زمان انتظار {retry_after} ثانیه را اعلام کرده است." if retry_after.isdigit() else ""
            # The gtx endpoint is an unofficial web endpoint and may throttle clients or shared IPs.
            raise TranslationError(
                "سرویس Google Translate درخواست‌ها را محدود کرده است (HTTP 429: Too Many Requests)."
                " این خطا الزاماً به معنی قطع اینترنت نیست. کمی صبر کن و دوباره امتحان کن؛ اگر ادامه داشت، "
                "ارائه‌دهنده آنلاین را به یک سرور LibreTranslate قابل‌دسترسی تغییر بده یا از Local AI استفاده کن."
                f"{retry_hint}"
            ) from exc
        raise TranslationError(
            f"Google Translate خطای HTTP {status or 'نامشخص'} برگرداند. "
            "دسترسی شبکه، پروکسی و وضعیت موقت سرویس را بررسی کن."
        ) from exc
    except requests.RequestException as exc:
        raise TranslationError(
            "به آدرس مترجم آنلاین Google دسترسی برقرار نشد. اینترنت و تنظیم پروکسی را بررسی کن. "
            f"جزئیات: {exc}"
        ) from exc
    except ValueError as exc:
        raise TranslationError("پاسخ مترجم آنلاین Google قابل خواندن نیست؛ احتمالاً ساختار سرویس تغییر کرده است.") from exc

    try:
        segments = data[0]
        result = "".join(str(segment[0]) for segment in segments if segment and segment[0])
    except (IndexError, TypeError, KeyError) as exc:
        raise TranslationError("مترجم آنلاین Google پاسخ ترجمه معتبری برنگرداند.") from exc
    if not result.strip():
        raise TranslationError("مترجم آنلاین Google پاسخ خالی برگرداند.")
    return result.strip()


def _translate_libretranslate(text: str, settings: dict[str, Any]) -> str:
    endpoint = str(settings.get("libretranslate_url", "")).strip()
    if not endpoint:
        raise TranslationError(
            "نشانی API برای LibreTranslate وارد نشده است. در تنظیمات نشانی سرویس را وارد کن یا "
            "ارائه‌دهنده آنلاین را روی Google Translate بگذار."
        )
    endpoint = endpoint.rstrip("/")
    # Accept either a server base URL or the full /translate endpoint.
    if not endpoint.endswith("/translate"):
        endpoint += "/translate"

    payload: dict[str, str] = {"q": text, "source": "en", "target": "fa", "format": "text"}
    api_key = str(settings.get("libretranslate_api_key", "")).strip()
    if api_key:
        payload["api_key"] = api_key

    try:
        response = requests.post(endpoint, json=payload, timeout=(5, 25), **_proxy_kwargs(settings))
        response.raise_for_status()
        data = response.json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "نامشخص"
        explanation = "؛ احتمالاً این سرویس کلید API می‌خواهد یا درخواست‌ها را محدود کرده است" if status in (401, 403, 429) else ""
        raise TranslationError(f"LibreTranslate خطای HTTP {status} برگرداند{explanation}. نشانی و کلید API را بررسی کن.") from exc
    except requests.RequestException as exc:
        raise TranslationError(f"اتصال به LibreTranslate ناموفق بود. نشانی سرویس، اینترنت و پروکسی را بررسی کن. جزئیات: {exc}") from exc
    except ValueError as exc:
        raise TranslationError("پاسخ LibreTranslate قابل خواندن نیست؛ نشانی API را بررسی کن.") from exc

    result = data.get("translatedText") if isinstance(data, dict) else None
    if not isinstance(result, str) or not result.strip():
        raise TranslationError("LibreTranslate ترجمه معتبری برنگرداند. نشانی سرویس یا کلید API را بررسی کن.")
    return result.strip()


def _normalize_lmstudio_url(value: Any) -> str:
    base_url = str(value or "http://127.0.0.1:1234/v1").strip().rstrip("/")
    if not base_url:
        base_url = "http://127.0.0.1:1234/v1"
    if "://" not in base_url:
        base_url = "http://" + base_url
    # Users sometimes paste an endpoint URL instead of the server base URL.
    for suffix in ("/chat/completions", "/models"):
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)].rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"
    return base_url


def _translate_local_ai(text: str, settings: dict[str, Any], context: str = "") -> str:
    base_url = _normalize_lmstudio_url(settings.get("lmstudio_base_url", "http://127.0.0.1:1234/v1"))
    model = str(settings.get("lmstudio_model", "")).strip()

    try:
        if not model:
            models_response = requests.get(f"{base_url}/models", timeout=(3, 8))
            models_response.raise_for_status()
            models_data = models_response.json()
            models = models_data.get("data", []) if isinstance(models_data, dict) else []
            if not models or not isinstance(models[0], dict) or not models[0].get("id"):
                raise TranslationError(
                    "به API محلی وصل شدم، اما مدل بارگذاری‌شده‌ای پیدا نکردم. در LM Studio یک مدل را Load کن "
                    "و Local Server را Start کن."
                )
            model = str(models[0]["id"])

        context_line = (
            f"\nGlossary and recent dialogue context (use for consistent terminology):\n{context}\n"
            if context.strip() else ""
        )
        system_prompt = (
            "You are a professional English-to-Persian (Farsi) translator for video games and subtitles. "
            "Translate into natural, fluent Persian. Preserve meaning, tone, character names, item names, "
            "numbers, placeholders, and formatting tokens. Do not explain or add quotation marks. "
            "Return only the Persian translation."
        )
        user_prompt = f"{context_line}\nTranslate this English text to Persian. Use the glossary/context when relevant:\n{text}"
        response = requests.post(
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 512,
                "stream": False,
            },
            timeout=(5, 120),
        )
        response.raise_for_status()
        data = response.json()
    except TranslationError:
        raise
    except requests.ConnectionError as exc:
        raise TranslationError(
            f"اتصال به LM Studio برقرار نشد ({base_url}). در LM Studio به بخش Developer/Local Server برو، "
            "سرور را Start کن و مطمئن شو نشانی و پورت همان مقدار تنظیمات است. "
            f"جزئیات: {exc}"
        ) from exc
    except requests.Timeout as exc:
        raise TranslationError(
            "پاسخ LM Studio بیش از زمان مجاز طول کشید. مدل را Load کن، حافظه GPU/CPU را بررسی کن یا مدل سبک‌تری انتخاب کن."
        ) from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "نامشخص"
        raise TranslationError(
            f"LM Studio خطای HTTP {status} برگرداند. مدل و Local Server را بررسی کن. جزئیات: {exc}"
        ) from exc
    except requests.RequestException as exc:
        raise TranslationError(f"درخواست به LM Studio ناموفق بود: {exc}") from exc
    except ValueError as exc:
        raise TranslationError("پاسخ LM Studio JSON معتبر نیست.") from exc

    try:
        message = data["choices"][0]["message"]["content"]
        if isinstance(message, list):
            # Accommodate APIs that return content blocks instead of a plain string.
            result = "".join(
                str(part.get("text", "")) for part in message if isinstance(part, dict)
            )
        else:
            result = str(message)
    except (KeyError, IndexError, TypeError) as exc:
        raise TranslationError("LM Studio پاسخ ترجمه معتبری برنگرداند. مدل/قالب گفت‌وگو را بررسی کن.") from exc

    result = result.strip()
    if not result:
        raise TranslationError("LM Studio پاسخ خالی برگرداند. مدل دیگری را Load کن یا قالب چت مدل را بررسی کن.")
    return result


# Argos model objects are expensive to discover/initialize repeatedly. Keep a process-local
# cache so repeated short game lines do not pay the initialization cost on every OCR result.
_OFFLINE_LOCK = threading.RLock()
_OFFLINE_TRANSLATION_CACHE: dict[tuple[str, str], Any] = {}


def _get_offline_translation(source: str, target: str):
    try:
        import argostranslate.translate as argos_translate
    except ImportError as exc:
        raise TranslationError(
            "کتابخانه موتور آفلاین در محیط Python برنامه نصب نیست. از همین پوشه setup_windows.bat و سپس "
            "install_offline_model.bat را اجرا کن."
        ) from exc

    key = (source, target)
    with _OFFLINE_LOCK:
        cached = _OFFLINE_TRANSLATION_CACHE.get(key)
        if cached is not None:
            return cached

        search_dirs = _configure_argos_search_paths()
        _refresh_argos_language_cache(argos_translate)
        try:
            languages = argos_translate.get_installed_languages()
            source_language = next((language for language in languages if getattr(language, "code", None) == source), None)
            target_language = next((language for language in languages if getattr(language, "code", None) == target), None)

            translation = None
            # Preferred API in recent Argos versions; this also supports language
            # pivoting if a direct pair is not present but a route is installed.
            get_by_codes = getattr(argos_translate, "get_translation_from_codes", None)
            if callable(get_by_codes):
                try:
                    translation = get_by_codes(source, target)
                except Exception:
                    translation = None
            if translation is None and source_language is not None and target_language is not None:
                translation = source_language.get_translation(target_language)

            if translation is None:
                pairs: list[str] = []
                try:
                    import argostranslate.package as argos_package
                    packages = argos_package.get_installed_packages()
                    pairs = [
                        f"{getattr(item, 'from_code', '?')}→{getattr(item, 'to_code', '?')}"
                        for item in packages
                        if getattr(item, 'from_code', None) or getattr(item, 'to_code', None)
                    ]
                except Exception:
                    pass
                roots = [str(path) for path in search_dirs if path.exists()]
                if source_language is None or target_language is None:
                    language_codes = ", ".join(str(getattr(language, "code", "?")) for language in languages) or "هیچ زبان نصب‌شده‌ای گزارش نشد"
                    detail = f"زبان‌های کشف‌شده: {language_codes}."
                else:
                    detail = f"زبان‌های en و fa دیده شدند، اما مسیر ترجمهٔ {source} به {target} پیدا نشد."
                package_detail = f" بسته‌ها: {', '.join(pairs) or 'نامشخص'}."
                path_detail = f" مسیرهای بررسی‌شده: {' | '.join(roots) or 'هیچ مسیر موجودی پیدا نشد'}."
                raise TranslationError(
                    f"مدل آفلاین انگلیسی به فارسی در دسترس نیست. {detail}{package_detail}{path_detail} "
                    "برنامه و نصب‌کننده را از یک پوشه اجرا کن؛ اگر مدل با Argos GUI نصب شده، برنامه را یک بار ببند و دوباره باز کن."
                )

            _OFFLINE_TRANSLATION_CACHE[key] = translation
            return translation
        except TranslationError:
            raise
        except Exception as exc:
            raise TranslationError(f"آماده‌سازی مدل آفلاین ناموفق بود: {type(exc).__name__}: {exc}") from exc


def _translate_offline(text: str, settings: dict[str, Any]) -> str:
    source = str(settings.get("offline_source", "en"))
    target = str(settings.get("offline_target", "fa"))
    try:
        # Keep Argos translation calls serialized: it avoids two OCR/test threads
        # initializing or invoking the same model at the same time.
        with _OFFLINE_LOCK:
            translation = _get_offline_translation(source, target)
            result = translation.translate(text)
    except TranslationError:
        raise
    except Exception as exc:
        raise TranslationError(f"موتور آفلاین ترجمه را انجام نداد: {exc}") from exc

    if not isinstance(result, str) or not result.strip():
        raise TranslationError("موتور آفلاین پاسخ خالی برگرداند.")
    return result.strip()
