@echo off
cd /d "%~dp0"
python -B tools\probe_reputation_service.py --query-own --all
if errorlevel 1 goto done
python -B tools\sync_reputation_names.py --apply
if errorlevel 1 goto done
python -B tools\build_reputation_report.py
echo.
echo Organization names updated on disk. The game must reload localization to display them.
echo These are snapshot values, not a live counter in the running game.
:done
pause
