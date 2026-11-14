@echo off
cd /d "%~dp0"
python -B tools\prepare_native_displayinfo.py remove
pause
