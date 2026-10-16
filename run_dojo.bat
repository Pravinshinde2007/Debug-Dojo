@echo off
title Debug Dojo Launcher
echo ===================================================
echo               Starting Debug Dojo...
echo ===================================================

cd /d "%~dp0debug-dojo\backend"

echo Opening browser at http://127.0.0.1:8000 ...
start "" "http://127.0.0.1:8000"

echo Running Debug Dojo Backend & Sandbox Judge...
py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
