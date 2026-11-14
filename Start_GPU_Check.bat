@echo off
cd /d "%~dp0"
"C:\Python314\python.exe" -B -u "%~dp0tools\gpu_diagnostics.py"
echo.
pause
