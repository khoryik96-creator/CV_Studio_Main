param([switch]$Stop, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$sourcerRoot = $PSScriptRoot
$sourcerBridge = Join-Path $sourcerRoot 'bridge.py'
$sourcerPython = Join-Path $sourcerRoot '.venv\Scripts\python.exe'
$sourcerRuntime = Join-Path $sourcerRoot 'runtime'
$sourcerPidFile = Join-Path $sourcerRuntime 'bridge.pid'
if ($Stop) {
    if (Test-Path -LiteralPath $sourcerPidFile) {
        $sourcerProcessId = [int](Get-Content -LiteralPath $sourcerPidFile -Raw)
        $sourcerProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $sourcerProcessId"
        if ($sourcerProcess -and $sourcerProcess.ExecutablePath -eq $sourcerPython -and
            $sourcerProcess.CommandLine.Contains($sourcerBridge)) {
            # The Windows venv launcher may own a Python child. Stop this
            # verified POC process tree, never a process selected by port alone.
            & taskkill.exe /PID $sourcerProcessId /T /F | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'The matching POC process could not be stopped.' }
            Write-Host 'Sourcer POC bridge stopped.'
        } elseif ($sourcerProcess) { throw 'The saved process does not match this POC. Nothing was stopped.' }
    }
    exit 0
}
try {
    $sourcerHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:5073/health' -TimeoutSec 2
    if ($sourcerHealth.product -eq 'CVStudioSourcerPOC') {
        if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5073/' }
        exit 0
    }
} catch { }
if (Get-NetTCPConnection -LocalPort 5073 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 5073 is in use by another application. It was left untouched.'
}
if (-not (Test-Path -LiteralPath $sourcerPython)) {
    Write-Host 'Preparing the separate POC environment. Your CV Studio installation is unchanged.'
    $sourcerLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($sourcerLauncher) { & $sourcerLauncher.Source -3 -m venv (Join-Path $sourcerRoot '.venv') }
    else {
        $sourcerLauncher = Get-Command python.exe -ErrorAction SilentlyContinue
        if (-not $sourcerLauncher) { throw 'Python 3.10 or newer is required for this POC.' }
        & $sourcerLauncher.Source -m venv (Join-Path $sourcerRoot '.venv')
    }
    if ($LASTEXITCODE -ne 0) { throw 'The separate Python environment could not be created.' }
}
& $sourcerPython -c "import importlib.util; raise SystemExit(0 if all(importlib.util.find_spec(p) for p in ('flask', 'requests')) else 1)"
if ($LASTEXITCODE -ne 0) {
    & $sourcerPython -m pip install --disable-pip-version-check -r (Join-Path $sourcerRoot 'requirements-poc.txt')
    if ($LASTEXITCODE -ne 0) { throw 'POC dependencies could not be installed.' }
}
[void](New-Item -ItemType Directory -Path $sourcerRuntime -Force)
$sourcerArguments = @(('"' + $sourcerBridge + '"'), '--port', '5073')
$sourcerProcess = Start-Process -FilePath $sourcerPython -ArgumentList $sourcerArguments `
    -WorkingDirectory $sourcerRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $sourcerRuntime 'bridge.log') `
    -RedirectStandardError (Join-Path $sourcerRuntime 'bridge-error.log')
$sourcerProcess.Id | Set-Content -LiteralPath $sourcerPidFile -Encoding ascii
for ($sourcerAttempt = 0; $sourcerAttempt -lt 30; $sourcerAttempt++) {
    try {
        $sourcerHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:5073/health' -TimeoutSec 1
        if ($sourcerHealth.product -eq 'CVStudioSourcerPOC') {
            if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5073/' }
            exit 0
        }
    } catch { }
    Start-Sleep -Milliseconds 300
}
throw 'The POC bridge did not start. See its runtime bridge-error.log.'
