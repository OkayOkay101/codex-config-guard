@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Guard.ps1" restore
pause
