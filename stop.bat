@echo off
title Stop Maharashtra Skill Intelligence Platform
cd /d "%~dp0"

echo ====================================================================
echo   Stopping Maharashtra Skill Intelligence Platform...
echo ====================================================================
echo.

powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort 3000, 8000 -ErrorAction SilentlyContinue).OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"

echo Services on ports 3000 and 8000 have been stopped.
timeout /t 2 /nobreak >nul
