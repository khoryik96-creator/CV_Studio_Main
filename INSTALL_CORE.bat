@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title The Guok's Lab - Setup Core
color 0A
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
if /i not "%GUOLAB_INSTALL_WRAPPED%"=="1" echo Press any key to close this window...
if /i not "%GUOLAB_INSTALL_WRAPPED%"=="1" pause >nul
exit /b 9

:pathCheckDone

if exist "%~dp0INSTALL_CORE.ps1" goto :installPsPresent
echo ERROR: INSTALL_CORE.ps1 is missing.
echo Please re-extract the ZIP and run INSTALL.bat again.
echo.
if /i not "%GUOLAB_INSTALL_WRAPPED%"=="1" echo Press any key to close this window...
if /i not "%GUOLAB_INSTALL_WRAPPED%"=="1" pause >nul
exit /b 1

:installPsPresent
echo Running PowerShell installer core...
echo Log file: %LOG%
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_CORE.ps1"
set "RC=%ERRORLEVEL%"

if /i not "%GUOLAB_INSTALL_WRAPPED%"=="1" (
    echo.
    echo ============================================
    echo   Installer core finished with exit code %RC%.
    echo ============================================
    echo.
    echo Press any key to close this window...
    pause >nul
)
exit /b %RC%
