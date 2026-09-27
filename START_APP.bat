@echo off
rem InterviewIQ - start backend (:8000) + frontend (:3001) and open the app.
rem Double-click this file from Explorer; works regardless of folder or spaces.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo Starting InterviewIQ backend (:8000)...
powershell -NoProfile -Command "Start-Process -FilePath '%ROOT%\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory '%ROOT%\backend' -WindowStyle Hidden"

echo Starting InterviewIQ frontend (:3001)...
powershell -NoProfile -Command "Start-Process -FilePath '%ROOT%\.venv\Scripts\python.exe' -ArgumentList '-m','serve_frontend','3001' -WorkingDirectory '%ROOT%\scripts' -WindowStyle Hidden"

echo Waiting for servers to come up...
timeout /t 8 /nobreak >nul

echo Opening http://localhost:3001 ...
start "" "http://localhost:3001"

echo.
echo InterviewIQ is running:
echo   App      : http://localhost:3001
echo   API docs : http://localhost:8000/docs
echo   Stop     : double-click STOP_APP.bat
echo (you can close this window - servers keep running)
timeout /t 5 /nobreak >nul
