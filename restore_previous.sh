#!/bin/bash
# Restore the previous healthy CV Studio release and its signed root receipt.
set -u
STATE_DIR="$HOME/.guo_lab_cv_studio"
STATE_PATH="$STATE_DIR/update_state.json"
RECEIPT_PATH="$STATE_DIR/install_receipt.json"
LAUNCHER="$HOME/Desktop/CV Studio.command"
[ -f "$STATE_PATH" ] || { echo 'No CV Studio rollback state is available.'; exit 2; }

find_python(){ for p in python3 /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do command -v "$p" >/dev/null 2>&1 && { printf '%s\n' "$p"; return 0; }; done; return 1; }
PY="$(find_python 2>/dev/null || true)"
if [ -n "$PY" ]; then
  eval "$(STATE="$STATE_PATH" "$PY" - <<'PYREAD'
import json,os,shlex
s=json.load(open(os.environ['STATE'],encoding='utf-8'))
for k in ('current_root','current_version','current_receipt','previous_root','previous_version','previous_receipt'):
 print(k.upper()+'='+shlex.quote(str(s.get(k,''))))
PYREAD
)"
elif command -v perl >/dev/null 2>&1; then
  eval "$(STATE="$STATE_PATH" perl -MJSON::PP -e 'open F,"<",$ENV{STATE} or exit 2;local $/;my $s=decode_json(<F>);for my $k(qw(current_root current_version current_receipt previous_root previous_version previous_receipt)){my $v=$s->{$k}//"";$v=~s/'"'"'/'"'"'\\'"'"''"'"'/g;print uc($k)."='"'"'$v'"'"'\\n";}' )"
else
  echo 'Python 3 or Perl is required to read rollback state.'; exit 2
fi

[ -n "${PREVIOUS_ROOT:-}" ] && [ -f "$PREVIOUS_ROOT/start.sh" ] || { echo 'The previous CV Studio folder is missing. Nothing was changed.'; exit 3; }
[ -n "${PREVIOUS_RECEIPT:-}" ] && [ -f "$PREVIOUS_RECEIPT" ] || { echo 'The previous signed receipt is missing. Nothing was changed.'; exit 4; }

mkdir -p "$STATE_DIR" "$HOME/Desktop"
SAFETY="$STATE_DIR/install_receipt.before_restore.$$.json"
LAUNCHER_BACKUP="$STATE_DIR/launcher.before_restore.$$.command"
LAUNCHER_TEMP="$STATE_DIR/launcher.restore.$$.command"
HAD_LAUNCHER=0
[ -f "$RECEIPT_PATH" ] && cp -f "$RECEIPT_PATH" "$SAFETY"
if [ -f "$LAUNCHER" ]; then cp -f "$LAUNCHER" "$LAUNCHER_BACKUP" && HAD_LAUNCHER=1; fi

rollback_partial(){
  if [ -f "$SAFETY" ]; then cp -f "$SAFETY" "$RECEIPT_PATH"; else rm -f "$RECEIPT_PATH"; fi
  if [ "$HAD_LAUNCHER" -eq 1 ] && [ -f "$LAUNCHER_BACKUP" ]; then cp -f "$LAUNCHER_BACKUP" "$LAUNCHER"; else rm -f "$LAUNCHER"; fi
  rm -f "$SAFETY" "$LAUNCHER_BACKUP" "$LAUNCHER_TEMP"
}

cp -f "$PREVIOUS_RECEIPT" "$RECEIPT_PATH" || { rollback_partial; echo 'Could not stage previous receipt.'; exit 5; }
verify_previous(){
  local native=''
  if [ -d "$PREVIOUS_ROOT/runtime/native" ]; then native="$(find "$PREVIOUS_ROOT/runtime/native" -maxdepth 1 -type f -name 'CVStudio*' -perm -111 2>/dev/null | head -1)"; fi
  if [ -n "$native" ]; then "$native" --check-install-receipt >/dev/null 2>&1; return $?; fi
  local p=''
  for p in "$STATE_DIR/venv/bin/python3" "$STATE_DIR/venv/bin/python" python3 /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    command -v "$p" >/dev/null 2>&1 && "$p" "$PREVIOUS_ROOT/app.py" --check-install-receipt >/dev/null 2>&1 && return 0
  done
  return 1
}
if ! verify_previous; then rollback_partial; echo 'Previous signed receipt did not verify. Current release remains active.'; exit 5; fi

PORT_PID="$(lsof -nP -tiTCP:5000 -sTCP:LISTEN 2>/dev/null | head -1)"
if [ -n "$PORT_PID" ]; then
  CMD="$(ps -p "$PORT_PID" -o command= 2>/dev/null || true)"
  case "$CMD" in *"${CURRENT_ROOT:-}"*) kill "$PORT_PID" 2>/dev/null || true; sleep 1;; esac
fi

printf '#!/bin/bash\nexport PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"\nbash %q\n' "$PREVIOUS_ROOT/start.sh" > "$LAUNCHER_TEMP" || { rollback_partial; echo 'Could not prepare the previous launcher.'; exit 5; }
chmod +x "$LAUNCHER_TEMP" 2>/dev/null || true
mv -f "$LAUNCHER_TEMP" "$LAUNCHER" || { rollback_partial; echo 'Could not switch the Desktop launcher.'; exit 5; }
chmod +x "$LAUNCHER" 2>/dev/null || true

STATE_OK=0
if [ -n "$PY" ]; then
  STATE="$STATE_PATH" "$PY" - <<'PYSWAP' && STATE_OK=1
import json,os,time
p=os.environ['STATE'];s=json.load(open(p,encoding='utf-8'))
for a,b in (('current_root','previous_root'),('current_version','previous_version'),('current_receipt','previous_receipt')): s[a],s[b]=s.get(b,''),s.get(a,'')
s['restored_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());s['health']=None
t=p+'.tmp';open(t,'w',encoding='utf-8').write(json.dumps(s,indent=2));os.replace(t,p)
PYSWAP
else
  STATE="$STATE_PATH" perl -MJSON::PP -e 'open F,"<",$ENV{STATE} or exit 2;local $/;my $s=decode_json(<F>);for my $pair([qw(current_root previous_root)],[qw(current_version previous_version)],[qw(current_receipt previous_receipt)]){my($a,$b)=@$pair;($s->{$a},$s->{$b})=($s->{$b}//"",$s->{$a}//"")} $s->{restored_at}=scalar(gmtime);$s->{health}=undef;open O,">",$ENV{STATE}.".tmp" or exit 3;print O JSON::PP->new->pretty->encode($s);close O;rename $ENV{STATE}.".tmp",$ENV{STATE} or exit 4;' && STATE_OK=1
fi
if [ "$STATE_OK" -ne 1 ]; then rollback_partial; echo 'Could not commit rollback state. Current release remains active.'; exit 5; fi

rm -f "$SAFETY" "$LAUNCHER_BACKUP" "$LAUNCHER_TEMP"
echo "Restored CV Studio ${PREVIOUS_VERSION:-previous version} from:"
echo "$PREVIOUS_ROOT"
exit 0
