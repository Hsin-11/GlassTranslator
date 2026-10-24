@echo off
setlocal
cd /d "%~dp0"
title Glass Translator - Automated Tests
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] The project virtual environment is missing.
  echo Run setup_windows.bat first.
  pause
  exit /b 1
)
echo Running the Glass Translator automated test suite...
echo.
"%~dp0.venv\Scripts\python.exe" -m unittest discover -s tests -v
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo All automated tests passed.
) else (
  echo Some tests failed. Send the complete report above when asking for help.
)
pause
exit /b %RESULT%
