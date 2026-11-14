@echo off
cd /d "%~dp0"
python -B tools\probe_reputation_service.py --query-own --all
if errorlevel 1 goto done
python -B tools\build_reputation_report.py
:done
pause
