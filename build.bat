@echo off
REM SPDX-License-Identifier: Apache-2.0
REM Build GuitarFX.exe with PyInstaller (run after activating .venv via setup.bat)
setlocal

if not exist ".venv\Scripts\python.exe" (
    echo [build] .venv not found - run setup.bat first.
    exit /b 1
)

call .venv\Scripts\activate.bat

echo [build] Ensuring PyInstaller is installed...
python -m pip install --quiet pyinstaller

echo [build] Building GuitarFX.exe (console build for testing)...
python -m PyInstaller --noconfirm --clean --onefile --name GuitarFX ^
  --collect-submodules skins ^
  --collect-all sounddevice ^
  --add-data "skins/stage/theme.json;skins/stage" ^
  --add-data "skins/classic/theme.json;skins/classic" ^
  --add-data "skins/neon/theme.json;skins/neon" ^
  main.py

if errorlevel 1 (
    echo [build] FAILED.
    exit /b 1
)

echo.
echo [build] Done -^> dist\GuitarFX.exe
echo [build] For the final clean build, add  --windowed  to hide the console.
endlocal
