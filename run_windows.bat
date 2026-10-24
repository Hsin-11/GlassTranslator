@echo off
setlocal
cd /d "%~dp0"
set "ARGOS_PACKAGES_DIR=%APPDATA%\GlassTranslator\argos-packages"
set "ARGOS_PACKAGE_DIR=%ARGOS_PACKAGES_DIR%"
set "ARGOS_TRANSLATE_PACKAGE_DIR=%ARGOS_PACKAGES_DIR%"
if not exist "%ARGOS_PACKAGES_DIR%" mkdir "%ARGOS_PACKAGES_DIR%"
if not exist .venv\Scripts\python.exe (
  echo First run setup_windows.bat to install dependencies.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python main.py
if errorlevel 1 (
  echo.
  echo The app stopped with an error. Read the message above.
  pause
)
