@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Guard.ps1" status
pause
