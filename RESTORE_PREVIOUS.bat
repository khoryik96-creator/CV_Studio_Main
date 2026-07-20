@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Restore Previous CV Studio
echo Restoring the previous healthy CV Studio release...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RESTORE_PREVIOUS.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Restore complete. Launch CV Studio from the normal Desktop shortcut.
) else (
  echo Restore did not complete. No unsafe partial switch was kept.
)
echo.
pause
exit /b %RC%
