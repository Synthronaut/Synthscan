@echo off
cd /d "%~dp0"
python -B tools\prepare_native_displayinfo.py install
if errorlevel 1 goto end
echo.
echo Test profile installed. Restart Star Citizen to load it.
echo F14 requests DisplayInfo ON; F15 requests OFF without opening the console.
echo This path is experimental and has not yet been validated in the live game.
echo Automatic sampling is disabled.
:end
pause
