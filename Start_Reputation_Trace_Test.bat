@echo off
cd /d "%~dp0"
python -B tools\reputation_trace_probe.py --launch
pause
