@echo off
rem Reads game UDP ping/pong and player frame events until game exit. One UAC prompt.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start_live_network_probe.ps1"
