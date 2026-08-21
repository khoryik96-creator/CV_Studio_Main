param(
    [ValidateSet('Inspect','Stop')]
    [string]$Mode = 'Inspect',
    [string]$Root = $PSScriptRoot,
    [int]$ExpectedPid = 0,
    [switch]$PreserveWatchdog
)
$ErrorActionPreference = 'SilentlyContinue'

function Normalize-PathText([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return '' }
    try { return [IO.Path]::GetFullPath($Value).TrimEnd('\','/').ToLowerInvariant() }
    catch { return $Value.Trim().TrimEnd('\','/').ToLowerInvariant() }
}

function Get-Sha256([string]$Value) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes([string]$Value))).Replace('-','').ToLowerInvariant())
    }
    finally { $sha.Dispose() }
}

function Find-CVStudioRoot($Proc) {
    if (-not $Proc) { return '' }
    $name = ([string]$Proc.Name).ToLowerInvariant()
    if ($name -notin @('cvstudio.exe','cvstudio','python.exe','pythonw.exe','python3.exe','python3','python')) { return '' }
    $exe = [string]$Proc.ExecutablePath
    if ($exe) {
        $normExe = Normalize-PathText $exe
        $marker = '\runtime\native\'
        $idx = $normExe.IndexOf($marker,[StringComparison]::OrdinalIgnoreCase)
        if ($idx -gt 0) { return $normExe.Substring(0,$idx) }
    }
    $cmd = [string]$Proc.CommandLine
    if ($cmd) {
        $matches = [regex]::Matches($cmd, '(?i)(?:^|\s)(?:"([^"]+?\\app\.pyc?)"|([^\s"]+?\\app\.pyc?))(?:\s|$)')
        foreach ($m in $matches) {
            $entry = if ($m.Groups[1].Success) { $m.Groups[1].Value } else { $m.Groups[2].Value }
            if ($entry) { return Normalize-PathText (Split-Path -Parent $entry) }
        }
    }
    return ''
}

function Get-CVStudioHttpIdentity([int]$ListenerPid, [string]$ProcessName) {
    $allowed = @('cvstudio.exe','cvstudio','python.exe','pythonw.exe','python3.exe','python3','python')
    if (([string]$ProcessName).ToLowerInvariant() -notin $allowed) { return $null }
    try {
        $response = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/instance' -Method Get -TimeoutSec 2 -Headers @{ 'Cache-Control'='no-cache' }
        if (-not $response -or [string]$response.product -ne 'CV Studio') { return $null }
        if ([int]$response.pid -ne $ListenerPid) { return $null }
        $ownerRoot = Normalize-PathText ([string]$response.root)
        $instanceId = ([string]$response.instance_id).Trim().ToLowerInvariant()
        $rootHash = ([string]$response.root_hash).Trim().ToLowerInvariant()
        $version = ([string]$response.version).Trim()
        if (-not $ownerRoot -or -not $instanceId -or $version -notmatch '^v\d+(?:\.\d+)+$') { return $null }
        $calculated = Get-Sha256 $ownerRoot
        if ($instanceId -ne $calculated.Substring(0,24)) { return $null }
        if ($rootHash -and $rootHash -ne $calculated) { return $null }
        return [pscustomobject]@{ Root=$ownerRoot; Version=$version; InstanceId=$instanceId; Verified=$true }
    }
    catch { return $null }
}

function Stop-CVStudioWatchdogs([string]$OwnerRoot) {
    $rootValue = Normalize-PathText $OwnerRoot
    if (-not $rootValue) { return }
    $watchdogPath = Normalize-PathText (Join-Path $rootValue 'WATCHDOG.vbs')
    Get-CimInstance Win32_Process -Filter "Name='wscript.exe' OR Name='cscript.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
        $cmd = ([string]$_.CommandLine).Replace('/','\').ToLowerInvariant()
        if ($cmd -and $cmd.Contains($watchdogPath)) {
            Stop-Process -Id ([int]$_.ProcessId) -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-PortRecord {
    $listener = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $listener) { return [pscustomobject]@{ State='free'; Pid=0; Root=''; Name=''; Verified=$false } }
    $pidValue = [int]$listener.OwningProcess
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue" -ErrorAction SilentlyContinue
    $name = if ($proc) { [string]$proc.Name } else { '' }
    $identity = Get-CVStudioHttpIdentity $pidValue $name
    $commandRoot = Find-CVStudioRoot $proc
    $ownerRoot = if ($identity) { [string]$identity.Root } else { $commandRoot }
    $status = 'unrelated'
    if ($identity) {
        if ((Normalize-PathText $ownerRoot) -eq (Normalize-PathText $Root)) { $status = 'same' } else { $status = 'other' }
    } elseif ($commandRoot -and (Normalize-PathText $commandRoot) -eq (Normalize-PathText $Root)) {
        # A non-responsive process may still be stopped by its own package, but a
        # different package is never killed without the signed-root-style HTTP identity.
        $status = 'same'
    }
    return [pscustomobject]@{ State=$status; Pid=$pidValue; Root=$ownerRoot; Name=$name; Verified=[bool]$identity }
}

$record = Get-PortRecord
if ($Mode -eq 'Stop') {
    if ($ExpectedPid -le 0 -or [int]$record.Pid -ne $ExpectedPid) {
        Write-Output ("changed`t$($record.Pid)`t$($record.Root)`t$($record.Name)")
        exit 4
    }
    if ($record.State -notin @('same','other')) {
        Write-Output ("unrelated`t$($record.Pid)`t$($record.Root)`t$($record.Name)")
        exit 5
    }

    # Deliberate Stop/upgrade/package-replacement callers must stop the old
    # watchdog before its listener. During watchdog-initiated recovery, keep the
    # calling watchdog alive so it can launch the replacement after this helper
    # terminates the unresponsive listener.
    if (-not $PreserveWatchdog) {
        Stop-CVStudioWatchdogs $record.Root
    }
    Stop-Process -Id ([int]$record.Pid) -Force -ErrorAction Stop

    # Close a small restart race.  Re-stop only a listener that still proves it is
    # CV Studio from the same package root; never kill an arbitrary port owner.
    for ($attempt = 0; $attempt -lt 4; $attempt++) {
        Start-Sleep -Milliseconds 300
        $again = Get-PortRecord
        if ($again.State -eq 'free') { break }
        if ($again.State -in @('same','other') -and (Normalize-PathText $again.Root) -eq (Normalize-PathText $record.Root)) {
            if (-not $PreserveWatchdog) {
                Stop-CVStudioWatchdogs $again.Root
            }
            Stop-Process -Id ([int]$again.Pid) -Force -ErrorAction SilentlyContinue
            continue
        }
        break
    }
    Write-Output ("stopped`t$($record.Pid)`t$($record.Root)`t$($record.Name)")
    exit 0
}
Write-Output ("$($record.State)`t$($record.Pid)`t$($record.Root)`t$($record.Name)")
