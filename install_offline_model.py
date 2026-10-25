"""Install and verify the official Argos Translate English -> Persian model.

Run this script with the same .venv Python used to launch Glass Translator.
It uses Argos' package index first, then falls back to the official index JSON
and the published en->fa model URL if the Argos index helper fails.
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

import requests

SOURCE_CODE = "en"
TARGET_CODE = "fa"
OFFICIAL_INDEX_URL = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
KNOWN_OFFICIAL_MODEL_URL = "https://argos-net.com/v1/translate-en_fa-1_5.argosmodel"
KNOWN_IPFS_CID = "QmZ33DueKF3oy3jqaJGayimXDZ5osbHAVmh4C7P9MdEW69"



def _configure_installer_environment() -> Path:
    """Use the exact same persistent Argos packages root as the app/checker."""
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
    root = appdata / "GlassTranslator" / "argos-packages"
    root.mkdir(parents=True, exist_ok=True)
    for name in ("ARGOS_PACKAGES_DIR", "ARGOS_TRANSLATE_PACKAGE_DIR", "ARGOS_PACKAGE_DIR"):
        os.environ[name] = str(root)
    return root

def _print_environment() -> None:
    print("=" * 66)
    print("Glass Translator — نصب مدل آفلاین انگلیسی به فارسی")
    print("=" * 66)
    print(f"Python مورد استفاده: {sys.executable}")
    print(f"نسخه Python: {sys.version.split()[0]}")
    print(f"ARGOS_PACKAGES_DIR: {os.environ.get('ARGOS_PACKAGES_DIR', '(تنظیم نشده؛ مسیر پیش‌فرض Argos)')}")
    print(f"ARGOS_PACKAGE_DIR (سازگاری قدیمی): {os.environ.get('ARGOS_PACKAGE_DIR', '(تنظیم نشده)')}")
    print()


def _installed_translation(argos_translate):
    # Use the same multi-directory discovery as the running app, then refresh the
    # cached language graph (Argos caches get_installed_languages()).
    try:
        from translator import _configure_argos_search_paths, _refresh_argos_language_cache
        roots = _configure_argos_search_paths()
        print("مسیرهای جست‌وجوی مدل Argos:", " | ".join(str(path) for path in roots if path.exists()) or "هنوز مسیر موجودی پیدا نشده")
        _refresh_argos_language_cache(argos_translate)
    except Exception as exc:
        print(f"هشدار در بررسی مسیرهای Argos: {exc}")
        clear_cache = getattr(argos_translate.get_installed_languages, "cache_clear", None)
        if callable(clear_cache):
            clear_cache()
    languages = argos_translate.get_installed_languages()
    source_lang = next((lang for lang in languages if lang.code == SOURCE_CODE), None)
    target_lang = next((lang for lang in languages if lang.code == TARGET_CODE), None)
    translation = source_lang.get_translation(target_lang) if source_lang and target_lang else None
    return translation, languages


def _describe_installed_packages(argos_package) -> None:
    try:
        packages = argos_package.get_installed_packages()
        if not packages:
            print("بستهٔ زبانی نصب‌شده‌ای در محل فعلی Argos پیدا نشد.")
            return
        print("بسته‌های زبانی شناسایی‌شده:")
        for item in packages:
            print(f"  - {getattr(item, 'from_code', '?')} -> {getattr(item, 'to_code', '?')} | {getattr(item, 'package_version', '?')}")
    except Exception as exc:
        print(f"خواندن فهرست بسته‌های نصب‌شده ممکن نشد: {exc}")


def _package_url_from_index() -> list[str]:
    """Read official public index directly; supports common index JSON shapes."""
    response = requests.get(OFFICIAL_INDEX_URL, timeout=(10, 25), headers={"User-Agent": "GlassTranslator/0.2.7"})
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        records = payload.get("packages", payload.get("data", []))
        if not isinstance(records, list):
            records = []
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    urls: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("from_code") != SOURCE_CODE or record.get("to_code") != TARGET_CODE:
            continue
        links = record.get("links", [])
        if isinstance(links, str):
            links = [links]
        if isinstance(links, list):
            for link in links:
                if not isinstance(link, str):
                    continue
                if link.startswith("https://") and link not in urls:
                    urls.append(link)
                elif link.startswith("ipfs://"):
                    cid = link.removeprefix("ipfs://").strip()
                    for gateway in ("https://ipfs.io/ipfs/", "https://dweb.link/ipfs/"):
                        candidate = gateway + cid
                        if candidate not in urls:
                            urls.append(candidate)
    if KNOWN_OFFICIAL_MODEL_URL not in urls:
        urls.append(KNOWN_OFFICIAL_MODEL_URL)
    for gateway in ("https://ipfs.io/ipfs/", "https://dweb.link/ipfs/"):
        candidate = gateway + KNOWN_IPFS_CID
        if candidate not in urls:
            urls.append(candidate)
    return urls


def _links_to_urls(links: Any) -> list[str]:
    """Convert Argos model metadata links to HTTPS URLs."""
    if isinstance(links, str):
        links = [links]
    urls: list[str] = []
    if not isinstance(links, (list, tuple)):
        return urls
    for link in links:
        if not isinstance(link, str):
            continue
        if link.startswith("https://"):
            candidates = [link]
        elif link.startswith("ipfs://"):
            cid = link.removeprefix("ipfs://").strip()
            candidates = [f"https://ipfs.io/ipfs/{cid}", f"https://dweb.link/ipfs/{cid}"]
        else:
            candidates = []
        for url in candidates:
            if url not in urls:
                urls.append(url)
    return urls


def _unique_urls(urls: list[str]) -> list[str]:
    result: list[str] = []
    for url in urls:
        if url and url not in result:
            result.append(url)
    return result


def _download_model(urls: list[str]) -> Path:
    """Download with explicit timeouts and visible progress rather than Argos' unbounded downloader."""
    cache_root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GlassTranslator" / "models"
    cache_root.mkdir(parents=True, exist_ok=True)
    destination = cache_root / "translate-en_fa-1_5.argosmodel"
    errors: list[str] = []
    if destination.exists() and destination.stat().st_size >= 1_000_000 and zipfile.is_zipfile(destination):
        print(f"مدل قبلاً دریافت شده و فایل آن معتبر است: {destination}", flush=True)
        return destination

    urls = _unique_urls(urls)
    if not urls:
        raise RuntimeError("هیچ نشانی دانلود معتبری برای مدل پیدا نشد.")

    import time
    for index, url in enumerate(urls, start=1):
        print(f"منبع دانلود {index}/{len(urls)}: {url}", flush=True)
        temp_path = destination.with_suffix(destination.suffix + ".part")
        try:
            downloaded = 0
            last_reported_bucket = -1
            last_report_time = 0.0
            with requests.get(
                url,
                stream=True,
                timeout=(15, 45),
                headers={"User-Agent": "GlassTranslator/0.2.7"},
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length") or 0)
                if total > 0:
                    print(f"حجم مدل طبق سرور: {total / (1024 * 1024):.1f} MiB", flush=True)
                with temp_path.open("wb") as file:
                    for chunk in response.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        file.write(chunk)
                        downloaded += len(chunk)
                        now = time.monotonic()
                        if total > 0:
                            percent = min(100, int(downloaded * 100 / total))
                            bucket = percent // 5
                            if bucket > last_reported_bucket:
                                last_reported_bucket = bucket
                                print(f"پیشرفت دریافت: {percent}% ({downloaded / (1024 * 1024):.1f} MiB)", flush=True)
                        elif now - last_report_time >= 5:
                            last_report_time = now
                            print(f"دریافت‌شده: {downloaded / (1024 * 1024):.1f} MiB", flush=True)
            if temp_path.stat().st_size < 1_000_000 or not zipfile.is_zipfile(temp_path):
                raise RuntimeError("فایل دریافت‌شده مدل معتبر Argos نیست یا ناقص است.")
            temp_path.replace(destination)
            print(f"فایل مدل دریافت شد ({destination.stat().st_size / (1024 * 1024):.1f} MiB).", flush=True)
            return destination
        except Exception as exc:
            errors.append(f"{url} -> {type(exc).__name__}: {exc}")
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            print(f"این مسیر ناموفق بود: {type(exc).__name__}: {exc}", flush=True)

    raise RuntimeError("دریافت مدل از همهٔ نشانی‌ها شکست خورد:\n" + "\n".join(errors))


def _switch_app_to_offline() -> None:
    try:
        from config import load_settings, save_settings
        settings = load_settings()
        settings["mode"] = "offline"
        save_settings(settings)
        print("موتور پیش‌فرض برنامه روی Offline تنظیم شد.")
    except Exception as exc:
        print(f"مدل نصب شد، اما تنظیم خودکار موتور ممکن نشد: {exc}")
        print("برنامه را باز کن و در تنظیمات موتور Offline را انتخاب کن.")


def main() -> int:
    canonical_root = _configure_installer_environment()
    _print_environment()
    print(f"مخزن پایدار مدل: {canonical_root}")
    try:
        import argostranslate.package as argos_package
        import argostranslate.translate as argos_translate
    except ImportError:
        print("کتابخانه Argos در همین محیط پایتون نصب نیست.")
        print("از همین پوشه install_offline_model.bat را اجرا کن تا وابستگی داخل .venv نصب شود.")
        return 1

    print(f"کتابخانه Argos: {getattr(argos_translate, '__file__', '(مسیر نامشخص)')}")
    try:
        from translator import _configure_argos_search_paths
        roots = _configure_argos_search_paths()
        import argostranslate.settings as argos_settings
        print(f"مسیر نصب Argos: {getattr(argos_settings, 'package_data_dir', '(نامشخص)')}")
        print("مسیرهای جست‌وجوی Argos:", " | ".join(str(path) for path in roots))
    except Exception as exc:
        print(f"هشدار در تنظیم مسیر مشترک Argos: {type(exc).__name__}: {exc}")
    _describe_installed_packages(argos_package)

    try:
        translation, languages = _installed_translation(argos_translate)
        if translation is not None:
            print("مدل انگلیسی به فارسی از قبل نصب و قابل دسترسی است؛ تست واقعی اجرا می‌شود…")
            result = translation.translate("Hello.")
            if not isinstance(result, str) or not result.strip():
                print("مدل نصب است اما متن آزمایشی خروجی معتبری نداد.")
                return 4
            _switch_app_to_offline()
            print(f"تست مدل موفق بود: Hello. -> {result}")
            print("نصب کامل است. اکنون همین پوشه را با run_windows.bat اجرا کن.")
            return 0

        print("مدل مستقیم انگلیسی به فارسی در محیط فعلی نصب نیست؛ شروع دریافت…")
        urls: list[str] = []

        # Preferred route: read the Argos index, but download through a bounded
        # requests stream instead of package.download(), which in some Argos releases
        # uses urllib without a timeout or progress and can appear frozen here.
        download_attempt_started = False
        try:
            print("در حال به‌روزرسانی فهرست بسته‌های Argos…", flush=True)
            argos_package.update_package_index()
            available = argos_package.get_available_packages()
            package = next((item for item in available if item.from_code == SOURCE_CODE and item.to_code == TARGET_CODE), None)
            if package is not None:
                print(f"بستهٔ رسمی پیدا شد: {SOURCE_CODE} -> {TARGET_CODE}", flush=True)
                download_attempt_started = True
                urls = _links_to_urls(getattr(package, "links", []))
                urls.extend([KNOWN_OFFICIAL_MODEL_URL,
                             f"https://ipfs.io/ipfs/{KNOWN_IPFS_CID}",
                             f"https://dweb.link/ipfs/{KNOWN_IPFS_CID}"])
                urls = _unique_urls(urls)
                print("نشانی‌های مدل از فهرست Argos:", " | ".join(urls) or "هیچ‌کدام", flush=True)
                model_path = _download_model(urls)
                print("در حال نصب مدل دریافت‌شده…", flush=True)
                argos_package.install_from_path(model_path)
                translation, _ = _installed_translation(argos_translate)
                if translation is not None:
                    result = translation.translate("Hello.")
                    if isinstance(result, str) and result.strip():
                        _switch_app_to_offline()
                        print(f"تست مدل موفق بود: Hello. -> {result}", flush=True)
                        print("نصب کامل است. اکنون همین پوشه را با run_windows.bat اجرا کن.", flush=True)
                        return 0
                raise RuntimeError("مدل نصب شد، اما پس از نصب مسیر en -> fa توسط Argos قابل استفاده نبود.")
            else:
                print("مدل در خروجی مدیر بسته پیدا نشد؛ فهرست رسمی مستقیم بررسی می‌شود.", flush=True)
        except Exception as exc:
            print(f"دانلود/نصب از مسیر اصلی Argos ناموفق بود: {type(exc).__name__}: {exc}", flush=True)
            if download_attempt_started:
                # A bounded, progress-reporting download was already attempted across all
                # URLs; avoid silently repeating the same long download sequence.
                raise
            # If the Argos index itself was unavailable, fall through to the public index.

        # Fallback route: official public JSON index plus direct model URL.
        try:
            urls = _package_url_from_index()
        except Exception as exc:
            print(f"خواندن فهرست رسمی GitHub ناموفق بود: {exc}")
            urls = [KNOWN_OFFICIAL_MODEL_URL]

        model_path = _download_model(urls)
        print("در حال نصب فایل مدل در مخزن Argos…")
        argos_package.install_from_path(model_path)

        translation, languages = _installed_translation(argos_translate)
        if translation is None:
            print("فایل نصب شد، اما مسیر ترجمه در Argos دیده نمی‌شود.")
            print("زبان‌های فعلی Argos:", ", ".join(f"{lang.code} ({lang.name})" for lang in languages) or "هیچ‌کدام")
            _describe_installed_packages(argos_package)
            print("برنامه را از همان پوشه‌ای اجرا کن که این فایل نصب را اجرا کردی؛ هر دو باید از یک .venv استفاده کنند.")
            return 3

        print("در حال اجرای تست واقعی ترجمهٔ آفلاین…")
        result = translation.translate("Hello.")
        if not isinstance(result, str) or not result.strip():
            print("مدل نصب شده، اما تست ترجمه خروجی معتبری برنگرداند.")
            return 4

        _switch_app_to_offline()
        print(f"تست مدل موفق بود: Hello. -> {result}")
        print("نصب کامل است. پس از نصب، ترجمه‌های Offline به اینترنت یا LM Studio نیاز ندارند.")
        print("برای جلوگیری از اشتباه مسیر، برنامه را با run_windows.bat همین پوشه اجرا کن.")
        print("یادآوری: Argos سبک‌تر است، اما کیفیت ترجمه ممکن است از Google یا مدل زبانی بزرگ پایین‌تر باشد.")
        return 0

    except Exception as exc:
        print("\nنصب یا آزمایش مدل آفلاین موفق نشد.")
        print(f"جزئیات فنی: {type(exc).__name__}: {exc}")
        print("بررسی کن همین پوشهٔ پروژه در حال اجرا باشد و اینترنت هنگام دریافت فایل مدل وصل باشد.")
        print("اگر دوباره خطا دیدی، تمام متن این پنجره را بفرست؛ بخش Python و خطای آخر برای تشخیص کافی است.")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
