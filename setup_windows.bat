@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher was not found. Install Python 3.11 x64 first.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo Could not create a Python 3.11 environment. Check your Python installation.
    pause
    exit /b 1
  )
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto failed
pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Setup finished. Run run_windows.bat to start Glass Translator.
pause
exit /b 0
:failed
echo.
echo Installation failed. Check the internet connection and pip error above.
pause
exit /b 1
