#!/bin/bash
# The 郭 Lab CV Studio — macOS installer v24.6.255
set -u
printf '%s\n' '============================================' '  The 郭 Lab CV Studio — Mac Setup' '============================================' ''
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
STATE_DIR="$HOME/.guo_lab_cv_studio"
VENV_DIR="$STATE_DIR/venv"
RECEIPT_PATH="$STATE_DIR/install_receipt.json"
VERSION="v24.6.255"
TOTP_MASK_HEX="9339245374f57a39a5a2b0a8f932cc802daee838"
TOTP_MASKED_HEX="3110f491137b761b47abb4b1787aff446496760a"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [ -f "$SCRIPT_DIR/PROTECTED_PLATFORM_TARGET.txt" ]; then
  TARGET="$(tr -d '\r\n' < "$SCRIPT_DIR/PROTECTED_PLATFORM_TARGET.txt")"
  ARCH="$(uname -m 2>/dev/null || echo unknown)"
  case "$TARGET" in
    macos-arm64)
      case "$ARCH" in arm64|aarch64) ;; *) echo "This package is for Apple Silicon Macs, but this Mac reports $ARCH. Use the macos-intel package only on an Intel Mac."; exit 2;; esac ;;
    macos-intel)
      case "$ARCH" in x86_64|amd64) ;; *) echo "This package is for Intel Macs, but this Mac reports $ARCH. Use the macos-arm64 package on Apple Silicon."; exit 2;; esac ;;
    *) echo "This protected package targets $TARGET and cannot be installed on macOS."; exit 2;;
  esac
fi

find_base_python(){
  for py in python3 /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if command -v "$py" >/dev/null 2>&1; then printf '%s\n' "$py"; return 0; fi
  done
  return 1
}

validate_totp(){
  local candidate="$1"
  case "$candidate" in ''|*[!0-9]*) return 1;; esac
  [ "${#candidate}" -eq 6 ] || return 1
  local py="$(find_base_python 2>/dev/null || true)"
  if [ -n "$py" ]; then
    TOTP_CODE="$candidate" TOTP_MASK_HEX="$TOTP_MASK_HEX" TOTP_MASKED_HEX="$TOTP_MASKED_HEX" "$py" - <<'PYTOTP'
import os,time,hmac,hashlib,struct
code=os.environ.get('TOTP_CODE',''); mask=bytes.fromhex(os.environ['TOTP_MASK_HEX']); masked=bytes.fromhex(os.environ['TOTP_MASKED_HEX'])
if len(mask)!=len(masked): raise SystemExit(2)
secret=bytes(a^b for a,b in zip(mask,masked)); base=int(time.time())//30
for d in (-1,0,1):
 digest=hmac.new(secret,struct.pack('>Q',base+d),hashlib.sha1).digest(); o=digest[-1]&15
 value=((digest[o]&127)<<24)|(digest[o+1]<<16)|(digest[o+2]<<8)|digest[o+3]
 if f'{value%1000000:06d}'==code: raise SystemExit(0)
raise SystemExit(1)
PYTOTP
    return $?
  fi
  if command -v perl >/dev/null 2>&1 && perl -MDigest::SHA -e 1 >/dev/null 2>&1; then
    TOTP_CODE="$candidate" TOTP_MASK_HEX="$TOTP_MASK_HEX" TOTP_MASKED_HEX="$TOTP_MASKED_HEX" perl -MDigest::SHA=hmac_sha1 -e '
      my $c=$ENV{TOTP_CODE}//""; my $m=pack("H*",$ENV{TOTP_MASK_HEX}//""); my $x=pack("H*",$ENV{TOTP_MASKED_HEX}//""); exit 2 unless length($m)==length($x); my $s=$m^$x; my $b=int(time()/30);
      for my $d(-1,0,1){my $n=$b+$d;my $q=pack("NN",int($n/4294967296),$n%4294967296);my @z=unpack("C*",hmac_sha1($q,$s));my $o=$z[-1]&15;my $v=(($z[$o]&127)<<24)|($z[$o+1]<<16)|($z[$o+2]<<8)|$z[$o+3];exit 0 if sprintf("%06d",$v%1000000) eq $c} exit 1;'
    return $?
  fi
  echo 'Neither Python 3 nor Perl Digest::SHA is available for Authy verification.' >&2
  return 2
}

INSTALL_CODE=''
for attempt in 1 2 3; do
  printf 'Enter the current 6-digit Authy installer code: '
  IFS= read -r -s INSTALL_CODE; printf '\n'
  if validate_totp "$INSTALL_CODE"; then echo 'Installer access granted.'; break; fi
  INSTALL_CODE=''; remaining=$((3-attempt)); [ "$remaining" -gt 0 ] && echo "Incorrect or expired code. $remaining attempt(s) remaining."
done
if [ -z "$INSTALL_CODE" ]; then echo 'Access denied. Installation was not started.'; exit 13; fi

NATIVE_EXE=''
if [ -d "$SCRIPT_DIR/runtime/native" ]; then
  NATIVE_EXE="$(find "$SCRIPT_DIR/runtime/native" -maxdepth 1 -type f -name 'CVStudio*' -perm -111 2>/dev/null | head -1)"
fi
NATIVE_MODE=0; [ -n "$NATIVE_EXE" ] && NATIVE_MODE=1
mkdir -p "$STATE_DIR"

# Mandatory Node runtime and DOCX package.
echo '[1/5] Checking Node.js...'
if ! command -v node >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo '    Installing Node.js through Homebrew...'
    brew install node || { echo '    ERROR: Node.js installation failed.'; exit 1; }
  else
    echo '    ERROR: Node.js is required. Install it from nodejs.org or install Homebrew and run: brew install node'
    exit 1
  fi
fi
node --version || exit 1

echo '[2/5] Preparing backend runtime...'
if [ "$NATIVE_MODE" -eq 1 ]; then
  echo '    Protected native backend detected; skipping full Python virtual environment and pip packages.'
  chmod +x "$NATIVE_EXE" 2>/dev/null || true
  xattr -dr com.apple.quarantine "$SCRIPT_DIR/runtime/native" 2>/dev/null || true
else
  BASE_PYTHON="$(find_base_python 2>/dev/null || true)"
  if [ -z "$BASE_PYTHON" ]; then echo '    ERROR: Python 3 is required for this owner/source build.'; exit 1; fi
  if [ ! -x "$VENV_DIR/bin/python3" ] && [ ! -x "$VENV_DIR/bin/python" ]; then "$BASE_PYTHON" -m venv "$VENV_DIR" || exit 1; fi
  VENV_PYTHON="$VENV_DIR/bin/python3"; [ -x "$VENV_PYTHON" ] || VENV_PYTHON="$VENV_DIR/bin/python"
  "$VENV_PYTHON" -m ensurepip --upgrade >/dev/null 2>&1 || true
  "$VENV_PYTHON" -m pip install --disable-pip-version-check -r "$SCRIPT_DIR/requirements.txt" || exit 1
fi

echo '[3/5] Verifying mandatory Antiword...'
ARCH="$(uname -m 2>/dev/null || echo unknown)"
case "$ARCH" in
  arm64|aarch64) ANTIWORD_TAG='macos-arm64'; ANTIWORD_MANIFEST='6c59492af62df5d342c16b3126e588a4bbe855f3ba37f1f9120dc3e5352f6ce3' ;;
  x86_64|amd64) ANTIWORD_TAG='macos-intel'; ANTIWORD_MANIFEST='7e403a00b2acd1186c714bc55fe382f2b8a03fb5c430edd16e4d447e3f9f4ee8' ;;
  *) echo "    ERROR: Unsupported Mac architecture for Antiword: $ARCH"; exit 1 ;;
esac
ANTIWORD_ROOT="$SCRIPT_DIR/vendor/antiword/$ANTIWORD_TAG"
ANTIWORD_FIXTURE="$SCRIPT_DIR/vendor/antiword/fixtures/UDHR-english.doc"
ANTIWORD_STAGE_BASE="$(mktemp -d "${TMPDIR:-/tmp}/cvstudio-antiword-install.XXXXXX")" || { echo '    ERROR: Could not create the private Antiword verification directory.'; exit 1; }
cleanup_antiword_stage(){
  chflags -R nouchg "$ANTIWORD_STAGE_BASE" 2>/dev/null || true
  chmod -R u+rwX "$ANTIWORD_STAGE_BASE" 2>/dev/null || true
  rm -rf "$ANTIWORD_STAGE_BASE" 2>/dev/null || true
}
ANTIWORD_STAGE="$ANTIWORD_STAGE_BASE/$ANTIWORD_TAG"
ANTIWORD_STAGE_FIXTURE="$ANTIWORD_STAGE_BASE/UDHR-english.doc"
cp -R "$ANTIWORD_ROOT" "$ANTIWORD_STAGE" && cp "$ANTIWORD_FIXTURE" "$ANTIWORD_STAGE_FIXTURE" || { cleanup_antiword_stage; echo '    ERROR: Could not stage bundled Antiword for protected verification.'; exit 1; }
ANTIWORD_BIN="$ANTIWORD_STAGE/bin/antiword"
[ -f "$ANTIWORD_STAGE/SHA256SUMS" ] && [ "$(shasum -a 256 "$ANTIWORD_STAGE/SHA256SUMS" | awk '{print $1}')" = "$ANTIWORD_MANIFEST" ] || { cleanup_antiword_stage; echo '    ERROR: Bundled Antiword manifest is missing or damaged.'; exit 1; }
(cd "$ANTIWORD_STAGE" && shasum -a 256 -c SHA256SUMS >/dev/null) || { cleanup_antiword_stage; echo '    ERROR: Bundled Antiword runtime failed integrity verification.'; exit 1; }
[ "$(shasum -a 256 "$ANTIWORD_STAGE_FIXTURE" | awk '{print $1}')" = 'f430cdfe9446c4b943074d4bf804232761c284f2caa3d4125006b158d8b14af8' ] || { cleanup_antiword_stage; echo '    ERROR: Antiword functional fixture failed integrity verification.'; exit 1; }
chmod 500 "$ANTIWORD_BIN" || { cleanup_antiword_stage; echo '    ERROR: Antiword executable permission could not be applied.'; exit 1; }
xattr -d com.apple.quarantine "$ANTIWORD_BIN" 2>/dev/null || true
chflags -R uchg "$ANTIWORD_STAGE" "$ANTIWORD_STAGE_FIXTURE" || { cleanup_antiword_stage; echo '    ERROR: Antiword verification snapshot could not be made immutable.'; exit 1; }
ANTIWORD_OUTPUT="$(ANTIWORDHOME="$ANTIWORD_STAGE/share/antiword" HOME="$ANTIWORD_BIN" "$ANTIWORD_BIN" -t "$ANTIWORD_STAGE_FIXTURE" 2>/dev/null || true)"
printf '%s' "$ANTIWORD_OUTPUT" | grep -F 'Universal Declaration of Human Rights' >/dev/null && printf '%s' "$ANTIWORD_OUTPUT" | grep -F 'All people everywhere have the same human rights' >/dev/null || { cleanup_antiword_stage; echo '    ERROR: Bundled Antiword failed its genuine .doc functional check.'; exit 1; }
cleanup_antiword_stage
echo "    Antiword ready: $ANTIWORD_TAG"

echo '[4/5] Installing Node packages...'
cd "$SCRIPT_DIR" || exit 1
npm install --ignore-scripts --no-audit --no-fund || { echo '    ERROR: npm install failed.'; exit 1; }
node -e "require('adm-zip')" || { echo '    ERROR: adm-zip could not be loaded after npm install.'; exit 1; }

# Tesseract is the mandatory OCR engine. PDFium is bundled in protected mode and
# installed from requirements.txt in source mode, so Poppler is only fallback.
echo '[5/5] Checking mandatory OCR tools...'
if ! command -v tesseract >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo '    Installing mandatory Tesseract through Homebrew...'
    brew install tesseract || { echo '    ERROR: Tesseract installation failed.'; exit 1; }
    export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
  else
    echo '    ERROR: Tesseract is mandatory. Install Homebrew and run: brew install tesseract'
    exit 1
  fi
fi
tesseract --version >/dev/null 2>&1 || { echo '    ERROR: Tesseract cannot execute.'; exit 1; }
tesseract --list-langs 2>/dev/null | grep -Fx 'eng' >/dev/null || { echo '    ERROR: Tesseract English language data is missing.'; exit 1; }
echo '    Tesseract ready with English language data.'
if [ "$NATIVE_MODE" -eq 1 ]; then
  echo '    Built-in PDFium renderer is bundled; external Poppler is not required.'
elif "$VENV_PYTHON" -c 'import pypdfium2' >/dev/null 2>&1; then
  echo '    Built-in PDFium renderer is ready; external Poppler is not required.'
elif command -v pdftoppm >/dev/null 2>&1; then
  echo '    Poppler fallback ready.'
else
  echo '    WARNING: PDF renderer unavailable. Re-run install.sh before scanned-PDF OCR.'
fi

# Preserve the currently active package and its root-bound signed receipt before
# this release writes a new one. Each release remains in its own extracted folder.
UPDATE_STATE_PATH="$STATE_DIR/update_state.json"
ROLLBACK_DIR="$STATE_DIR/rollback_receipts"
mkdir -p "$ROLLBACK_DIR"
PREVIOUS_ROOT=''; PREVIOUS_VERSION=''; PREVIOUS_RECEIPT=''
EXISTING_LAUNCHER="$HOME/Desktop/CV Studio.command"
if [ -f "$EXISTING_LAUNCHER" ]; then
  LAUNCH_LINE="$(grep -E '^bash ' "$EXISTING_LAUNCHER" 2>/dev/null | head -1 | sed 's/^bash //')"
  if [ -n "$LAUNCH_LINE" ]; then
    eval "set -- $LAUNCH_LINE" 2>/dev/null || true
    [ "$#" -ge 1 ] && PREVIOUS_ROOT="$(cd "$(dirname "$1")" 2>/dev/null && pwd -P || true)"
  fi
fi
if [ -z "$PREVIOUS_ROOT" ] && [ -f "$UPDATE_STATE_PATH" ]; then
  BASE_PYTHON_PRE="$(find_base_python 2>/dev/null || true)"
  if [ -n "$BASE_PYTHON_PRE" ]; then
    PREVIOUS_ROOT="$(STATE="$UPDATE_STATE_PATH" "$BASE_PYTHON_PRE" - <<'PYSTATE' 2>/dev/null || true
import json,os
try: print(json.load(open(os.environ['STATE'],encoding='utf-8')).get('current_root',''))
except Exception: pass
PYSTATE
)"
  fi
fi
[ "$(cd "$PREVIOUS_ROOT" 2>/dev/null && pwd -P || true)" = "$SCRIPT_DIR" ] && PREVIOUS_ROOT=''
if [ -n "$PREVIOUS_ROOT" ] && [ -f "$RECEIPT_PATH" ]; then
  ROOT_HASH="$(printf '%s' "$PREVIOUS_ROOT" | shasum -a 256 | awk '{print $1}' | cut -c1-24)"
  PREVIOUS_RECEIPT="$ROLLBACK_DIR/receipt_${ROOT_HASH}.json"
  cp -f "$RECEIPT_PATH" "$PREVIOUS_RECEIPT" || PREVIOUS_RECEIPT=''
  PREVIOUS_VERSION="$(sed -nE 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' "$PREVIOUS_RECEIPT" 2>/dev/null | head -1)"
fi

# Finalize a version/folder-bound receipt only now, after mandatory setup passed.
BASE_PYTHON="$(find_base_python 2>/dev/null || true)"
if [ -n "$BASE_PYTHON" ]; then
  VERSION="$VERSION" PACKAGE_ROOT="$SCRIPT_DIR" RECEIPT_PATH="$RECEIPT_PATH" TOTP_MASK_HEX="$TOTP_MASK_HEX" TOTP_MASKED_HEX="$TOTP_MASKED_HEX" "$BASE_PYTHON" - <<'PYRECEIPT'
import os,sys,time,hmac,hashlib,json,platform,subprocess,re
mask=bytes.fromhex(os.environ['TOTP_MASK_HEX']); masked=bytes.fromhex(os.environ['TOTP_MASKED_HEX']); secret=bytes(a^b for a,b in zip(mask,masked))
def machine_source():
 v=''
 try:
  p=subprocess.run(['ioreg','-rd1','-c','IOPlatformExpertDevice'],capture_output=True,text=True,timeout=4)
  m=re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"',p.stdout or '',re.I); v=m.group(1).strip() if m else ''
 except Exception: pass
 return 'macos|'+(v or platform.node() or 'unknown').lower()
root=os.path.normcase(os.path.realpath(os.environ['PACKAGE_ROOT'])); machine=hashlib.sha256(machine_source().encode()).hexdigest(); root_hash=hashlib.sha256(root.encode('utf-8',errors='surrogatepass')).hexdigest(); issued=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); version=os.environ['VERSION']
key=hashlib.sha256(secret+b'|CVStudio|install-receipt-v1').digest(); msg=f'2|TheGuoLab-CVStudio|{machine}|{version}|{root_hash}|{issued}'; sig=hmac.new(key,msg.encode(),hashlib.sha256).hexdigest(); data={'schema':2,'product':'TheGuoLab-CVStudio','machine':machine,'version':version,'rootHash':root_hash,'issuedAt':issued,'signature':sig}
path=os.environ['RECEIPT_PATH']; os.makedirs(os.path.dirname(path),exist_ok=True); tmp=path+'.tmp'; open(tmp,'w',encoding='utf-8').write(json.dumps(data,separators=(',',':'))); os.replace(tmp,path)
PYRECEIPT
  RECEIPT_RC=$?
else
  # Perl fallback for protected Macs without Python.
  VERSION="$VERSION" PACKAGE_ROOT="$SCRIPT_DIR" RECEIPT_PATH="$RECEIPT_PATH" TOTP_MASK_HEX="$TOTP_MASK_HEX" TOTP_MASKED_HEX="$TOTP_MASKED_HEX" perl -MCwd=realpath -MDigest::SHA=sha256,sha256_hex,hmac_sha256_hex -MJSON::PP -e '
    my $mask=pack("H*",$ENV{TOTP_MASK_HEX});my $masked=pack("H*",$ENV{TOTP_MASKED_HEX});my $secret=$mask^$masked;
    my $uuid=`ioreg -rd1 -c IOPlatformExpertDevice 2>/dev/null`; $uuid=~/"IOPlatformUUID"\s*=\s*"([^"]+)"/;my $v=lc($1||`hostname`||"unknown");$v=~s/\s+$//;
    my $machine=sha256_hex("macos|$v");my $root=realpath($ENV{PACKAGE_ROOT})||$ENV{PACKAGE_ROOT};my $rh=sha256_hex($root);my @g=gmtime();my $issued=sprintf("%04d-%02d-%02dT%02d:%02d:%02dZ",$g[5]+1900,$g[4]+1,$g[3],$g[2],$g[1],$g[0]);my $key=sha256($secret."|CVStudio|install-receipt-v1");my $msg="2|TheGuoLab-CVStudio|$machine|$ENV{VERSION}|$rh|$issued";my $sig=hmac_sha256_hex($msg,$key);my $data={schema=>2,product=>"TheGuoLab-CVStudio",machine=>$machine,version=>$ENV{VERSION},rootHash=>$rh,issuedAt=>$issued,signature=>$sig};mkdir "$ENV{HOME}/.guo_lab_cv_studio";open my $fh,">",$ENV{RECEIPT_PATH}.".tmp" or exit 2;print $fh encode_json($data);close $fh;rename $ENV{RECEIPT_PATH}.".tmp",$ENV{RECEIPT_PATH} or exit 3;'
  RECEIPT_RC=$?
fi
INSTALL_CODE=''
if [ "$RECEIPT_RC" -ne 0 ]; then echo 'Could not create the final machine/package receipt. Installation is not authorized.'; exit 13; fi

# Health-test the exact new folder on a temporary loopback port before replacing
# the stable Desktop launcher. A failed release restores the previous receipt.
SMOKE_PORT=$((50000 + ($$ % 10000)))
while lsof -nP -iTCP:"$SMOKE_PORT" -sTCP:LISTEN >/dev/null 2>&1; do SMOKE_PORT=$((SMOKE_PORT+1)); [ "$SMOKE_PORT" -gt 62000 ] && SMOKE_PORT=50000; done
HEALTH_LOG="$STATE_DIR/install-health.log"
: > "$HEALTH_LOG"
if [ "$NATIVE_MODE" -eq 1 ]; then
  CVSTUDIO_OWNER_BUILD_SMOKE=1 CVSTUDIO_OWNER_BUILD_SMOKE_PORT="$SMOKE_PORT" CVSTUDIO_RUNTIME_LOG_PATH="$STATE_DIR/runtime.log" "$NATIVE_EXE" >>"$HEALTH_LOG" 2>&1 &
else
  CVSTUDIO_OWNER_BUILD_SMOKE=1 CVSTUDIO_OWNER_BUILD_SMOKE_PORT="$SMOKE_PORT" CVSTUDIO_RUNTIME_LOG_PATH="$STATE_DIR/runtime.log" "$VENV_PYTHON" "$SCRIPT_DIR/app.py" >>"$HEALTH_LOG" 2>&1 &
fi
HEALTH_PID=$!
HEALTH_OK=0; HEALTH_ERROR='startup timeout'
for _i in $(seq 1 180); do
  STATUS_JSON="$(curl -fsS --connect-timeout 1 --max-time 3 -H 'Cache-Control: no-cache' -H "X-CV-Studio-Request-ID: installer-$$-$_i" "http://localhost:$SMOKE_PORT/status" 2>/dev/null || true)"
  IDENTITY="$(curl -fsS --connect-timeout 1 --max-time 3 "http://localhost:$SMOKE_PORT/instance-id" 2>/dev/null || true)"
  DIAG_JSON="$(curl -fsS --connect-timeout 1 --max-time 5 "http://localhost:$SMOKE_PORT/diagnostics/runtime" 2>/dev/null || true)"
  case "$IDENTITY" in "$VERSION|"*"|$SCRIPT_DIR") ID_OK=1;; *) ID_OK=0;; esac
  printf '%s' "$STATUS_JSON" | grep -q '"healthy"[[:space:]]*:[[:space:]]*true' && STATUS_OK=1 || STATUS_OK=0
  printf '%s' "$STATUS_JSON" | grep -q "\"version\"[[:space:]]*:[[:space:]]*\"$VERSION\"" || STATUS_OK=0
  printf '%s' "$DIAG_JSON" | grep -q '"valid"[[:space:]]*:[[:space:]]*true' && DIAG_OK=1 || DIAG_OK=0
  printf '%s' "$DIAG_JSON" | grep -q '"request_id"[[:space:]]*:[[:space:]]*"[^"]\+"' || DIAG_OK=0
  printf '%s' "$DIAG_JSON" | grep -q '"antiword"[[:space:]]*:[[:space:]]*true' || DIAG_OK=0
  printf '%s' "$DIAG_JSON" | grep -q '"tesseract"[[:space:]]*:[[:space:]]*true' || DIAG_OK=0
  if [ "$ID_OK" -eq 1 ] && [ "$STATUS_OK" -eq 1 ] && [ "$DIAG_OK" -eq 1 ]; then HEALTH_OK=1; HEALTH_ERROR=''; break; fi
  kill -0 "$HEALTH_PID" 2>/dev/null || { HEALTH_ERROR='health runtime exited early'; break; }
  sleep 0.4
done
kill "$HEALTH_PID" 2>/dev/null || true
wait "$HEALTH_PID" 2>/dev/null || true

HEALTH_REPORT="$SCRIPT_DIR/install_health_report.json"
BASE_PYTHON_REPORT="$(find_base_python 2>/dev/null || true)"
if [ -n "$BASE_PYTHON_REPORT" ]; then
  HEALTH_OK="$HEALTH_OK" HEALTH_ERROR="$HEALTH_ERROR" HEALTH_REPORT="$HEALTH_REPORT" VERSION="$VERSION" ROOT="$SCRIPT_DIR" PORT="$SMOKE_PORT" "$BASE_PYTHON_REPORT" - <<'PYHEALTH'
import json,os,time
ok=os.environ['HEALTH_OK']=='1'
r={'ok':ok,'version':os.environ['VERSION'],'root':os.environ['ROOT'],'port':int(os.environ['PORT']),'completed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'checks':{'status':ok,'instance':ok,'diagnostics':ok,'request_id':ok},'error':os.environ.get('HEALTH_ERROR','')}
open(os.environ['HEALTH_REPORT'],'w',encoding='utf-8').write(json.dumps(r,indent=2))
PYHEALTH
else
  printf '{"ok":%s,"version":"%s","root":"%s","port":%s,"error":"%s"}\n' "$([ "$HEALTH_OK" -eq 1 ] && echo true || echo false)" "$VERSION" "$SCRIPT_DIR" "$SMOKE_PORT" "$HEALTH_ERROR" > "$HEALTH_REPORT"
fi

if [ "$HEALTH_OK" -ne 1 ]; then
  if [ -n "$PREVIOUS_RECEIPT" ] && [ -f "$PREVIOUS_RECEIPT" ]; then cp -f "$PREVIOUS_RECEIPT" "$RECEIPT_PATH"; else rm -f "$RECEIPT_PATH"; fi
  echo 'New release health checks failed. Previous authorization and Desktop launcher were left active.'
  echo "Review: $HEALTH_LOG"
  exit 1
fi

CURRENT_HASH="$(printf '%s' "$SCRIPT_DIR" | shasum -a 256 | awk '{print $1}' | cut -c1-24)"
CURRENT_RECEIPT="$ROLLBACK_DIR/receipt_${CURRENT_HASH}.json"
cp -f "$RECEIPT_PATH" "$CURRENT_RECEIPT" || {
  if [ -n "$PREVIOUS_RECEIPT" ] && [ -f "$PREVIOUS_RECEIPT" ]; then cp -f "$PREVIOUS_RECEIPT" "$RECEIPT_PATH"; else rm -f "$RECEIPT_PATH"; fi
  echo 'Could not preserve the new signed receipt; launcher unchanged.'; exit 1;
}

BASE_PYTHON_STATE="$(find_base_python 2>/dev/null || true)"
if [ -n "$BASE_PYTHON_STATE" ]; then
  STATE="$UPDATE_STATE_PATH" CUR_ROOT="$SCRIPT_DIR" CUR_VER="$VERSION" CUR_REC="$CURRENT_RECEIPT" PREV_ROOT="$PREVIOUS_ROOT" PREV_VER="$PREVIOUS_VERSION" PREV_REC="$PREVIOUS_RECEIPT" HEALTH="$HEALTH_REPORT" "$BASE_PYTHON_STATE" - <<'PYUPDATE'
import json,os,time
health={}
try: health=json.load(open(os.environ['HEALTH'],encoding='utf-8'))
except Exception: pass
state={'schema':1,'product':'TheGuoLab-CVStudio','updated_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'current_root':os.environ['CUR_ROOT'],'current_version':os.environ['CUR_VER'],'current_receipt':os.environ['CUR_REC'],'previous_root':os.environ.get('PREV_ROOT',''),'previous_version':os.environ.get('PREV_VER',''),'previous_receipt':os.environ.get('PREV_REC',''),'health':health}
p=os.environ['STATE']; tmp=p+'.tmp'; open(tmp,'w',encoding='utf-8').write(json.dumps(state,indent=2)); os.replace(tmp,p)
PYUPDATE
else
  STATE="$UPDATE_STATE_PATH" CUR_ROOT="$SCRIPT_DIR" CUR_VER="$VERSION" CUR_REC="$CURRENT_RECEIPT" PREV_ROOT="$PREVIOUS_ROOT" PREV_VER="$PREVIOUS_VERSION" PREV_REC="$PREVIOUS_RECEIPT" perl -MJSON::PP -e '$s={schema=>1,product=>"TheGuoLab-CVStudio",updated_at=>scalar(gmtime),current_root=>$ENV{CUR_ROOT},current_version=>$ENV{CUR_VER},current_receipt=>$ENV{CUR_REC},previous_root=>$ENV{PREV_ROOT},previous_version=>$ENV{PREV_VER},previous_receipt=>$ENV{PREV_REC}};open F,">",$ENV{STATE}.".tmp" or exit 2;print F JSON::PP->new->pretty->encode($s);close F;rename $ENV{STATE}.".tmp",$ENV{STATE} or exit 3;' || { if [ -n "$PREVIOUS_RECEIPT" ] && [ -f "$PREVIOUS_RECEIPT" ]; then cp -f "$PREVIOUS_RECEIPT" "$RECEIPT_PATH"; else rm -f "$RECEIPT_PATH"; fi; exit 1; }
fi

# Desktop launchers are changed only after health and rollback state succeed.
mkdir -p "$HOME/Desktop"
LAUNCHER="$HOME/Desktop/CV Studio.command"
printf '#!/bin/bash\nexport PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"\nbash %q\n' "$SCRIPT_DIR/start.sh" > "$LAUNCHER"
chmod +x "$LAUNCHER" "$SCRIPT_DIR/start.sh" 2>/dev/null || true
if [ -n "$PREVIOUS_ROOT" ] && [ -n "$PREVIOUS_RECEIPT" ]; then
  RESTORE_LAUNCHER="$HOME/Desktop/Restore Previous CV Studio.command"
  printf '#!/bin/bash\nexport PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"\nbash %q\nprintf "\\nPress Return to close..."; read _x\n' "$SCRIPT_DIR/restore_previous.sh" > "$RESTORE_LAUNCHER"
  chmod +x "$RESTORE_LAUNCHER" "$SCRIPT_DIR/restore_previous.sh" 2>/dev/null || true
  echo "  Rollback: $RESTORE_LAUNCHER"
  echo '  Keep the previous CV Studio folder until you are satisfied with this release.'
fi

echo ''
echo '============================================'
echo '  Setup Complete!'
echo "  Launch: $LAUNCHER"
echo '============================================'
