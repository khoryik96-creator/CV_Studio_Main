@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0INSTALL_RECEIPT.ps1" goto :denied
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_RECEIPT.ps1" -Mode Verify >nul 2>&1
if errorlevel 1 goto :denied
if /i "%~1"=="--wait" goto :wait_for_start
start "" wscript.exe "%~dp0START_HIDDEN.vbs"
exit /b 0

:wait_for_start
cscript.exe //nologo "%~dp0START_HIDDEN.vbs"
exit /b %ERRORLEVEL%

:denied
echo.
echo CV Studio is not authorized on this computer.
echo Run INSTALL.bat and enter the current 6-digit Authy code first.
echo.
pause
exit /b 13
