@echo off
title CPR Debriefing System — Stop

echo.
echo  Stopping CPR Debriefing System...

docker compose down

echo.
echo  All services stopped. Your data (reports, uploads) is preserved.
echo.
pause
