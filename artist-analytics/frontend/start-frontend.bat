@echo off
REM Double-click to install (first time) and start the frontend at http://localhost:5173
cd /d "%~dp0"
if not exist node_modules (
  echo Installing packages, this takes a minute the first time...
  call npm.cmd install
  if errorlevel 1 (
    echo.
    echo npm install failed. Copy the error above and send it to Claude.
    pause
    exit /b 1
  )
)
start "" http://localhost:5173
call npm.cmd run dev
pause
