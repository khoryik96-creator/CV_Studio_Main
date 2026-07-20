$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $env:LOCALAPPDATA 'TheGuoLab\CVStudio'
$StatePath = Join-Path $StateDir 'update_state.json'
$ReceiptPath = Join-Path $StateDir 'install_receipt.json'

function Write-StateAtomic($State) {
    $tmp = $StatePath + '.tmp'
    $State | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination $StatePath -Force
}

if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
    Write-Host 'No CV Studio rollback state is available.'
    exit 2
}
$state = Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json
$previousRoot = [string]$state.previous_root
$previousReceipt = [string]$state.previous_receipt
$currentRoot = [string]$state.current_root
if (-not $previousRoot -or -not (Test-Path -LiteralPath (Join-Path $previousRoot 'CV Studio.bat') -PathType Leaf)) {
    Write-Host 'The previous CV Studio folder is missing. Nothing was changed.'
    exit 3
}
if (-not $previousReceipt -or -not (Test-Path -LiteralPath $previousReceipt -PathType Leaf)) {
    Write-Host 'The previous signed install receipt is missing. Nothing was changed.'
    exit 4
}

New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
$receiptSafety = Join-Path $StateDir ('install_receipt.before_restore.' + [guid]::NewGuid().ToString('N') + '.json')
$launcherSafety = Join-Path $StateDir ('launcher.before_restore.' + [guid]::NewGuid().ToString('N') + '.lnk')
$hadReceipt = Test-Path -LiteralPath $ReceiptPath -PathType Leaf
if ($hadReceipt) { Copy-Item -LiteralPath $ReceiptPath -Destination $receiptSafety -Force }
$desktop = [Environment]::GetFolderPath('Desktop')
if (-not $desktop) { $desktop = Join-Path $env:USERPROFILE 'Desktop' }
if (-not (Test-Path -LiteralPath $desktop)) { New-Item -ItemType Directory -Path $desktop -Force | Out-Null }
$linkPath = Join-Path $desktop 'CV Studio.lnk'
$hadLauncher = Test-Path -LiteralPath $linkPath -PathType Leaf
if ($hadLauncher) { Copy-Item -LiteralPath $linkPath -Destination $launcherSafety -Force }

try {
    Copy-Item -LiteralPath $previousReceipt -Destination $ReceiptPath -Force
    $verifyScript = Join-Path $previousRoot 'INSTALL_RECEIPT.ps1'
    if (-not (Test-Path -LiteralPath $verifyScript -PathType Leaf)) { throw 'Previous receipt verifier is missing.' }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verifyScript -Mode Verify | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Previous signed receipt did not verify for this computer and folder.' }

    $stopScript = Join-Path $currentRoot 'STOP_CORE.ps1'
    if ($currentRoot -and (Test-Path -LiteralPath $stopScript -PathType Leaf)) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stopScript -Root $currentRoot | Out-Null
    }

    $ws = New-Object -ComObject WScript.Shell
    $shortcut = $ws.CreateShortcut($linkPath)
    $shortcut.TargetPath = Join-Path $previousRoot 'CV Studio.bat'
    $shortcut.WorkingDirectory = $previousRoot
    $icon = Join-Path $previousRoot 'cv_studio.ico'
    if (Test-Path -LiteralPath $icon) { $shortcut.IconLocation = $icon }
    $shortcut.Description = 'The 郭 Lab - CV Studio'
    $shortcut.Save()
    if (-not (Test-Path -LiteralPath $linkPath -PathType Leaf)) { throw 'The previous Desktop launcher could not be created.' }

    $oldCurrentRoot = [string]$state.current_root
    $oldCurrentVersion = [string]$state.current_version
    $oldCurrentReceipt = [string]$state.current_receipt
    $state.current_root = [string]$state.previous_root
    $state.current_version = [string]$state.previous_version
    $state.current_receipt = [string]$state.previous_receipt
    $state.previous_root = $oldCurrentRoot
    $state.previous_version = $oldCurrentVersion
    $state.previous_receipt = $oldCurrentReceipt
    $state.restored_at = [DateTime]::UtcNow.ToString('o')
    $state.health = $null
    Write-StateAtomic $state

    Remove-Item -LiteralPath $receiptSafety,$launcherSafety -Force -ErrorAction SilentlyContinue
    Write-Host "Restored CV Studio $($state.current_version) from:"
    Write-Host $state.current_root
    exit 0
} catch {
    if ($hadReceipt -and (Test-Path -LiteralPath $receiptSafety -PathType Leaf)) {
        Copy-Item -LiteralPath $receiptSafety -Destination $ReceiptPath -Force
    } elseif (Test-Path -LiteralPath $ReceiptPath) {
        Remove-Item -LiteralPath $ReceiptPath -Force -ErrorAction SilentlyContinue
    }
    if ($hadLauncher -and (Test-Path -LiteralPath $launcherSafety -PathType Leaf)) {
        Copy-Item -LiteralPath $launcherSafety -Destination $linkPath -Force
    } elseif (Test-Path -LiteralPath $linkPath) {
        Remove-Item -LiteralPath $linkPath -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $receiptSafety,$launcherSafety -Force -ErrorAction SilentlyContinue
    Write-Host "Restore failed. The current release remains active. $($_.Exception.Message)"
    exit 5
}
