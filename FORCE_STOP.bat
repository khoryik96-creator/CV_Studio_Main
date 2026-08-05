@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo Force-stopping CV Studio (orphaned/stale processes)...
echo.
if exist "%~dp0FORCE_STOP.ps1" goto :forceCorePresent
echo ERROR: FORCE_STOP.ps1 is missing. Re-extract the package.
echo.
pause
exit /b 1

:forceCorePresent
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0FORCE_STOP.ps1" -Root "%~dp0"
set "RC=%ERRORLEVEL%"
echo.
echo Done.
echo.
pause
exit /b %RC%
