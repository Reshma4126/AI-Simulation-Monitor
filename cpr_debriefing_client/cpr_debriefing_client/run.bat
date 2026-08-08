@echo off
title CPR Debriefing System — Launcher
color 0A

echo.
echo  ============================================================
echo    CPR Debriefing System
echo  ============================================================
echo.

REM ── Check Docker is installed and running ─────────────────────────────────
docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    color 0C
    echo  [ERROR] Docker Desktop is not running or not installed.
    echo.
    echo  Please install Docker Desktop from:
    echo  https://www.docker.com/products/docker-desktop/
    echo.
    echo  After installing, start Docker Desktop and run this script again.
    echo.
    pause
    exit /b 1
)
echo  [OK] Docker is running.

REM ── Detect NVIDIA GPU ─────────────────────────────────────────────────────
nvidia-smi >nul 2>&1
IF %ERRORLEVEL% == 0 (
    echo  [OK] NVIDIA GPU detected — starting in GPU mode.
    echo.
    set COMPOSE_CMD=docker compose -f docker-compose.yml -f docker-compose.gpu.yml
) ELSE (
    echo  [INFO] No NVIDIA GPU found — starting in CPU mode.
    echo.
    set COMPOSE_CMD=docker compose -f docker-compose.yml
)

REM ── Create .env if not present (API keys are optional for JSON mode) ─────────
IF EXIST .env (
    echo  [OK] Found .env — environment variables loaded.
) ELSE (
    IF EXIST .env.example (
        copy .env.example .env >nul
        echo  [OK] Created .env from defaults. App works without API keys for JSON mode.
    ) ELSE (
        echo  [INFO] No .env file — using built-in defaults.
    )
)


echo.
echo  Starting services (first run may take 5-10 min to download Ollama model)...
echo  ============================================================
echo.

REM ── Pull latest images and start ─────────────────────────────────────────
%COMPOSE_CMD% pull ollama
%COMPOSE_CMD% up --build -d

IF %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo  [ERROR] Failed to start services. Check the logs:
    echo    docker compose logs
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo  Services are starting up...
echo  The app will be ready at: http://localhost:5000
echo.
echo  Waiting for the app to be ready...

REM ── Poll until the app responds ───────────────────────────────────────────
:wait_loop
timeout /t 3 /nobreak >nul
curl -sf http://localhost:5000 >nul 2>&1
IF %ERRORLEVEL% == 0 goto app_ready
goto wait_loop

:app_ready
echo  [OK] App is ready!
echo  ============================================================
echo.

REM ── Open browser ─────────────────────────────────────────────────────────
start "" http://localhost:5000

echo  Press any key to view live logs (Ctrl+C to stop viewing, app keeps running).
pause >nul
%COMPOSE_CMD% logs -f app

