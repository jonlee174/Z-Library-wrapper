@echo off
REM One-click build + install on Windows (double-click me).
python "%~dp0build.py" --install %*
pause
