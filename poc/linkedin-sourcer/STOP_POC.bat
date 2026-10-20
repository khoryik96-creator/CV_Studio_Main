@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Poc.ps1" -Stop
if errorlevel 1 pause
