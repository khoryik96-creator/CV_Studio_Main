@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."
echo ============================================
echo   CV Studio v24.6.326 Protected Windows Build
echo ============================================
echo.
echo Owner-only builder. Do not send this file or the private source to colleagues.
echo.
where python >nul 2>&1 || (echo ERROR: Python 3.12+ is required.& pause & exit /b 1)
where node >nul 2>&1 || (echo ERROR: Node.js is required.& pause & exit /b 1)
python owner_build_tools\repo_consistency.py --root . --repair
if errorlevel 1 goto :fail
python -m pip install --disable-pip-version-check --upgrade "nuitka==4.1.3" ordered-set zstandard pywin32
if errorlevel 1 goto :fail
python -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :fail
call npm install --ignore-scripts --no-audit --no-fund --package-lock=false
if errorlevel 1 goto :fail
call npm install --no-save --ignore-scripts --no-audit --no-fund --package-lock=false javascript-obfuscator@4.1.1
if errorlevel 1 goto :fail
python owner_build_tools\repo_consistency.py --root .
if errorlevel 1 goto :fail
python owner_build_tools\build_protected.py --target windows-x64 --source-root . --output-dir protected-output
if errorlevel 1 goto :fail
echo.
echo Build complete. Open the protected-output folder.
explorer protected-output
pause
exit /b 0
:fail
echo.
echo BUILD FAILED. No colleague package should be distributed.
echo Review the messages above, fix the issue, and run this builder again.
pause
exit /b 1
