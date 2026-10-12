@echo off
cd /d "%~dp0"
python restore_data.py
if errorlevel 1 pause
