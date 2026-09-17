@echo off
title Maharashtra Skill Intelligence Platform
cd /d "%~dp0"

echo ====================================================================
echo   Maharashtra Skill Intelligence Platform
echo   Starting Frontend (Port 3000) ^& FastAPI Backend (Port 8000)...
echo ====================================================================
echo.

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not found. Please install Node.js to continue.
    pause
    exit /b
)

:: Launch server.js in background window
start "SIH Web Platform" /b cmd /c "node server.js"

:: Give the server a moment to bind and open default browser
timeout /t 3 /nobreak >nul
start http://localhost:3000/

echo.
echo ====================================================================
echo   Platform is running!
echo   - Web URL:    http://localhost:3000/
echo   - Login ID:   admin
echo   - Password:   SIH2026
echo.
echo   To stop all services: Double-click stop.bat
echo ====================================================================
echo.
pause
