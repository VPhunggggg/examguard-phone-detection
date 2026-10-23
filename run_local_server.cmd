@echo off
set PORT=5000
set APP_HOST=127.0.0.1
cd /d "%~dp0"
python -B app.py
