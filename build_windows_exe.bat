@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Glass Translator 0.2.10 - Windows EXE Builder
for /f "usebackq delims=" %%V in ("%~dp0VERSION") do set "APP_VERSION=%%V"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "ARGOS_SOURCE=%APPDATA%\GlassTranslator\argos-packages"
set "OCR_SOURCE=%USERPROFILE%\.EasyOCR\model"
set "STAGE=%~dp0build_staging"

if not exist "%~dp0main.py" (
  echo [ERROR] main.py was not found. Extract the complete source package first.
  pause
  exit /b 1
)
if not exist "%~dp0GlassTranslator.spec" (
  echo [ERROR] GlassTranslator.spec was not found.
  pause
  exit /b 1
)

if not exist "%VENV_PY%" (
  echo [INFO] Creating a Python 3.11 virtual environment for building...
  where py >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python Launcher not found. Install Python 3.11 x64 to BUILD the EXE.
    echo The final EXE does not require Python to be installed on its target PC.
    pause
    exit /b 1
  )
  py -3.11 -m venv "%~dp0.venv"
  if errorlevel 1 goto failed
)

set "ARGOS_PACKAGES_DIR=%APPDATA%\GlassTranslator\argos-packages"
set "ARGOS_PACKAGE_DIR=%ARGOS_PACKAGES_DIR%"
set "ARGOS_TRANSLATE_PACKAGE_DIR=%ARGOS_PACKAGES_DIR%"
if not exist "%ARGOS_PACKAGES_DIR%" mkdir "%ARGOS_PACKAGES_DIR%"

echo.
echo ================================================================
echo Glass Translator %APP_VERSION% - Windows x64 EXE Builder
echo ================================================================
echo.

echo [1/7] Installing/checking build dependencies...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto failed
"%VENV_PY%" -m pip install -r requirements.txt -r requirements-offline.txt "pyinstaller>=6.10,<7"
if errorlevel 1 goto failed

echo.
echo [2/7] Running automated tests...
"%VENV_PY%" -m unittest discover -s tests -v
if errorlevel 1 goto failed

echo.
echo [3/7] Staging locally installed models for a self-contained build...
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%"
if exist "%ARGOS_SOURCE%" (
  mkdir "%STAGE%\argos-packages"
  xcopy "%ARGOS_SOURCE%\*" "%STAGE%\argos-packages\" /E /I /H /Y >nul
  echo [OK] Argos model files staged from %ARGOS_SOURCE%
) else (
  echo [WARN] Argos model folder was not found. Offline translation will need a model on the target PC.
)
if exist "%OCR_SOURCE%\craft_mlt_25k.pth" if exist "%OCR_SOURCE%\english_g2.pth" (
  mkdir "%STAGE%\easyocr-models"
  xcopy "%OCR_SOURCE%\*" "%STAGE%\easyocr-models\" /E /I /H /Y >nul
  echo [OK] EasyOCR models staged from %OCR_SOURCE%
) else (
  echo [WARN] EasyOCR model files were not found in %OCR_SOURCE%.
  echo        OCR may download its model files on first run.
)

echo.
echo [4/7] Building the application with PyInstaller...
"%VENV_PY%" -m PyInstaller --noconfirm --clean "GlassTranslator.spec"
if errorlevel 1 goto failed
if not exist "%~dp0dist\GlassTranslator\GlassTranslator.exe" (
  echo [ERROR] PyInstaller finished but the EXE was not found.
  goto failed
)

echo.
echo [5/7] Adding portable launcher and Persian guide...
copy /Y "%~dp0run_portable_windows.bat" "%~dp0dist\GlassTranslator\run_portable_windows.bat" >nul
copy /Y "%~dp0README_FA.md" "%~dp0dist\GlassTranslator\README_FA.md" >nul
copy /Y "%~dp0README_BUILD_EXE_FA.md" "%~dp0dist\GlassTranslator\README_BUILD_EXE_FA.md" >nul
if not exist "%~dp0dist\GlassTranslator\data" mkdir "%~dp0dist\GlassTranslator\data"

echo.
echo [6/7] Creating the distributable ZIP...
if exist "%~dp0GlassTranslator_Windows_x64_v%APP_VERSION%.zip" del /q "%~dp0GlassTranslator_Windows_x64_v%APP_VERSION%.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%~dp0dist\GlassTranslator\*' -DestinationPath '%~dp0GlassTranslator_Windows_x64_v%APP_VERSION%.zip' -Force"
if errorlevel 1 (
  echo [WARN] EXE was built but ZIP creation failed. Keep the complete dist\GlassTranslator folder.
) else (
  echo [OK] ZIP created.
)
echo.
echo [7/7] Checking for Inno Setup to build an installer with an uninstaller...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "!ISCC!" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "!ISCC!" (
  "!ISCC!" /DAppVersion=%APP_VERSION% "%~dp0GlassTranslator.iss"
  if errorlevel 1 (
    echo [WARN] EXE and ZIP were built, but Inno Setup failed to create the installer.
  ) else (
    echo [OK] Installer: %~dp0installer_output\GlassTranslator_Setup_x64_v%APP_VERSION%.exe
  )
) else (
  echo [SKIP] Inno Setup 6 was not found. Install it to also create Setup.exe with uninstaller.
)
if exist "%STAGE%" rmdir /s /q "%STAGE%"

echo.
echo ================================================================
echo BUILD SUCCESSFUL
echo EXE: %~dp0dist\GlassTranslator\GlassTranslator.exe
echo ZIP: %~dp0GlassTranslator_Windows_x64_v%APP_VERSION%.zip
echo Installer if built: %~dp0installer_output\GlassTranslator_Setup_x64_v%APP_VERSION%.exe
echo Standard run: double-click GlassTranslator.exe
echo Portable run: double-click run_portable_windows.bat
echo Keep the entire output folder together; do not copy only the EXE.
echo ================================================================
pause
exit /b 0

:failed
echo.
echo BUILD FAILED. Keep the error text shown above and share it for diagnosis.
echo The build staging folder, if created, has been retained for inspection.
pause
exit /b 1
