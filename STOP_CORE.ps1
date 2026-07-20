param([string]$Root = $PSScriptRoot)
$ErrorActionPreference = 'SilentlyContinue'

function Normalize-PathText([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return '' }
    try { return [IO.Path]::GetFullPath($Value).TrimEnd('\','/').ToLowerInvariant() }
    catch { return $Value.Trim().TrimEnd('\','/').ToLowerInvariant() }
}
function Test-PathWithin([string]$Candidate,[string]$Base) {
    $c=Normalize-PathText $Candidate; $b=Normalize-PathText $Base
    if(-not $c -or -not $b){return $false}
    return ($c -eq $b -or $c.StartsWith($b+'\',[StringComparison]::OrdinalIgnoreCase) -or $c.StartsWith($b+'/',[StringComparison]::OrdinalIgnoreCase))
}
function Get-ProcessInfo([int]$PidValue) {
    if($PidValue -le 0){return $null}
    Get-CimInstance Win32_Process -Filter "ProcessId=$PidValue" -ErrorAction SilentlyContinue
}
function Find-CVStudioRoot($Proc) {
    if(-not $Proc){return ''}
    $name=([string]$Proc.Name).ToLowerInvariant()
    if($name -notin @('cvstudio.exe','cvstudio','python.exe','pythonw.exe','python3.exe','python3','python')){return ''}
    $exe=[string]$Proc.ExecutablePath
    if($exe){
        $normExe=Normalize-PathText $exe
        $marker='\runtime\native\'
        $idx=$normExe.IndexOf($marker,[StringComparison]::OrdinalIgnoreCase)
        if($idx -gt 0){return $normExe.Substring(0,$idx)}
    }
    $cmd=[string]$Proc.CommandLine
    if($cmd){
        $matches=[regex]::Matches($cmd,'(?i)(?:^|\s)(?:"([^"]+?\\app\.pyc?)"|([^\s"]+?\\app\.pyc?))(?:\s|$)')
        foreach($m in $matches){
            $entry=if($m.Groups[1].Success){$m.Groups[1].Value}else{$m.Groups[2].Value}
            if($entry){return Normalize-PathText (Split-Path -Parent $entry)}
        }
    }
    return ''
}
function Stop-ExactWatchdog([string]$OwnerRoot) {
    $rootValue=Normalize-PathText $OwnerRoot
    if(-not $rootValue){return 0}
    $watchdogPath=Normalize-PathText (Join-Path $rootValue 'WATCHDOG.vbs')
    $targets=@(Get-CimInstance Win32_Process -Filter "Name='wscript.exe' OR Name='cscript.exe'" -ErrorAction SilentlyContinue|Where-Object{
        $cmd=([string]$_.CommandLine).Replace('/','\').ToLowerInvariant()
        $cmd -and $cmd.Contains($watchdogPath)
    })
    foreach($target in $targets){
        Stop-Process -Id ([int]$target.ProcessId)-Force -ErrorAction SilentlyContinue
        Write-Host "Stopped CV Studio watchdog $($target.ProcessId)."
    }
    return $targets.Count
}
function Parse-PortInfo([string]$Text) {
    $parts=[string]$Text -split "`t",4
    return [pscustomobject]@{
        State=if($parts.Count -gt 0){$parts[0]}else{''}
        Pid=if($parts.Count -gt 1){[int]$parts[1]}else{0}
        Root=if($parts.Count -gt 2){$parts[2]}else{''}
        Name=if($parts.Count -gt 3){$parts[3]}else{''}
    }
}

$Root=Normalize-PathText $Root
$sha=[Security.Cryptography.SHA256]::Create()
try { $hash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Root))).Replace('-','').ToLowerInvariant()) }
finally { $sha.Dispose() }
$instance=$hash.Substring(0,24)
$stateDir=Join-Path $env:LOCALAPPDATA 'TheGuoLab\CVStudio'
$pidFile=Join-Path $stateDir ("cvstudio.$instance.pid.json")
$helper=Join-Path $Root 'INSTANCE_PORT.ps1'
$stopped=$false

# Stop this package's watchdog first.  A stale watchdog was the reason an old
# pythonw.exe could come back after STOP.bat appeared to succeed.
$watchdogsStopped=Stop-ExactWatchdog $Root
if($watchdogsStopped -gt 0){$stopped=$true}

# The port helper validates /instance, PID, package-root hash and process type.
# This lets STOP.bat safely identify an older CV Studio package even when its
# pythonw command line contains only a relative app.py path.
if(Test-Path -LiteralPath $helper){
    $rawInspect = (& $helper -Mode Inspect -Root $Root | Select-Object -Last 1)
    $port = Parse-PortInfo $rawInspect
    if($port.State -in @('same','other') -and $port.Pid -gt 0){
        if($port.State -eq 'other'){ Write-Host "Found an older/different CV Studio package on port 5000: $($port.Root)" }
        $oldWatchdogsStopped=Stop-ExactWatchdog $port.Root
        if($oldWatchdogsStopped -gt 0){$stopped=$true}
        $rawStop = (& $helper -Mode Stop -Root $Root -ExpectedPid $port.Pid | Select-Object -Last 1)
        $stopResult = Parse-PortInfo $rawStop
        if($stopResult.State -eq 'stopped'){
            Write-Host "Stopped verified CV Studio listener $($port.Pid)."
            $stopped=$true
        } else {
            Write-Warning "The CV Studio listener changed before it could be stopped ($($stopResult.State))."
        }
    } elseif($port.State -eq 'unrelated' -and $port.Pid -gt 0){
        Write-Warning "Port 5000 belongs to another program ($($port.Name), PID $($port.Pid)); it was not stopped."
    }
}

# Keep the package-scoped PID fallback for a server that is still starting and
# has not opened port 5000 yet.  It may stop only a process whose executable or
# absolute app entry resolves back to this exact package root.
if(Test-Path -LiteralPath $pidFile){
    try{
        $record=Get-Content -LiteralPath $pidFile -Raw -Encoding UTF8|ConvertFrom-Json
        if([string]$record.instance_id -eq $instance -and (Normalize-PathText ([string]$record.root)) -eq $Root){
            $proc=Get-ProcessInfo ([int]$record.pid)
            $ownerRoot=Find-CVStudioRoot $proc
            if($proc -and $ownerRoot -and (Normalize-PathText $ownerRoot) -eq $Root){
                Stop-Process -Id ([int]$record.pid) -Force -ErrorAction Stop
                Write-Host "Stopped CV Studio process $($record.pid)."
                $stopped=$true
            } elseif($proc){
                Write-Warning 'The saved PID belongs to another program and was not stopped.'
            }
        }
    }catch{Write-Warning "Could not use the saved CV Studio PID: $($_.Exception.Message)"}
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

if(-not $stopped){Write-Host 'No running CV Studio server was found.'}
exit 0
