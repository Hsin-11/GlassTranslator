@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Glass Translator - Build Windows EXE
for /f "usebackq delims=" %%V in ("%~dp0VERSION") do set "APP_VERSION=%%V"

if not exist "%~dp0main.py" (
  echo [ERROR] main.py was not found. Run this script from the full source bundle.
  pause
  exit /b 1
)
if not exist "%~dp0GlassTranslator.spec" (
  echo [ERROR] GlassTranslator.spec was not found.
  pause
  exit /b 1
)
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo [ERROR] The project's .venv was not found.
  echo First run setup_windows.bat and allow installation to finish.
  pause
  exit /b 1
)

set "ARGOS_PACKAGES_DIR=%APPDATA%\GlassTranslator\argos-packages"
set "ARGOS_PACKAGE_DIR=%ARGOS_PACKAGES_DIR%"
set "ARGOS_TRANSLATE_PACKAGE_DIR=%ARGOS_PACKAGES_DIR%"
if not exist "%ARGOS_PACKAGES_DIR%" mkdir "%ARGOS_PACKAGES_DIR%"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

echo ================================================================
echo Glass Translator %APP_VERSION% - Windows x64 EXE Builder
echo ================================================================
echo Project: %~dp0
echo Python:  %VENV_PY%
echo Argos model directory: %ARGOS_PACKAGES_DIR%
echo.

echo [1/5] Checking the required runtime packages...
"%VENV_PY%" -c "import PySide6, PySide6.QtSvg, easyocr, torch, torchvision, argostranslate, mss, numpy, PIL, requests, pynput; print('Dependencies OK')"
if errorlevel 1 goto failed

echo.
echo [2/5] Running the automated tests...
"%VENV_PY%" -m unittest discover -s tests -v
if errorlevel 1 goto failed

echo.
echo [3/5] Installing/checking PyInstaller...
"%VENV_PY%" -m pip install "pyinstaller>=6.10,<7"
if errorlevel 1 goto failed

echo.
echo [4/5] Building GlassTranslator.exe in onedir mode...
"%VENV_PY%" -m PyInstaller --noconfirm --clean "GlassTranslator.spec"
if errorlevel 1 goto failed
if not exist "%~dp0dist\GlassTranslator\GlassTranslator.exe" (
  echo [ERROR] PyInstaller returned, but the EXE was not found.
  goto failed
)

echo.
echo [5/5] Packaging the complete dist folder as a ZIP...
if exist "%~dp0GlassTranslator_Windows_x64.zip" del /q "%~dp0GlassTranslator_Windows_x64.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%~dp0dist\GlassTranslator\*' -DestinationPath '%~dp0GlassTranslator_Windows_x64.zip' -Force"
if errorlevel 1 (
  echo [WARN] The EXE folder was built, but ZIP creation failed.
  echo Keep the complete dist\GlassTranslator folder.
) else (
  echo Release ZIP created: %~dp0GlassTranslator_Windows_x64.zip
)

echo.
echo ================================================================
echo BUILD SUCCESSFUL
echo EXE: %~dp0dist\GlassTranslator\GlassTranslator.exe
echo Keep the whole dist\GlassTranslator folder. Do not copy only the EXE.
echo The Argos language model and user settings remain under %%APPDATA%%.
echo ================================================================
pause
exit /b 0

:failed
echo.
echo BUILD FAILED. Read and save the full error output above.
echo Do not delete .venv or the installed Argos model to try to fix the build.
pause
exit /b 1
