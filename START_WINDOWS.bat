@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- One-click local run (Windows) ---
REM Requires: Python 3.11+ installed and on PATH.

if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create venv. Make sure Python is installed.
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies.
  pause
  exit /b 1
)

REM Generate a default SESSION_SECRET if not set
if not exist ".env" (
  echo Creating .env...
  python tools\gen_env.py
)

echo Starting server...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
