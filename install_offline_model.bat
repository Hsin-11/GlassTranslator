@echo off
setlocal
cd /d "%~dp0"
set "ARGOS_PACKAGES_DIR=%APPDATA%\GlassTranslator\argos-packages"
set "ARGOS_PACKAGE_DIR=%ARGOS_PACKAGES_DIR%"
set "ARGOS_TRANSLATE_PACKAGE_DIR=%ARGOS_PACKAGES_DIR%"
if not exist "%ARGOS_PACKAGES_DIR%" mkdir "%ARGOS_PACKAGES_DIR%"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] This project's .venv was not found.
  echo First run setup_windows.bat from this same folder.
  pause
  exit /b 1
)
echo Installing/checking Argos in:
echo %VENV_PY%
echo.
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto failed
"%VENV_PY%" -m pip install -r requirements-offline.txt
if errorlevel 1 goto failed
"%VENV_PY%" install_offline_model.py
if errorlevel 1 goto failed
echo.
echo Offline English-to-Persian translation is installed and tested.
echo Run run_windows.bat from this same folder.
pause
exit /b 0
:failed
echo.
echo Offline model setup failed. Keep this window open and send the full error text.
pause
exit /b 1
