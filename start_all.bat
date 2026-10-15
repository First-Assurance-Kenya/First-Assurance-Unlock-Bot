@echo off
chcp 65001 >nul
title First Assurance - Account Unlock System Launcher
cls
echo =====================================================================
echo       FIRST ASSURANCE - IT ACCOUNT UNLOCK SYSTEM
echo               Insure • Secure • Assure
echo =====================================================================
echo.
echo [1/3] Starting Dev Tunnel (Teams Cloud Bridge)...
start "1. Dev Tunnel (Teams Cloud Bridge)" cmd /k "title Dev Tunnel ^& echo Starting tunnel spiffy-fog-m1hf0t6... ^& devtunnel host spiffy-fog-m1hf0t6"
timeout /t 3 /nobreak >nul

echo [2/3] Starting Teams Bot Server (Port 3978)...
start "2. Teams Bot Server (Port 3978)" cmd /k "title Teams Bot Server ^& echo Starting Teams Bot on port 3978... ^& python bot/teams_app.py"
timeout /t 2 /nobreak >nul

echo [3/3] Starting Backend REST API (Port 8000 - Optional)...
start "3. Backend API & Swagger (Port 8000)" cmd /k "title Backend REST API ^& echo Starting Swagger API on port 8000... ^& python -m uvicorn backend.main:app --reload --port 8000"

echo.
echo =====================================================================
echo  All services have been launched in separate windows!
echo.
echo  • Dev Tunnel : https://vrt0glbb-3978.uks1.devtunnels.ms
echo  • Teams Bot  : http://localhost:3978
echo  • API Docs   : http://localhost:8000/docs
echo.
echo  To stop everything at once, double-click stop_all.bat
echo =====================================================================
echo.
pause
