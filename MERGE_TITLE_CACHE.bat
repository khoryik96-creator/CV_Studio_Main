@echo off
chcp 65001 >nul
echo The 郭 Lab CV Studio - Merge Title Angle Caches
echo.
echo Drop all colleagues' lead_title_cache.json files into this folder first
echo (rename each one so they don't overwrite each other, e.g.
echo  lead_title_cache_alice.json, lead_title_cache_bob.json, etc.)
echo.
set /p FILES="Enter the cache filenames to merge, space-separated: "
if "%FILES%"=="" (
    echo No files entered. Exiting.
    pause
    exit /b
)
if exist merge_title_cache.py (
  python merge_title_cache.py %FILES% -o lead_title_cache.json
) else if exist merge_title_cache.pyc (
  python merge_title_cache.pyc %FILES% -o lead_title_cache.json
) else (
  echo ERROR: merge_title_cache.py/.pyc not found.
  pause
  exit /b 1
)
echo.
echo Done. Copy the resulting lead_title_cache.json to each laptop's
echo cv_formatter folder to give everyone the combined cache.
echo.
pause
