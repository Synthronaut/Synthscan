@echo off
cd /d "%~dp0"
python -B tools\refresh_game_reference.py
if errorlevel 1 echo Reference refresh failed. Please see the error above.
pause
