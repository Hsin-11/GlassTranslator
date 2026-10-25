@echo off
setlocal
cd /d "%~dp0"
set "GLASSTRANSLATOR_PORTABLE=1"
if not exist "GlassTranslator.exe" (
  echo GlassTranslator.exe was not found in this folder.
  echo Build the app first with build_windows_exe.bat.
  pause
  exit /b 1
)
start "" "%~dp0GlassTranslator.exe"
exit /b 0
