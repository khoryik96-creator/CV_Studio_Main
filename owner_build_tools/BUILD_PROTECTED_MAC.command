#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "============================================"
echo "  CV Studio v24.6.240 Protected Mac Build"
echo "============================================"
echo ""
echo "Owner-only builder. Do not send this file or the private source to colleagues."
echo ""
command -v python3 >/dev/null 2>&1 || { echo "ERROR: Python 3.12+ is required."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js is required."; exit 1; }
python3 owner_build_tools/repo_consistency.py --root . --repair
python3 -m pip install --disable-pip-version-check --upgrade "nuitka==4.1.3" ordered-set zstandard
python3 -m pip install --disable-pip-version-check -r requirements.txt
npm install --ignore-scripts --no-audit --no-fund --package-lock=false
npm install --no-save --ignore-scripts --no-audit --no-fund --package-lock=false javascript-obfuscator@4.1.1
python3 owner_build_tools/repo_consistency.py --root .
ARCH="$(uname -m)"
case "$ARCH" in
  arm64|aarch64) TARGET="macos-arm64" ;;
  x86_64|amd64) TARGET="macos-intel" ;;
  *) echo "ERROR: Unsupported Mac architecture: $ARCH"; exit 1 ;;
esac
python3 owner_build_tools/build_protected.py --target "$TARGET" --source-root . --output-dir protected-output
echo ""
echo "Build complete: protected-output"
open protected-output 2>/dev/null || true
