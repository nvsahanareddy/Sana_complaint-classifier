@echo off
title Smart Complaint Assistant - Backend

echo Starting Smart Complaint Assistant Backend...
echo Keep this window open. Wait for the line: Application startup complete

cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    pause
    exit /b 1
)

rem If the sentence model is already downloaded, do not contact huggingface.co at start-up
rem (a slow or blocked connection makes start-up wait for a very long time).
if exist "%USERPROFILE%\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2" (
    set HF_HUB_OFFLINE=1
    set TRANSFORMERS_OFFLINE=1
)

rem --reload-dir app : only watch the code folder. Every reload loads the model again (slow),
rem so remove "--reload --reload-dir app" if you are not editing the code.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app

pause