@echo off
setlocal
cd /d "%~dp0"

start "TalentGraph API" cmd /k "call npm run server"
start "TalentGraph Frontend" cmd /k "call npm run dev:web -- --host 127.0.0.1"

echo TalentGraph Evolution is starting...
echo Frontend: http://127.0.0.1:5173/signin
echo API:      http://127.0.0.1:3001/api/health
endlocal
