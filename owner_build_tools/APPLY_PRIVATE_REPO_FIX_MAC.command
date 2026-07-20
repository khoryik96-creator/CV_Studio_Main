#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "============================================"
echo "  CV Studio private GitHub repo no-lock sync"
echo "============================================"
python3 owner_build_tools/repo_consistency.py --root . --repair --report repo_consistency_report.json
if [[ -d .git ]] && command -v git >/dev/null 2>&1; then
  git rm -f --ignore-unmatch package-lock.json npm-shrinkwrap.json >/dev/null 2>&1 || true
  git add package.json .gitignore .gitattributes "CV Studio.bat" INSTALL.bat INSTALL_CORE.bat MERGE_TITLE_CACHE.bat STOP.bat .github/workflows/build-protected.yml owner_build_tools/repo_consistency.py owner_build_tools/BUILD_PROTECTED_WINDOWS.bat owner_build_tools/APPLY_PRIVATE_REPO_FIX_WINDOWS.bat owner_build_tools/APPLY_PRIVATE_REPO_FIX_MAC.command owner_build_tools/BUILD_PROTECTED_MAC.command
  echo "Files staged. Review with: git status"
  git status --short
  echo "Then commit and push the staged changes to your PRIVATE repository."
else
  echo "This folder is not a Git clone (or Git is unavailable). Upload the repaired files to the private repository manually."
fi
