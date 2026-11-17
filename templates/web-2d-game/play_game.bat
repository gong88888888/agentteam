@echo off
setlocal
cd /d "%~dp0"
set "PORT=8787"
echo Starting 迷宫冒险家 at http://localhost:%PORT%/
start "" cmd /c "timeout /t 2 >nul & start http://localhost:%PORT%/"
python -m http.server %PORT% --bind 127.0.0.1
