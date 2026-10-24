from __future__ import annotations

import os
import sys
from pathlib import Path


def configure_argos_environment() -> Path:
    """Force installer, checker and app to share one persistent model directory."""
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
    root = appdata / "GlassTranslator" / "argos-packages"
    root.mkdir(parents=True, exist_ok=True)
    for name in ("ARGOS_PACKAGES_DIR", "ARGOS_TRANSLATE_PACKAGE_DIR", "ARGOS_PACKAGE_DIR"):
        os.environ[name] = str(root)
    return root


def _get_translation(argos_translate):
    clear = getattr(argos_translate.get_installed_languages, "cache_clear", None)
    if callable(clear):
        clear()
    get_by_codes = getattr(argos_translate, "get_translation_from_codes", None)
    if callable(get_by_codes):
        try:
            found = get_by_codes("en", "fa")
            if found is not None:
                return found
        except Exception:
            pass
    languages = argos_translate.get_installed_languages()
    source = next((lang for lang in languages if getattr(lang, "code", None) == "en"), None)
    target = next((lang for lang in languages if getattr(lang, "code", None) == "fa"), None)
    return source.get_translation(target) if source and target else None


def _cached_model_archives(argos_settings) -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    candidates = [
        local / "GlassTranslator" / "models" / "translate-en_fa-1_5.argosmodel",
    ]
    downloads = getattr(argos_settings, "downloads_dir", None)
    if downloads:
        candidates.append(Path(downloads) / "translate-en_fa-1_5.argosmodel")
    result: list[Path] = []
    for path in candidates:
        try:
            if path.is_file() and path not in result:
                result.append(path)
        except OSError:
            continue
    return result


def main() -> int:
    canonical = configure_argos_environment()
    print("=" * 70)
    print("Glass Translator — بررسی و ترمیم مدل آفلاین")
    print("=" * 70)
    print(f"Python: {sys.executable}")
    print(f"مخزن اصلی مدل: {canonical}")
    print(f"ARGOS_PACKAGES_DIR: {os.environ['ARGOS_PACKAGES_DIR']}")

    try:
        import argostranslate
        import argostranslate.package as argos_package
        import argostranslate.settings as argos_settings
        import argostranslate.translate as argos_translate
        from translator import _configure_argos_search_paths, _refresh_argos_language_cache
    except Exception as exc:
        print(f"خطا در واردکردن Argos: {type(exc).__name__}: {exc}")
        return 1

    roots = _configure_argos_search_paths()
    print(f"Argos library: {getattr(argostranslate, '__file__', '(unknown)')}")
    print(f"Argos package_data_dir: {getattr(argos_settings, 'package_data_dir', '(نامشخص)')}")
    print("مسیرهای جست‌وجوی مدل:")
    for path in roots:
        print(f"  {'[موجود]' if path.is_dir() else '[نیست]'} {path}")

    def report_packages() -> list:
        try:
            found = argos_package.get_installed_packages()
        except Exception as exc:
            print(f"خواندن بسته‌های نصب‌شده ناموفق بود: {type(exc).__name__}: {exc}")
            return []
        print("بسته‌های شناسایی‌شده:")
        for item in found:
            print(f"  - {getattr(item, 'from_code', '?')} -> {getattr(item, 'to_code', '?')} | {getattr(item, 'package_path', '?')}")
        if not found:
            print("  (هیچ بسته‌ای توسط Argos پیدا نشد)")
        return found

    packages = report_packages()
    translation = _get_translation(argos_translate)

    # If the previous installer successfully downloaded the archive but the package
    # registration went into another directory, install the cached archive into the
    # canonical directory. This repair uses no network request.
    if translation is None:
        archives = _cached_model_archives(argos_settings)
        if archives:
            for archive in archives:
                try:
                    print(f"مسیر ترجمه هنوز دیده نمی‌شود؛ تلاش برای ثبت دوباره از فایل محلی: {archive}")
                    argos_package.install_from_path(archive)
                    _refresh_argos_language_cache(argos_translate)
                    translation = _get_translation(argos_translate)
                    if translation is not None:
                        print("مدل از فایل محلی در مخزن استاندارد ثبت شد.")
                        break
                except Exception as exc:
                    print(f"ثبت دوبارهٔ مدل از فایل محلی ناموفق بود: {type(exc).__name__}: {exc}")

    if translation is None:
        languages = argos_translate.get_installed_languages()
        print("زبان‌های کشف‌شده:", ", ".join(
            f"{getattr(lang, 'code', '?')} ({getattr(lang, 'name', '')})" for lang in languages
        ) or "هیچ زبان نصب‌شده‌ای گزارش نشد")
        print("بسته‌های شناسایی‌شده پس از بررسی:")
        report_packages()
        try:
            existing = list(canonical.iterdir())
            print("محتویات مخزن اصلی:", ", ".join(item.name for item in existing) or "خالی")
        except OSError as exc:
            print(f"خواندن مخزن اصلی ناموفق بود: {exc}")
        print("نتیجه: مسیر ترجمه en -> fa پیدا نشد.")
        print("اگر فایل .argosmodel ذخیره‌شده وجود ندارد، install_offline_model.bat را دوباره اجرا کن.")
        return 2

    try:
        result = translation.translate("Hello.")
        print(f"تست واقعی: Hello. -> {result}")
        if not isinstance(result, str) or not result.strip():
            print("نتیجه: مدل پاسخ خالی برگرداند.")
            return 3
    except Exception as exc:
        print(f"تست ترجمه شکست خورد: {type(exc).__name__}: {exc}")
        return 4

    print("نتیجه: مدل آفلاین آماده است.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
