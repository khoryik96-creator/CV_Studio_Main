#!/bin/bash
# The 郭 Lab CV Studio — macOS launcher v24.6.359
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
STATE_DIR="$HOME/.guo_lab_cv_studio"
URL="http://localhost:5000"
VERSION="v24.6.359"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
mkdir -p "$STATE_DIR"

curl_get(){ curl -fsS --connect-timeout 2 --max-time 4 -H 'Cache-Control: no-cache' "$1" 2>/dev/null || true; }
identity_matches(){
  local body="$1" v iid r
  IFS='|' read -r v iid r <<EOF
$body
EOF
  [ "$v" = "$VERSION" ] && [ "$(cd "$r" 2>/dev/null && pwd -P)" = "$SCRIPT_DIR" ]
}

NATIVE_EXE=''
if [ -d "$SCRIPT_DIR/runtime/native" ]; then NATIVE_EXE="$(find "$SCRIPT_DIR/runtime/native" -maxdepth 1 -type f -name 'CVStudio*' 2>/dev/null | head -1)"; fi
find_python(){ for p in "$STATE_DIR/venv/bin/python3" "$STATE_DIR/venv/bin/python" python3 /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do command -v "$p" >/dev/null 2>&1 && { printf '%s\n' "$p"; return 0; }; done; return 1; }

# Verify the exact version/folder receipt without requiring Python in native mode.
if [ -n "$NATIVE_EXE" ]; then
  chmod +x "$NATIVE_EXE" 2>/dev/null || true
  "$NATIVE_EXE" --check-install-receipt >/dev/null 2>&1 || { osascript -e 'display alert "CV Studio authorization required" message "Run install.sh and complete setup for this exact folder first."' 2>/dev/null || true; exit 13; }
else
  PY="$(find_python 2>/dev/null || true)"
  [ -n "$PY" ] && "$PY" "$SCRIPT_DIR/app.py" --check-install-receipt >/dev/null 2>&1 || { echo 'Run install.sh first.'; exit 13; }
fi

IDENTITY="$(curl_get "$URL/instance-id")"
if identity_matches "$IDENTITY"; then open "$URL"; exit 0; fi

PORT_PID="$(lsof -nP -tiTCP:5000 -sTCP:LISTEN 2>/dev/null | head -1)"
if [ -n "$PORT_PID" ]; then
  CMD="$(ps -p "$PORT_PID" -o command= 2>/dev/null || true)"
  IS_CV=0
  case "$CMD" in */runtime/native/CVStudio*|*/app.py|*/app.py\ *|*/app.pyc|*/app.pyc\ *) IS_CV=1;; esac
  if [ "$IS_CV" -eq 1 ]; then
    if osascript -e 'display dialog "Another CV Studio version is using port 5000. Stop it and launch this version?" buttons {"Cancel","Stop and Launch"} default button "Stop and Launch"' 2>/dev/null | grep -q 'Stop and Launch'; then
      # Recheck PID/command immediately before stopping to avoid a PID-reuse race.
      NOW_CMD="$(ps -p "$PORT_PID" -o command= 2>/dev/null || true)"
      [ "$NOW_CMD" = "$CMD" ] && kill "$PORT_PID" 2>/dev/null || true
      sleep 1
    else exit 3; fi
  else
    osascript -e 'display alert "CV Studio cannot use port 5000" message "Another application is using localhost port 5000. CV Studio did not stop it."' 2>/dev/null || true
    exit 4
  fi
fi

if ! (cd "$SCRIPT_DIR" && command -v node >/dev/null 2>&1 && node -e "require('adm-zip')" >/dev/null 2>&1); then
  osascript -e 'display alert "CV Studio installation incomplete" message "The required Node package adm-zip is missing or damaged. Run install.sh again."' 2>/dev/null || true
  exit 5
fi

LOG="$STATE_DIR/runtime-launch.log"
[ -f "$LOG" ] && [ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 1048576 ] && { rm -f "$LOG.1"; mv "$LOG" "$LOG.1"; }
cd "$SCRIPT_DIR" || exit 1
if [ -n "$NATIVE_EXE" ]; then
  CVSTUDIO_RUNTIME_LOG_PATH="$STATE_DIR/runtime.log" nohup "$NATIVE_EXE" >>"$LOG" 2>&1 &
else
  PY="$(find_python 2>/dev/null || true)"; [ -n "$PY" ] || { echo 'Python environment missing. Run install.sh.'; exit 1; }
  CVSTUDIO_RUNTIME_LOG_PATH="$STATE_DIR/runtime.log" nohup "$PY" "$SCRIPT_DIR/app.py" >>"$LOG" 2>&1 &
fi

for i in $(seq 1 240); do
  IDENTITY="$(curl_get "$URL/instance-id")"
  if identity_matches "$IDENTITY"; then open "$URL"; exit 0; fi
  [ -n "$IDENTITY" ] && break
  sleep 0.25
done
osascript -e 'display alert "CV Studio failed to start" message "The expected version/folder did not answer. Check ~/.guo_lab_cv_studio/runtime-launch.log."' 2>/dev/null || true
exit 6
