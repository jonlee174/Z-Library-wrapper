@echo off
REM Thin wrapper so you can double-click to install on Windows.
powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
