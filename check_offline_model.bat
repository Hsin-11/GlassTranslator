@echo off
setlocal
cd /d "%~dp0"
set "ARGOS_PACKAGES_DIR=%APPDATA%\GlassTranslator\argos-packages"
set "ARGOS_PACKAGE_DIR=%ARGOS_PACKAGES_DIR%"
set "ARGOS_TRANSLATE_PACKAGE_DIR=%ARGOS_PACKAGES_DIR%"
if not exist "%ARGOS_PACKAGES_DIR%" mkdir "%ARGOS_PACKAGES_DIR%"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] .venv was not found. First run setup_windows.bat.
  pause
  exit /b 1
)
"%VENV_PY%" check_offline_model.py
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Offline model check failed with code %RESULT%. Send the full report above.
pause
exit /b %RESULT%
