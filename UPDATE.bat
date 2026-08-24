@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title CV Studio - Update
if not exist "%~dp0UPDATE_CORE.ps1" (
  echo ERROR: UPDATE_CORE.ps1 was not found in this folder.
  echo No files were changed and the current server was left untouched.
  pause
  exit /b 9
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0UPDATE_CORE.ps1" & exit /b !ERRORLEVEL!
