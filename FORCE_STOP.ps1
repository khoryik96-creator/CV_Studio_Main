param([string]$Root = $PSScriptRoot)
$ErrorActionPreference = 'SilentlyContinue'

# FORCE_STOP is the deliberate "really kill it" companion to STOP.bat. STOP.bat
# only stops a server it can positively verify belongs to THIS package folder,
# so an orphan launched from an older or renamed copy (a common cause of the
# "another CV Studio process changed before it could be stopped" dialog)
# survives it. This helper instead kills the watchdog and any Python process
# LISTENING on port 5000 - a strong CV Studio signal - regardless of which copy
# launched it. It deliberately leaves STOP.bat's careful default untouched.

Write-Host "Force-stopping CV Studio: watchdog first, then any Python server on port 5000."

# 1) Watchdog(s) first, or they respawn the server. Match any copy's WATCHDOG.vbs.
$watchdogs = @(Get-CimInstance Win32_Process -Filter "Name='wscript.exe' OR Name='cscript.exe'" -ErrorAction SilentlyContinue | Where-Object {
    ([string]$_.CommandLine).ToLowerInvariant().Contains('watchdog.vbs')
})
foreach ($w in $watchdogs) {
    Stop-Process -Id ([int]$w.ProcessId) -Force -ErrorAction SilentlyContinue
    Write-Host ("  Stopped watchdog process {0}." -f $w.ProcessId)
}

# 2) Any Python process LISTENING on port 5000. A python.exe you code with does
#    not listen on 5000; the hidden CV Studio server (pythonw.exe) does. This is
#    what bypasses the package-root identity check that STOP.bat relies on.
$listeners = @()
try {
    $listeners = @(Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
} catch { $listeners = @() }
if (-not $listeners -or $listeners.Count -eq 0) {
    # Fallback for older Windows without Get-NetTCPConnection.
    $listeners = @(netstat -ano | Select-String ':5000\s' | Select-String 'LISTENING' | ForEach-Object { ($_.ToString().Trim() -split '\s+')[-1] } | Sort-Object -Unique)
}
$killed = 0
foreach ($procId in $listeners) {
    $pidValue = 0
    [void][int]::TryParse([string]$procId, [ref]$pidValue)
    if ($pidValue -le 0) { continue }
    $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if (-not $proc) { continue }
    $pname = ([string]$proc.ProcessName).ToLowerInvariant()
    if ($pname -in @('python','pythonw','python3','cvstudio')) {
        Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
        Write-Host ("  Stopped {0} (PID {1}) listening on port 5000." -f $proc.ProcessName, $pidValue)
        $killed++
    } else {
        Write-Host ("  Port 5000 is held by '{0}' (PID {1}), which is not CV Studio - left running." -f $proc.ProcessName, $pidValue)
    }
}

# 3) Clear stale CV Studio PID files so the next launch starts clean.
$stateDir = Join-Path $env:LOCALAPPDATA 'TheGuoLab\CVStudio'
if (Test-Path -LiteralPath $stateDir) {
    Get-ChildItem -LiteralPath $stateDir -Filter 'cvstudio.*.pid.json' -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
    }
}

# 4) Verify the port is actually free now.
Start-Sleep -Milliseconds 400
$still = @()
try { $still = @(Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue) } catch { $still = @() }
if ($still -and $still.Count -gt 0) {
    Write-Host ("WARNING: port 5000 still has a listener (PID {0}). If it is not CV Studio, close that program; otherwise re-run FORCE_STOP." -f $still[0].OwningProcess)
    exit 2
}
Write-Host "CV Studio force-stop complete. Port 5000 is free - you can start CV Studio fresh."
exit 0
