@echo off
rem TWK Momentum EA installer - runs install.ps1 next to this file.
rem Extra arguments are passed through, e.g.:  install.bat -DataFolder "C:\path\to\data folder"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
