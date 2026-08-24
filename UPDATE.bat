@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title CV Studio - Update

echo ============================================
echo   CV Studio - Update ^& Restart
echo ============================================
echo.

rem --- Locate git: PATH first, then GitHub Desktop, then Git for Windows ---
set "GIT="
for %%G in (git.exe) do if not defined GIT set "GIT=%%~$PATH:G"
if not defined GIT if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
if not defined GIT if exist "%ProgramFiles(x86)%\Git\cmd\git.exe" set "GIT=%ProgramFiles(x86)%\Git\cmd\git.exe"
if not defined GIT for /d %%D in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do if exist "%%D\resources\app\git\cmd\git.exe" set "GIT=%%D\resources\app\git\cmd\git.exe"

if not defined GIT (
  echo Could not find git automatically.
  echo Open GitHub Desktop, click Fetch origin then Pull, then run this file again.
  echo The app will still start on the current version.
  echo.
  pause
  goto :restart
)

echo Using git: "%GIT%"
echo.
"%GIT%" rev-parse --is-inside-work-tree >nul 2>&1
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo This folder is not a Git clone, so it cannot update automatically.
  echo The app will still start on the current version.
  echo.
  pause
  goto :restart
)
echo Current branch:
"%GIT%" rev-parse --abbrev-ref HEAD
echo Pulling the latest version...
echo.
"%GIT%" pull --ff-only
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo ------------------------------------------------------------
  echo Update could not be applied automatically ^(exit code %RC%^).
  echo This usually means local edits, or the branch moved.
  echo Open GitHub Desktop and Pull manually, then run this again.
  echo The app will still start on the current version below.
  echo ------------------------------------------------------------
  echo.
  pause
) else (
  echo Update complete.
  echo.
)

:restart
echo Stopping any running CV Studio server...
if not exist "%~dp0FORCE_STOP.ps1" goto :stop_helper_missing
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0FORCE_STOP.ps1" -Root "%~dp0"
set "STOP_RC=%ERRORLEVEL%"
if not "%STOP_RC%"=="0" goto :stop_failed

echo Starting CV Studio...
if not exist "%~dp0CV Studio.bat" (
  echo ERROR: "CV Studio.bat" was not found in this folder.
  echo Make sure you are running UPDATE.bat from the CV Studio folder.
  echo.
  pause
  exit /b 1
)
call "%~dp0CV Studio.bat"
exit /b %ERRORLEVEL%

:stop_helper_missing
echo ERROR: FORCE_STOP.ps1 was not found in this folder.
echo CV Studio was not restarted because the old server could still be running.
echo.
pause
exit /b 2

:stop_failed
echo.
echo ERROR: CV Studio could not be stopped safely ^(exit code %STOP_RC%^).
echo The app was not restarted. Review the message above, then try again.
echo.
pause
exit /b %STOP_RC%
