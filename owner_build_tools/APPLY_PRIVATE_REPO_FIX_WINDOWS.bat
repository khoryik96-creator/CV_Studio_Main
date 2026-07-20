@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."
echo ============================================
echo   CV Studio private GitHub repo no-lock sync
echo ============================================
echo.
python owner_build_tools\repo_consistency.py --root . --repair --report repo_consistency_report.json
if errorlevel 1 goto :fail
if exist .git (
  where git >nul 2>&1
  if not errorlevel 1 (
    git rm -f --ignore-unmatch package-lock.json npm-shrinkwrap.json >nul 2>&1
    git add package.json .gitignore .gitattributes "CV Studio.bat" INSTALL.bat INSTALL_CORE.bat MERGE_TITLE_CACHE.bat STOP.bat .github\workflows\build-protected.yml owner_build_tools\repo_consistency.py owner_build_tools\BUILD_PROTECTED_WINDOWS.bat owner_build_tools\APPLY_PRIVATE_REPO_FIX_WINDOWS.bat owner_build_tools\APPLY_PRIVATE_REPO_FIX_MAC.command owner_build_tools\BUILD_PROTECTED_MAC.command
    echo.
    echo Files staged. Review with: git status
    git status --short
    echo.
    echo Then commit and push the staged changes to your PRIVATE repository.
  ) else (
    echo Git is not installed. The files are repaired locally; upload the current files to the private repository manually.
  )
) else (
  echo This folder is not a Git clone. The files are repaired locally; upload the current package.json, .gitignore, workflow and repo_consistency.py to the private repository.
)
pause
exit /b 0
:fail
echo.
echo REPOSITORY REPAIR FAILED. Review the error above.
pause
exit /b 1
