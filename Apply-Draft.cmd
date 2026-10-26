@echo off
if "%~1"=="" (
  echo Drag a draft TOML file onto this command, or pass its path.
  pause
  exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Guard.ps1" apply "%~1"
pause
