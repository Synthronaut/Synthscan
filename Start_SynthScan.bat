@echo off
title SynthScan Native
cd /d "%~dp0"
start "" pythonw "%~dp0native_control.py" --launch
exit
