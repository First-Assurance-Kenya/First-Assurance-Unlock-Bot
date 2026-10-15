@echo off
chcp 65001 >nul
title First Assurance - Stop All Services
cls
echo =====================================================================
echo  Stopping First Assurance Account Unlock Services...
echo =====================================================================
echo.

echo [1/3] Stopping Dev Tunnel...
taskkill /f /im devtunnel.exe 2>nul
if %errorlevel% equ 0 (echo  - Dev Tunnel stopped.) else (echo  - Dev Tunnel was not running.)

echo.
echo [2/3] Stopping Teams Bot (Port 3978)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3978 ^| findstr LISTENING') do (
    taskkill /f /pid %%a 2>nul
    echo  - Stopped process %%a on port 3978.
)

echo.
echo [3/3] Stopping Backend API (Port 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a 2>nul
    echo  - Stopped process %%a on port 8000.
)

echo.
echo =====================================================================
echo  All services stopped cleanly.
echo =====================================================================
echo.
pause
