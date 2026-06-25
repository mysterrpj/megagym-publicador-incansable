@echo off
setlocal
cd /d "%~dp0"

echo Abriendo panel local MEGAGYM...
start "MEGAGYM Admin Server" cmd /k "cd /d ""%~dp0"" && python admin_server.py"

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8787"
