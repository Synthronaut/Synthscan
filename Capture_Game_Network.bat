@echo off
rem One-time Windows administrator prompt; captures only the game server UDP flow.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\capture_game_network.ps1" -Elevate
