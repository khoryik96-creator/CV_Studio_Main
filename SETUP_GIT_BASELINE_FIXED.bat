@echo off
setlocal
cd /d "%~dp0"
title CV Studio Codex Git Setup

echo.
echo ============================================================
echo CV Studio v24.6.238 - Codex Git Baseline Setup
echo ============================================================
echo.
echo Working folder:
echo %CD%
echo.

if not exist "app.py" (
  echo ERROR: app.py is not in this folder.
  echo.
  echo This setup file is currently located in:
  echo %CD%
  echo.
  echo Move this SETUP_GIT_BASELINE_FIXED.bat file into the exact
  echo folder that contains app.py and index.html, then double-click it.
  echo.
  pause
  exit /b 1
)

where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: Git is not installed or Windows cannot find it.
  echo.
  echo Install Git for Windows, restart ChatGPT Desktop, then run
  echo this file again.
  echo.
  pause
  exit /b 1
)

echo Git found:
git --version
echo.

if not exist ".git" (
  echo Creating a local Git repository...
  git init
  if errorlevel 1 goto :failed
) else (
  echo This folder is already a Git repository.
)

for /f "delims=" %%A in ('git config --local user.name 2^>nul') do set "GIT_NAME=%%A"
if not defined GIT_NAME git config --local user.name "CV Studio Owner"

for /f "delims=" %%A in ('git config --local user.email 2^>nul') do set "GIT_EMAIL=%%A"
if not defined GIT_EMAIL git config --local user.email "cv-studio-owner@local.invalid"

echo Adding the v24.6.238 baseline files...
git add -A
if errorlevel 1 goto :failed

git rev-parse --verify HEAD >nul 2>nul
if errorlevel 1 (
  echo Creating the first baseline commit...
  git commit -m "CV Studio v24.6.238 baseline"
  if errorlevel 1 goto :failed
) else (
  git diff --cached --quiet
  if errorlevel 1 (
    echo Committing the Codex setup files...
    git commit -m "Add CV Studio Codex project instructions"
    if errorlevel 1 goto :failed
  ) else (
    echo No new commit was needed.
  )
)

echo.
echo ============================================================
echo SUCCESS
echo ============================================================
echo.
echo Your cv_formatter folder is now a Git repository.
echo.
echo Next:
echo 1. Open ChatGPT Desktop.
echo 2. Open Codex.
echo 3. Open this exact folder:
echo    %CD%
echo 4. Start a new Worktree chat.
echo 5. Paste CODEX_FIRST_PROMPT.txt.
echo.
pause
exit /b 0

:failed
echo.
echo ERROR: Git setup did not complete.
echo Copy or screenshot everything shown in this window.
echo.
pause
exit /b 1
