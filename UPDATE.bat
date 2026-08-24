@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title CV Studio - Update

set "UPDATE_APPLIED=0"
set "PREVIOUS_COMMIT="
set "CURRENT_COMMIT="
set "UPDATE_LOG="
set "UPDATE_STATE_DIR=%CVSTUDIO_UPDATE_STATE_DIR%"
if not defined UPDATE_STATE_DIR set "UPDATE_STATE_DIR=%LOCALAPPDATA%\TheGuoLab\CVStudio"
if not exist "%UPDATE_STATE_DIR%" mkdir "%UPDATE_STATE_DIR%" >nul 2>&1
if exist "%UPDATE_STATE_DIR%" set "UPDATE_LOG=%UPDATE_STATE_DIR%\source_update.log"
if defined UPDATE_LOG if exist "%UPDATE_LOG%" for %%L in ("%UPDATE_LOG%") do if %%~zL GEQ 1048576 move /y "%UPDATE_LOG%" "%UPDATE_LOG%.1" >nul 2>&1
call :log update_started

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
  call :log git_unavailable
  echo Could not find git automatically.
  echo Open GitHub Desktop, click Fetch origin then Pull, then run this file again.
  echo The app will still start on the current version.
  echo.
  pause
  goto :preflight
)

echo Using git: "%GIT%"
echo.
"%GIT%" rev-parse --is-inside-work-tree >nul 2>&1
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  call :log not_a_git_clone
  echo This folder is not a Git clone, so it cannot update automatically.
  echo The app will still start on the current version.
  echo.
  pause
  goto :preflight
)
for /f "usebackq delims=" %%C in (`"%GIT%" rev-parse HEAD`) do set "PREVIOUS_COMMIT=%%C"
set "CURRENT_COMMIT=%PREVIOUS_COMMIT%"
call :log previous_commit=%PREVIOUS_COMMIT%
echo Current branch:
"%GIT%" rev-parse --abbrev-ref HEAD
echo Pulling the latest version...
echo.
"%GIT%" pull --ff-only
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  call :log git_pull_failed_%RC%
  echo ------------------------------------------------------------
  echo Update could not be applied automatically ^(exit code %RC%^).
  echo This usually means local edits, or the branch moved.
  echo Open GitHub Desktop and Pull manually, then run this again.
  echo The app will still start on the current version below.
  echo ------------------------------------------------------------
  echo.
  pause
) else (
  set "UPDATE_APPLIED=1"
  echo Files updated successfully.
  echo.
)
if "%UPDATE_APPLIED%"=="1" for /f "usebackq delims=" %%C in (`"%GIT%" rev-parse HEAD`) do set "CURRENT_COMMIT=%%C"
if "%UPDATE_APPLIED%"=="1" call :log current_commit=%CURRENT_COMMIT%

:preflight
echo Checking the updated CV Studio before stopping the current server...
if not exist "%~dp0UPDATE_PREFLIGHT.ps1" goto :preflight_helper_missing
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0UPDATE_PREFLIGHT.ps1" -Root "%~dp0"
set "PREFLIGHT_RC=%ERRORLEVEL%"
if not "%PREFLIGHT_RC%"=="0" goto :preflight_failed
call :log preflight_passed

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
call "%~dp0CV Studio.bat" --wait
set "START_RC=%ERRORLEVEL%"
if not "%START_RC%"=="0" goto :start_failed
call :log restart_succeeded
if "%UPDATE_APPLIED%"=="1" echo CV Studio was updated and restarted successfully.
if not "%UPDATE_APPLIED%"=="1" echo CV Studio restarted on the current version.
if defined UPDATE_LOG echo Update log: "%UPDATE_LOG%"
exit /b 0

:preflight_helper_missing
call :log preflight_helper_missing
echo ERROR: UPDATE_PREFLIGHT.ps1 was not found in this folder.
echo The current CV Studio server was left untouched.
echo.
pause
exit /b 9

:preflight_failed
call :log preflight_failed_%PREFLIGHT_RC%
echo.
echo ERROR: The updated files are not ready to launch ^(exit code %PREFLIGHT_RC%^).
echo The current CV Studio server was left untouched.
echo Run INSTALL.bat if the message above reports a missing dependency.
if defined UPDATE_LOG echo Update log: "%UPDATE_LOG%"
echo.
pause
exit /b %PREFLIGHT_RC%

:stop_helper_missing
call :log stop_helper_missing
echo ERROR: FORCE_STOP.ps1 was not found in this folder.
echo CV Studio was not restarted because the old server could still be running.
echo.
pause
exit /b 2

:stop_failed
call :log stop_failed_%STOP_RC%
echo.
echo ERROR: CV Studio could not be stopped safely ^(exit code %STOP_RC%^).
echo The app was not restarted. Review the message above, then try again.
echo.
pause
exit /b %STOP_RC%

:start_failed
call :log restart_failed_%START_RC%
echo.
echo ERROR: The updated CV Studio did not start correctly ^(exit code %START_RC%^).
echo Previous source commit: %PREVIOUS_COMMIT%
echo Current source commit:  %CURRENT_COMMIT%
echo Use GitHub Desktop History if you need to return to the previous commit.
echo Local edits were not reset or overwritten by this recovery guidance.
if defined UPDATE_LOG echo Update log: "%UPDATE_LOG%"
echo.
pause
exit /b %START_RC%

:log
if defined UPDATE_LOG >>"%UPDATE_LOG%" echo %DATE% %TIME% ^| %*
exit /b 0
