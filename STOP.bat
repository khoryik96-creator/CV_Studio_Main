@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo Stopping The 郭 Lab CV Studio...
echo.
if exist "%~dp0STOP_CORE.ps1" goto :stopCorePresent
echo ERROR: STOP_CORE.ps1 is missing. Re-extract the package.
echo.
pause
exit /b 1

:stopCorePresent
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0STOP_CORE.ps1" -Root "%~dp0"
set "RC=%ERRORLEVEL%"
echo.
echo Done.
echo.
pause
exit /b %RC%
