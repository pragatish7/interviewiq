@echo off
rem InterviewIQ - stop backend (:8000) and frontend (:3001).
cd /d "%~dp0"

echo Stopping InterviewIQ servers...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 3001,8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo Done.
timeout /t 3 /nobreak >nul
