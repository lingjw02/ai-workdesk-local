@echo off
rem ============================================================
rem  AI WorkDesk OS - long-running server launcher (Windows)
rem  Double-click to start. Keeps the server alive and logs to
rem  data/server.log. Close the window to stop.
rem ============================================================
cd /d "%~dp0"

set "PY="
if exist "venv\Scripts\python.exe" (
  set "PY=venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
)

if "%PY%"=="" (
  echo [ERROR] Virtualenv not found.
  echo Run: python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

if not exist data mkdir data
echo [OK] Starting AI WorkDesk OS on http://localhost:3787
echo [OK] Logs: data\server.log  (Ctrl+C to stop)
"%PY%" main.py >> data\server.log 2>&1
