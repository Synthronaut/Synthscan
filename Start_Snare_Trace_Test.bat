@echo off
cd /d "%~dp0"
python -B tools\snare_trace_probe.py --launch
pause
