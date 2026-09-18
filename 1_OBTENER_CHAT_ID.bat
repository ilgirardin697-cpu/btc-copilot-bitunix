@echo off
title BTC Copilot - Telegram setup
cd /d "%~dp0"

if not exist .venv (
    py -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python telegram_setup.py

echo.
pause
