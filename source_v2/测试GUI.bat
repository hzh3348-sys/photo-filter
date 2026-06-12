@echo off
chcp 65001 >nul
cd /d "%~dp0"
python photo_filter_gui.py
pause
