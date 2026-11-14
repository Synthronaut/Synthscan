@echo off
rem One-shot Windows read-rights/header check; no memory scan or game changes.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start_read_access_probe.ps1"
