@echo off
cd /d "%~dp0"
python updater.py --apply-latest
if errorlevel 1 pause
