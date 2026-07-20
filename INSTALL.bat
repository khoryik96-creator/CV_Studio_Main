@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title The Guok's Lab - Setup
color 0A
set "GUOLAB_INSTALL_WRAPPED=1"
set "LOG=%~dp0install_log.txt"
set "CVSTUDIO_INSTALL_DIR=%~dp0"
powershell.exe -NoProfile -Command "$p=$env:CVSTUDIO_INSTALL_DIR; if ($p.Length -gt 210) { exit 9 } else { exit 0 }" >nul 2>&1
set "PATHCHECK_RC=%ERRORLEVEL%"
if "%PATHCHECK_RC%"=="9" goto :pathTooLong
if not "%PATHCHECK_RC%"=="0" echo WARNING: Could not run the optional folder-length check. Installation will continue.
goto :pathCheckDone

:pathTooLong
echo ERROR: This folder path is too long for reliable Windows installation.
echo Current folder: "%CVSTUDIO_INSTALL_DIR%"
echo Move the extracted cv_formatter folder to a short path such as:
echo C:\CVStudio\cv_formatter
echo Then run INSTALL.bat again.
echo.
echo Press any key to close this window...
pause >nul
exit /b 9

:pathCheckDone

echo ============================================
echo   The Guok's Lab - First Time Setup
echo ============================================
echo.
echo This installer requires the current 6-digit Authy code.
echo This window will stay open after install.
echo Ask the administrator for the current rotating code.
echo Log file: %LOG%
echo.

if exist "%~dp0INSTALL_CORE.bat" goto :installCorePresent
echo ERROR: INSTALL_CORE.bat is missing.
echo Please re-extract the ZIP and run INSTALL.bat again.
echo.
echo Press any key to close this window...
pause >nul
exit /b 1

:installCorePresent
call "%~dp0INSTALL_CORE.bat"
set "RC=%ERRORLEVEL%"

echo.
echo ============================================
if "%RC%"=="0" (
    echo   Setup wrapper finished.
) else (
    echo   Setup finished with exit code %RC%.
    echo   Review the messages above and install_log.txt before closing.
)
echo ============================================
echo.
echo Press any key to close this window...
pause >nul
exit /b %RC%
