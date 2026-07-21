$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Root.EndsWith('\')) { $Root += '\' }
$Log = Join-Path $Root 'install_log.txt'
$InstallVersion = 'v24.6.221'
$TargetMarker = Join-Path $Root 'PROTECTED_PLATFORM_TARGET.txt'
$script:IsProtectedPackage = Test-Path -LiteralPath $TargetMarker
$script:ProtectedNativeExe = Join-Path $Root 'runtime\native\CVStudio.exe'
$script:ProtectedAdmZipPackage = Join-Path $Root 'node_modules\adm-zip\package.json'
if ($script:IsProtectedPackage) {
    $TargetValue = (Get-Content -LiteralPath $TargetMarker -Raw -Encoding UTF8).Trim()
    if ($TargetValue -ne 'windows-x64') { Write-Host "This protected package targets $TargetValue and cannot be installed on Windows."; exit 2 }
    if (-not [Environment]::Is64BitOperatingSystem) { Write-Host 'This protected package requires 64-bit Windows 10 or 11.'; exit 2 }

    # Never misclassify a damaged/quarantined protected package as an owner/source
    # build. That old fallback produced misleading Python/npm errors even though a
    # protected colleague package should contain its native backend and adm-zip.
    $protectedProblems = @()
    if (-not (Test-Path -LiteralPath $script:ProtectedNativeExe -PathType Leaf)) {
        $protectedProblems += 'runtime\native\CVStudio.exe is missing (it may have been quarantined by antivirus or omitted from the ZIP).'
    } else {
        try {
            if ((Get-Item -LiteralPath $script:ProtectedNativeExe).Length -lt 102400) {
                $protectedProblems += 'runtime\native\CVStudio.exe is unexpectedly small or damaged.'
            }
        } catch {
            $protectedProblems += 'runtime\native\CVStudio.exe could not be inspected.'
        }
    }
    if (-not (Test-Path -LiteralPath $script:ProtectedAdmZipPackage -PathType Leaf)) {
        $protectedProblems += 'the bundled node_modules\adm-zip runtime dependency is missing.'
    }
    if ($protectedProblems.Count -gt 0) {
        $message = 'Protected package is incomplete or was modified. ' + ($protectedProblems -join ' ')
        Write-Host 'ERROR: Protected package validation failed.'
        $protectedProblems | ForEach-Object { Write-Host "  - $_" }
        Write-Host 'Re-extract the original protected Windows ZIP to a short folder. Check Windows Security Protection history for CVStudio.exe. Do not install from a partially copied folder.'
        try { Set-Content -LiteralPath $Log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $message" -Encoding UTF8 } catch {}
        exit 2
    }
}

function Write-Step {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Message"
    Write-Host $Message
    Add-Content -LiteralPath $Log -Value $line -Encoding UTF8
}

function Write-Blank { Write-Host ''; Add-Content -LiteralPath $Log -Value '' -Encoding UTF8 }


function Get-InstallerTotpSecret {
    # Offline TOTP must reconstruct verifier material locally. The owner QR/setup key
    # is intentionally absent from the colleague package, but this remains a local
    # access gate rather than cryptographic licensing.
    [byte[]]$mask = @(147, 57, 36, 83, 116, 245, 122, 57, 165, 162, 176, 168, 249, 50, 204, 128, 45, 174, 232, 56)
    [byte[]]$masked = @(49, 16, 244, 145, 19, 123, 118, 27, 71, 171, 180, 177, 120, 122, 255, 68, 100, 150, 118, 10)
    if ($mask.Length -ne $masked.Length) { throw 'Installer verifier is invalid.' }
    [byte[]]$secret = New-Object byte[] $mask.Length
    for ($i = 0; $i -lt $mask.Length; $i++) {
        $secret[$i] = [byte]($mask[$i] -bxor $masked[$i])
    }
    return $secret
}

function Get-InstallerTotpCode {
    param([byte[]]$Secret, [Int64]$Counter)
    [byte[]]$counterBytes = [BitConverter]::GetBytes($Counter)
    if ([BitConverter]::IsLittleEndian) { [Array]::Reverse($counterBytes) }
    $hmac = New-Object Security.Cryptography.HMACSHA1
    try {
        $hmac.Key = $Secret
        [byte[]]$digest = $hmac.ComputeHash($counterBytes)
    } finally {
        $hmac.Dispose()
    }
    $offset = $digest[$digest.Length - 1] -band 0x0F
    [Int64]$binary = (([Int64]($digest[$offset] -band 0x7F)) -shl 24) -bor
                       (([Int64]($digest[$offset + 1] -band 0xFF)) -shl 16) -bor
                       (([Int64]($digest[$offset + 2] -band 0xFF)) -shl 8) -bor
                       ([Int64]($digest[$offset + 3] -band 0xFF))
    return ([Int64]($binary % 1000000)).ToString('D6')
}

function Test-InstallerTotpCode {
    param([string]$Code)
    if ([string]::IsNullOrWhiteSpace($Code) -or $Code -notmatch '^\d{6}$') { return $false }
    [byte[]]$secret = Get-InstallerTotpSecret
    try {
        $epoch = [DateTime]::SpecifyKind([DateTime]'1970-01-01 00:00:00', [DateTimeKind]::Utc)
        [Int64]$unixSeconds = [Int64][Math]::Floor(([DateTime]::UtcNow - $epoch).TotalSeconds)
        [Int64]$counter = [Int64][Math]::Floor($unixSeconds / 30)
        foreach ($delta in @(-1, 0, 1)) {
            if ((Get-InstallerTotpCode -Secret $secret -Counter ($counter + $delta)) -eq $Code) { return $true }
        }
        return $false
    } finally {
        if ($secret) { [Array]::Clear($secret, 0, $secret.Length) }
    }
}

function Get-InstallerApprovalSignature {
    param([string]$IssuedAt, [string]$Nonce)
    [byte[]]$secret = Get-InstallerTotpSecret
    try {
        [byte[]]$suffix = [Text.Encoding]::UTF8.GetBytes('|CVStudio|install-receipt-v1')
        [byte[]]$material = New-Object byte[] ($secret.Length + $suffix.Length)
        [Array]::Copy($secret, 0, $material, 0, $secret.Length)
        [Array]::Copy($suffix, 0, $material, $secret.Length, $suffix.Length)
        $sha = [Security.Cryptography.SHA256]::Create()
        try { [byte[]]$key = $sha.ComputeHash($material) } finally { $sha.Dispose(); [Array]::Clear($material, 0, $material.Length) }
        $rootText = [IO.Path]::GetFullPath($Root).TrimEnd('\','/').ToLowerInvariant()
        $rootSha = [Security.Cryptography.SHA256]::Create()
        try { $rootHash = ([BitConverter]::ToString($rootSha.ComputeHash([Text.Encoding]::UTF8.GetBytes($rootText))).Replace('-','').ToLowerInvariant()) } finally { $rootSha.Dispose() }
        $message = 'approve|{0}|{1}|{2}|{3}' -f $InstallVersion, $rootHash, $IssuedAt, $Nonce
        $hmac = New-Object Security.Cryptography.HMACSHA256
        try {
            $hmac.Key = $key
            return ([BitConverter]::ToString($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($message))).Replace('-','').ToLowerInvariant())
        } finally { $hmac.Dispose(); [Array]::Clear($key, 0, $key.Length) }
    } finally { if ($secret) { [Array]::Clear($secret, 0, $secret.Length) } }
}

function Confirm-InstallerAccess {
    Write-Host 'This installer requires the current 6-digit Authy code from the administrator.'
    Write-Host 'Codes rotate every 30 seconds. Keep automatic date/time enabled.'
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            $secure = Read-Host 'Enter the current 6-digit Authy installer code' -AsSecureString
            $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            try {
                $plain = ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)).Trim()
            } finally {
                if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
            }
            $accepted = Test-InstallerTotpCode -Code $plain
            if ($accepted) {
                # Preserve the accepted code only long enough for INSTALL_RECEIPT.ps1
                # to validate and write the machine-bound receipt. v24.6.142 cleared
                # $plain before assigning it, so every valid Windows code produced an
                # empty child-process value and receipt creation always failed.
                # Create a short-lived package-bound approval ticket now.
                # The final receipt is written only after mandatory setup succeeds,
                # but it does not depend on the six-digit TOTP still being current.
                $script:InstallApprovalIssued = [DateTime]::UtcNow.ToString('o')
                $script:InstallApprovalNonce = [Guid]::NewGuid().ToString('N')
                $script:InstallApprovalSignature = Get-InstallerApprovalSignature -IssuedAt $script:InstallApprovalIssued -Nonce $script:InstallApprovalNonce
                $plain = $null
                Write-Host 'Installer access granted.'
                return $true
            }
            $plain = $null
        } catch {
            Write-Host "Installer access check failed: $($_.Exception.Message)"
            return $false
        }
        $remaining = 3 - $attempt
        if ($remaining -gt 0) { Write-Host "Incorrect or expired code. $remaining attempt(s) remaining." }
    }
    return $false
}

if (-not (Confirm-InstallerAccess)) {
    Write-Host 'Access denied. Installation was not started.'
    try { Add-Content -LiteralPath $Log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Installer access denied." -Encoding UTF8 } catch {}
    exit 13
}

$ReceiptScript = Join-Path $Root 'INSTALL_RECEIPT.ps1'
if (-not (Test-Path -LiteralPath $ReceiptScript)) {
    Write-Host 'Access granted, but INSTALL_RECEIPT.ps1 is missing. Re-extract the ZIP and run INSTALL.bat again.'
    $script:InstallApprovalIssued = $null
    $script:InstallApprovalNonce = $null
    $script:InstallApprovalSignature = $null
    exit 13
}
# The code is validated here, but the machine/package receipt is deliberately
# finalized only after every mandatory dependency step succeeds. A failed or
# partial install must never become launch-authorized.
$script:InstallerAccessApproved = $true

function Run-Logged {
    param([string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory = $Root)
    Write-Step "    Running: $FilePath $($Arguments -join ' ')"
    $oldLocation = Get-Location
    try {
        Set-Location -LiteralPath $WorkingDirectory
        $output = & $FilePath @Arguments 2>&1
        $rc = $LASTEXITCODE
        if ($null -eq $rc) { $rc = 0 }
        if ($output) {
            $output | ForEach-Object {
                Write-Host "    $_"
                Add-Content -LiteralPath $Log -Value "    $_" -Encoding UTF8
            }
        }
        return [int]$rc
    } catch {
        Write-Step "    ERROR launching ${FilePath}: $($_.Exception.Message)"
        return 999
    } finally {
        Set-Location $oldLocation
    }
}

function Get-FirstExistingFile {
    param([string[]]$Paths)
    foreach ($p in $Paths) {
        if ($p -and (Test-Path -LiteralPath $p)) { return $p }
    }
    return $null
}

function Add-PathFront {
    param([string]$Dir)
    if ($Dir -and (Test-Path -LiteralPath $Dir)) {
        $env:PATH = "$Dir;$env:PATH"
    }
}

function Create-Shortcut {
    param([string]$Phase)
    Write-Step "[Shortcut:$Phase] Creating Desktop shortcut..."
    try {
        $desktop = [Environment]::GetFolderPath('Desktop')
        if (-not $desktop -or -not (Test-Path -LiteralPath $desktop)) {
            $desktop = Join-Path $env:USERPROFILE 'Desktop'
        }
        if (-not (Test-Path -LiteralPath $desktop)) {
            New-Item -ItemType Directory -Path $desktop -Force | Out-Null
        }
        $target = Join-Path $Root 'CV Studio.bat'
        $icon = Join-Path $Root 'cv_studio.ico'
        $linkPath = Join-Path $desktop 'CV Studio.lnk'
        $ws = New-Object -ComObject WScript.Shell
        $s = $ws.CreateShortcut($linkPath)
        $s.TargetPath = $target
        $s.WorkingDirectory = $Root
        if (Test-Path -LiteralPath $icon) { $s.IconLocation = $icon }
        $s.Description = 'The 郭 Lab - CV Studio'
        $s.Save()
        if (Test-Path -LiteralPath $linkPath) {
            Write-Step "    Shortcut ready: $linkPath"
            return $true
        }
        Write-Step "    WARNING: Shortcut was not created at expected path: $linkPath"
    } catch {
        Write-Step "    WARNING: Shortcut creation failed: $($_.Exception.Message)"
    }
    try {
        $fallback = Join-Path ([Environment]::GetFolderPath('Desktop')) 'CV Studio Launcher.bat'
        Set-Content -LiteralPath $fallback -Value "@echo off`r`ncd /d `"$Root`"`r`ncall `"$Root`CV Studio.bat`"`r`n" -Encoding ASCII
        Write-Step "    Fallback launcher created: $fallback"
    } catch {
        Write-Step "    WARNING: Fallback launcher also failed: $($_.Exception.Message)"
    }
    return $false
}

$script:UpdateStateDir = Join-Path $env:LOCALAPPDATA 'TheGuoLab\CVStudio'
$script:UpdateStatePath = Join-Path $script:UpdateStateDir 'update_state.json'
$script:GlobalReceiptPath = Join-Path $script:UpdateStateDir 'install_receipt.json'
$script:RollbackContext = $null

function Normalize-InstallRoot {
    param([string]$Value)
    if (-not $Value) { return '' }
    try { return ([IO.Path]::GetFullPath($Value)).TrimEnd('\','/').ToLowerInvariant() } catch { return ([string]$Value).TrimEnd('\','/').ToLowerInvariant() }
}

function Get-DesktopCvStudioShortcutPath {
    $desktop = [Environment]::GetFolderPath('Desktop')
    if (-not $desktop) { $desktop = Join-Path $env:USERPROFILE 'Desktop' }
    return (Join-Path $desktop 'CV Studio.lnk')
}

function Get-ExistingCvStudioRoot {
    try {
        $link = Get-DesktopCvStudioShortcutPath
        if (Test-Path -LiteralPath $link) {
            $ws = New-Object -ComObject WScript.Shell
            $shortcut = $ws.CreateShortcut($link)
            $target = [string]$shortcut.TargetPath
            if ($target -and (Split-Path -Leaf $target) -ieq 'CV Studio.bat') {
                $candidate = Split-Path -Parent $target
                if (Test-Path -LiteralPath (Join-Path $candidate 'INSTALL_RECEIPT.ps1')) { return $candidate }
            }
        }
    } catch {}
    try {
        if (Test-Path -LiteralPath $script:UpdateStatePath) {
            $state = Get-Content -LiteralPath $script:UpdateStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
            $candidate = [string]$state.current_root
            if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate 'INSTALL_RECEIPT.ps1'))) { return $candidate }
        }
    } catch {}
    return ''
}

function Get-RootHashText {
    param([string]$Value)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes((Normalize-InstallRoot $Value)))).Replace('-','').ToLowerInvariant()) } finally { $sha.Dispose() }
}

function Backup-InstallReceipt {
    param([string]$ForRoot)
    if (-not $ForRoot -or -not (Test-Path -LiteralPath $script:GlobalReceiptPath -PathType Leaf)) { return '' }
    try {
        $rollbackDir = Join-Path $script:UpdateStateDir 'rollback_receipts'
        New-Item -ItemType Directory -Path $rollbackDir -Force | Out-Null
        $hash = Get-RootHashText $ForRoot
        $dest = Join-Path $rollbackDir ("receipt_{0}.json" -f $hash.Substring(0,24))
        Copy-Item -LiteralPath $script:GlobalReceiptPath -Destination $dest -Force
        return $dest
    } catch {
        Write-Step "    WARNING: Could not preserve the existing signed install receipt: $($_.Exception.Message)"
        return ''
    }
}

function Initialize-UpdateRollbackState {
    New-Item -ItemType Directory -Path $script:UpdateStateDir -Force | Out-Null
    $previousRoot = Get-ExistingCvStudioRoot
    if ((Normalize-InstallRoot $previousRoot) -eq (Normalize-InstallRoot $Root)) { $previousRoot = '' }
    $previousReceipt = Backup-InstallReceipt -ForRoot $previousRoot
    $previousVersion = ''
    try {
        if ($previousReceipt) { $previousVersion = [string](Get-Content -LiteralPath $previousReceipt -Raw -Encoding UTF8 | ConvertFrom-Json).version }
    } catch {}
    return [pscustomobject]@{
        PreviousRoot = $previousRoot
        PreviousVersion = $previousVersion
        PreviousReceipt = $previousReceipt
    }
}

function Restore-PreservedPreviousReceipt {
    param($Context)
    try {
        if ($Context -and $Context.PreviousReceipt -and (Test-Path -LiteralPath $Context.PreviousReceipt)) {
            Copy-Item -LiteralPath $Context.PreviousReceipt -Destination $script:GlobalReceiptPath -Force
            return $true
        }
        if (Test-Path -LiteralPath $script:GlobalReceiptPath) { Remove-Item -LiteralPath $script:GlobalReceiptPath -Force -ErrorAction SilentlyContinue }
    } catch {}
    return $false
}

function Get-FreeCvStudioSmokePort {
    $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, 0)
    try { $listener.Start(); return ([Net.IPEndPoint]$listener.LocalEndpoint).Port } finally { try { $listener.Stop() } catch {} }
}

function Invoke-CvStudioInstallHealthCheck {
    Write-Blank
    Write-Step '[Health] Starting the new release on a temporary loopback port...'
    $port = Get-FreeCvStudioSmokePort
    $process = $null
    $startedAt = [DateTime]::UtcNow
    $report = [ordered]@{
        ok = $false; version = $InstallVersion; root = $Root.TrimEnd('\'); port = $port
        started_at = $startedAt.ToString('o'); completed_at = ''; checks = [ordered]@{}; error = ''
    }
    $oldSmoke = $env:CVSTUDIO_OWNER_BUILD_SMOKE
    $oldPort = $env:CVSTUDIO_OWNER_BUILD_SMOKE_PORT
    try {
        $env:CVSTUDIO_OWNER_BUILD_SMOKE = '1'
        $env:CVSTUDIO_OWNER_BUILD_SMOKE_PORT = [string]$port
        if ($script:IsProtectedPackage) {
            $process = Start-Process -FilePath $script:ProtectedNativeExe -WorkingDirectory $Root -WindowStyle Hidden -PassThru
        } else {
            $appPath = Join-Path $Root 'app.py'
            $process = Start-Process -FilePath $script:PythonCmd -ArgumentList @(('"{0}"' -f $appPath)) -WorkingDirectory $Root -WindowStyle Hidden -PassThru
        }
    } catch {
        $report.error = "Could not start health-check runtime: $($_.Exception.Message)"
    } finally {
        if ($null -eq $oldSmoke) { Remove-Item Env:CVSTUDIO_OWNER_BUILD_SMOKE -ErrorAction SilentlyContinue } else { $env:CVSTUDIO_OWNER_BUILD_SMOKE = $oldSmoke }
        if ($null -eq $oldPort) { Remove-Item Env:CVSTUDIO_OWNER_BUILD_SMOKE_PORT -ErrorAction SilentlyContinue } else { $env:CVSTUDIO_OWNER_BUILD_SMOKE_PORT = $oldPort }
    }

    if ($process) {
        $deadline = (Get-Date).AddSeconds(75)
        while ((Get-Date) -lt $deadline) {
            try {
                $headers = @{ 'Cache-Control'='no-cache'; 'X-CV-Studio-Request-ID'=('installer-' + [guid]::NewGuid().ToString('N').Substring(0,16)) }
                $status = Invoke-RestMethod -Uri ("http://localhost:{0}/status" -f $port) -Headers $headers -Method Get -TimeoutSec 4
                $instance = Invoke-RestMethod -Uri ("http://localhost:{0}/instance" -f $port) -Headers $headers -Method Get -TimeoutSec 4
                $diag = Invoke-RestMethod -Uri ("http://localhost:{0}/diagnostics/runtime" -f $port) -Headers $headers -Method Get -TimeoutSec 8
                $report.checks.status = [bool]($status.healthy -and [string]$status.version -eq $InstallVersion)
                $report.checks.instance = [bool]([string]$instance.version -eq $InstallVersion -and (Normalize-InstallRoot ([string]$instance.root)) -eq (Normalize-InstallRoot $Root))
                $report.checks.diagnostics = [bool]($diag.ok -and [string]$diag.version -eq $InstallVersion -and $diag.install_receipt.valid)
                $report.checks.request_id = [bool]([string]$diag.request_id)
                $report.ok = [bool]($report.checks.status -and $report.checks.instance -and $report.checks.diagnostics -and $report.checks.request_id)
                if ($report.ok) { break }
            } catch {
                $report.error = $_.Exception.Message
            }
            Start-Sleep -Milliseconds 400
            try { if ($process.HasExited) { break } } catch {}
        }
    }
    try { if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue } } catch {}
    $report.completed_at = [DateTime]::UtcNow.ToString('o')
    try { $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Root 'install_health_report.json') -Encoding UTF8 } catch {}
    if ($report.ok) { Write-Step '    New release health checks passed.' } else { Write-Step "    ERROR: New release health checks failed: $($report.error)" }
    return [pscustomobject]$report
}

function Save-CvStudioUpdateState {
    param($Context, $Health)
    try {
        New-Item -ItemType Directory -Path $script:UpdateStateDir -Force | Out-Null
        $currentReceipt = Backup-InstallReceipt -ForRoot $Root
        $state = [ordered]@{
            schema = 1; product = 'TheGuoLab-CVStudio'; updated_at = [DateTime]::UtcNow.ToString('o')
            current_root = $Root.TrimEnd('\'); current_version = $InstallVersion; current_receipt = $currentReceipt
            previous_root = if ($Context) { [string]$Context.PreviousRoot } else { '' }
            previous_version = if ($Context) { [string]$Context.PreviousVersion } else { '' }
            previous_receipt = if ($Context) { [string]$Context.PreviousReceipt } else { '' }
            health = $Health
        }
        $tmp = $script:UpdateStatePath + '.tmp'
        $state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmp -Encoding UTF8
        Move-Item -LiteralPath $tmp -Destination $script:UpdateStatePath -Force
        Write-Step "    Rollback state saved: $script:UpdateStatePath"
        return $true
    } catch {
        Write-Step "    ERROR: Could not save rollback state: $($_.Exception.Message)"
        return $false
    }
}

function Create-RestoreShortcut {
    param($Context)
    if (-not $Context -or -not $Context.PreviousRoot -or -not $Context.PreviousReceipt) { return }
    try {
        $desktop = [Environment]::GetFolderPath('Desktop')
        if (-not $desktop) { $desktop = Join-Path $env:USERPROFILE 'Desktop' }
        $linkPath = Join-Path $desktop 'Restore Previous CV Studio.lnk'
        $target = Join-Path $Root 'RESTORE_PREVIOUS.bat'
        if (-not (Test-Path -LiteralPath $target)) { return }
        $ws = New-Object -ComObject WScript.Shell
        $s = $ws.CreateShortcut($linkPath)
        $s.TargetPath = $target
        $s.WorkingDirectory = $Root
        $icon = Join-Path $Root 'cv_studio.ico'; if (Test-Path -LiteralPath $icon) { $s.IconLocation = $icon }
        $s.Description = 'Restore the previous healthy CV Studio release'
        $s.Save()
        Write-Step "    Restore shortcut ready: $linkPath"
        Write-Step "    Keep the previous CV Studio folder until you are satisfied with this release."
    } catch { Write-Step "    WARNING: Restore shortcut could not be created: $($_.Exception.Message)" }
}

function Ensure-ProgramFilesNode {
    $localNodeDir = Join-Path $Root 'node'
    $localNodeExe = Join-Path $localNodeDir 'node.exe'
    $pfNodeDir = Join-Path $env:ProgramFiles 'nodejs'
    $pfNodeExe = Join-Path $pfNodeDir 'node.exe'
    if (-not (Test-Path -LiteralPath $localNodeExe)) { return }
    if (Test-Path -LiteralPath $pfNodeExe) {
        Write-Step '    Program Files Node.js already exists - future installs can reuse it.'
        return
    }
    Write-Step '    Trying to copy portable Node.js to Program Files for future installs...'
    $tempPs = Join-Path $env:TEMP ("guolab_copy_node_pf_{0}.ps1" -f ([guid]::NewGuid().ToString('N')))
    @"
`$ErrorActionPreference = 'Stop'
`$src = '$($localNodeDir.Replace("'", "''"))'
`$dest = Join-Path `$env:ProgramFiles 'nodejs'
New-Item -ItemType Directory -Path `$dest -Force | Out-Null
Copy-Item -Path (Join-Path `$src '*') -Destination `$dest -Recurse -Force
"@ | Set-Content -LiteralPath $tempPs -Encoding UTF8
    try {
        Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$tempPs) -Verb RunAs -Wait
    } catch {
        Write-Step "    Program Files copy skipped or blocked by Windows/UAC: $($_.Exception.Message)"
    }
    Remove-Item -LiteralPath $tempPs -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $pfNodeExe) {
        Write-Step '    Copied portable Node.js to Program Files.'
        Add-PathFront $pfNodeDir
    } else {
        Write-Step '    Program Files copy skipped or blocked. Local portable Node.js will still be used.'
    }
}

function Invoke-VerifiedNodeDownload {
    param([string]$FileName, [string]$OutFile)
    $base = 'https://nodejs.org/dist/v20.14.0'
    # Pinned from Node.js v20.14.0 official SHASUMS256.txt. Do not trust a
    # checksum downloaded from the same origin at installation time: an
    # upstream/CDN compromise could replace both the package and manifest.
    $expectedByFile = @{
        'node-v20.14.0-x64.msi' = '4235f05b99ae5dabadb5c10c124a0f7f7d4223e52df0857e4c4462b13f19c40e'
        'node-v20.14.0-win-x64.zip' = '04cc745e572ff53a6b9ce5b573e4a18303e32351e60c278a93b84466b60d532f'
    }
    $expected = [string]$expectedByFile[$FileName]
    if ([string]::IsNullOrWhiteSpace($expected)) {
        Write-Step "    Refusing unapproved Node download: $FileName"
        return $false
    }
    try {
        $downloaded = $false
        for ($attempt = 1; $attempt -le 3 -and -not $downloaded; $attempt++) {
            try {
                Invoke-WebRequest -Uri ($base + '/' + $FileName) -OutFile $OutFile -UseBasicParsing -TimeoutSec 180
                $downloaded = $true
            } catch {
                Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
                if ($attempt -ge 3) { throw }
                Start-Sleep -Seconds (2 * $attempt)
            }
        }
        $actual = (Get-FileHash -LiteralPath $OutFile -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) { throw "Node download SHA-256 mismatch for $FileName" }
        return $true
    } catch {
        Write-Step "    Verified Node download failed: $($_.Exception.Message)"
        Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
        return $false
    }
}

function Check-Python {
    Write-Step '[1/7] Checking Python (source builds only)...'
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { $cmd = Get-Command py -ErrorAction SilentlyContinue }
    if ($cmd) {
        $exe = $cmd.Source
        Write-Step "    Python command found: $exe"
        $script:PythonCmd = if ((Split-Path -Leaf $exe) -ieq 'py.exe') { 'py' } else { 'python' }
        return $true
    }
    Write-Step '    ERROR: Python is required for an owner/source build but is not installed.'
    Write-Step '    Install Python 3.12 from python.org, then re-run INSTALL.bat.'
    return $false
}

function Check-Node {
    Write-Blank
    Write-Step '[2/7] Checking Node.js...'
    $pf86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    $candidates = @(
        (Get-Command node -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        (Join-Path $env:ProgramFiles 'nodejs\node.exe'),
        $(if ($pf86) { Join-Path $pf86 'nodejs\node.exe' }),
        (Join-Path $env:APPDATA 'nvm\current\node.exe'),
        (Join-Path $Root 'node\node.exe')
    ) | Where-Object { $_ }
    $nodeExe = Get-FirstExistingFile $candidates
    if ($nodeExe) {
        Add-PathFront (Split-Path -Parent $nodeExe)
        Write-Step "    Node.js found: $nodeExe"
        if ($nodeExe -like "$Root*") { Ensure-ProgramFilesNode }
        return $true
    }
    Write-Step '    Node.js not found. Downloading installer (~30MB)...'
    $msi = Join-Path $env:TEMP 'guolab_node_setup.msi'
    try {
        if (-not (Invoke-VerifiedNodeDownload -FileName 'node-v20.14.0-x64.msi' -OutFile $msi)) { throw 'Verified Node MSI download failed' }
        Write-Step '    Installing Node.js to Program Files (UAC/admin may prompt)...'
        Start-Process -FilePath 'msiexec.exe' -ArgumentList @('/i',$msi,'/quiet','/norestart','ADDLOCAL=ALL') -Verb RunAs -Wait
        Remove-Item -LiteralPath $msi -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
        $env:PATH = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';' + $env:PATH
    } catch {
        Write-Step "    MSI install failed or was cancelled: $($_.Exception.Message)"
    }
    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($cmd) { Add-PathFront (Split-Path -Parent $cmd.Source); Write-Step "    Node.js ready: $($cmd.Source)"; return $true }
    Write-Step '    Trying portable Node.js fallback...'
    $zip = Join-Path $env:TEMP 'guolab_node.zip'
    $tmp = Join-Path $env:TEMP ('guolab_node_tmp_' + [guid]::NewGuid().ToString('N'))
    try {
        if (-not (Invoke-VerifiedNodeDownload -FileName 'node-v20.14.0-win-x64.zip' -OutFile $zip)) { throw 'Verified portable Node download failed' }
        Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
        Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
        $nodeFolder = Get-ChildItem -LiteralPath $tmp -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'node.exe') } | Select-Object -First 1
        if ($nodeFolder) {
            $dest = Join-Path $Root 'node'
            if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force -ErrorAction SilentlyContinue }
            Copy-Item -LiteralPath $nodeFolder.FullName -Destination $dest -Recurse -Force
            Add-PathFront $dest
            Write-Step '    Portable Node.js ready.'
            Ensure-ProgramFilesNode
            return $true
        }
    } catch {
        Write-Step "    Portable Node fallback failed: $($_.Exception.Message)"
    } finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Step '    ERROR: Could not install Node.js. Install from https://nodejs.org/ and re-run.'
    return $false
}

function Install-PythonPackages {
    Write-Blank
    Write-Step '[3/7] Installing Python packages...'
    Write-Step '    This may take a minute. Please wait.'
    $requirements = Join-Path $Root 'requirements.txt'
    $rc = Run-Logged -FilePath $script:PythonCmd -Arguments @('-m','pip','install','-r',$requirements)
    if ($rc -ne 0) {
        Write-Step '    ERROR: pip install failed. Trying python -m pip fallback...'
        $rc = Run-Logged -FilePath 'python' -Arguments @('-m','pip','install','-r',$requirements)
    }
    if ($rc -ne 0) { Write-Step '    ERROR: Python package install failed.'; return $false }
    Write-Step '    Checking optional pywin32 for local OneNote desktop reading...'
    $pywinCheckRc = Run-Logged -FilePath $script:PythonCmd -Arguments @('-c','import pythoncom, win32com.client')
    if ($pywinCheckRc -eq 0) {
        Write-Step '    pywin32 ready.'
    } else {
        Write-Step '    pywin32 not found. Installing optional desktop OneNote dependency...'
        $pywinRc = Run-Logged -FilePath $script:PythonCmd -Arguments @('-m','pip','install','pywin32')
        if ($pywinRc -ne 0) {
            Write-Step '    WARNING: pywin32 install failed. Web/synced OneNote and manual paste still work; desktop-only OneNote reading may be unavailable.'
        } else {
            $pywinVerifyRc = Run-Logged -FilePath $script:PythonCmd -Arguments @('-c','import pythoncom, win32com.client')
            if ($pywinVerifyRc -eq 0) {
                Write-Step '    pywin32 installed and verified.'
            } else {
                Write-Step '    WARNING: pywin32 installed but could not be imported yet. Restart Windows or run INSTALL.bat again if desktop OneNote reading is unavailable.'
            }
        }
    }
    $stampDir = Join-Path $env:APPDATA 'GUOLabCVStudio'
    New-Item -ItemType Directory -Path $stampDir -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $stampDir '.deps_ok') -Value 'v24.6.221-bundled-pdfium-ocr' -Encoding ASCII
    Write-Step '    Python packages ready.'
    return $true
}

function Get-AntiwordCandidates {
    $pf86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    $antiHome = [Environment]::GetEnvironmentVariable('ANTIWORDHOME','Machine')
    if (-not $antiHome) { $antiHome = [Environment]::GetEnvironmentVariable('ANTIWORDHOME','User') }
    $roots = @(
        (Join-Path $Root 'vendor\antiword'),
        (Join-Path $Root 'antiword'),
        (Join-Path $Root 'third_party\antiword'),
        (Join-Path $env:ProgramFiles 'Antiword'),
        (Join-Path $env:ProgramFiles 'antiword'),
        $(if ($pf86) { Join-Path $pf86 'Antiword' }),
        $(if ($pf86) { Join-Path $pf86 'antiword' }),
        'C:\antiword',
        $antiHome
    ) | Where-Object { $_ }
    $paths = @()
    foreach ($r in $roots) {
        $paths += (Join-Path $r 'antiword.exe')
        $paths += (Join-Path $r 'bin\antiword.exe')
        $paths += (Join-Path $r 'bin\x64\antiword.exe')
        $paths += (Join-Path $r 'bin\i386\antiword.exe')
    }
    $cmd1 = Get-Command antiword -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue
    $cmd2 = Get-Command antiword.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue
    if ($cmd1) { $paths += $cmd1 }
    if ($cmd2) { $paths += $cmd2 }
    foreach ($r in $roots) {
        if (Test-Path -LiteralPath $r) {
            try {
                $paths += @(Get-ChildItem -LiteralPath $r -Recurse -File -Filter 'antiword.exe' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
            } catch {}
        }
    }
    $seen = @{}
    foreach ($p in $paths) {
        if (-not $p) { continue }
        $key = $p.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true
        if (Test-Path -LiteralPath $p) { $p }
    }
}

function Find-AntiwordPackageSource {
    $packages = @(
        (Join-Path $Root 'antiword.zip'),
        (Join-Path $Root 'vendor\antiword.zip'),
        (Join-Path $Root 'vendor\antiword\antiword.zip'),
        (Join-Path $Root 'third_party\antiword.zip')
    )
    foreach ($zip in $packages) {
        if (Test-Path -LiteralPath $zip) { return @{ Type='Zip'; Path=$zip } }
    }
    $folders = @(
        (Join-Path $Root 'vendor\antiword'),
        (Join-Path $Root 'antiword'),
        (Join-Path $Root 'third_party\antiword')
    )
    foreach ($folder in $folders) {
        if (Test-Path -LiteralPath (Join-Path $folder 'antiword.exe')) { return @{ Type='Folder'; Path=$folder } }
    }
    return $null
}

function Install-AntiwordFolderToProgramFiles {
    param([string]$SourceFolder)
    if (-not $SourceFolder -or -not (Test-Path -LiteralPath (Join-Path $SourceFolder 'antiword.exe'))) { return $false }
    $resourceDir = Join-Path $SourceFolder 'Resources'
    if (-not (Test-Path -LiteralPath $resourceDir)) {
        Write-Step '    Antiword folder has no Resources folder; copying full folder anyway and relying on runtime quality fallback.'
    }
    $dest = Join-Path $env:ProgramFiles 'Antiword'
    Write-Step "    Trying to install Antiword to Program Files: $dest"
    $tempPs = Join-Path $env:TEMP ("guolab_install_antiword_{0}.ps1" -f ([guid]::NewGuid().ToString('N')))
    @"
`$ErrorActionPreference = 'Stop'
`$src = '$($SourceFolder.Replace("'", "''"))'
`$dest = Join-Path `$env:ProgramFiles 'Antiword'
New-Item -ItemType Directory -Path `$dest -Force | Out-Null
Copy-Item -Path (Join-Path `$src '*') -Destination `$dest -Recurse -Force
[Environment]::SetEnvironmentVariable('ANTIWORDHOME', `$dest, 'Machine')
`$machinePath = [Environment]::GetEnvironmentVariable('Path','Machine')
if (`$machinePath -notlike "*`$dest*") {
    [Environment]::SetEnvironmentVariable('Path', (`$machinePath.TrimEnd(';') + ';' + `$dest), 'Machine')
}
"@ | Set-Content -LiteralPath $tempPs -Encoding UTF8
    try {
        Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$tempPs) -Verb RunAs -Wait
    } catch {
        Write-Step "    Program Files Antiword install skipped or blocked by Windows/UAC: $($_.Exception.Message)"
    }
    Remove-Item -LiteralPath $tempPs -Force -ErrorAction SilentlyContinue
    $installed = Join-Path $dest 'antiword.exe'
    if (Test-Path -LiteralPath $installed) {
        Add-PathFront $dest
        $env:ANTIWORDHOME = $dest
        Write-Step "    Antiword installed/ready: $installed"
        return $true
    }
    return $false
}

function Install-AntiwordPackageRootToProgramFiles {
    param([string]$PackageRoot)
    if (-not $PackageRoot -or -not (Test-Path -LiteralPath $PackageRoot)) { return $false }
    $exe = Get-ChildItem -LiteralPath $PackageRoot -Recurse -File -Filter 'antiword.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $exe) { return $false }
    $dest = Join-Path $env:ProgramFiles 'Antiword'
    Write-Step "    Trying to install downloaded Antiword package to Program Files: $dest"
    $tempPs = Join-Path $env:TEMP ("guolab_install_antiword_pkg_{0}.ps1" -f ([guid]::NewGuid().ToString('N')))
    @"
`$ErrorActionPreference = 'Stop'
`$src = '$($PackageRoot.Replace("'", "''"))'
`$dest = Join-Path `$env:ProgramFiles 'Antiword'
New-Item -ItemType Directory -Path `$dest -Force | Out-Null
Copy-Item -Path (Join-Path `$src '*') -Destination `$dest -Recurse -Force
`$exe = Get-ChildItem -LiteralPath `$dest -Recurse -File -Filter 'antiword.exe' | Select-Object -First 1
if (`$exe) {
    # Put a convenience copy at the root if the package stores antiword.exe nested under bin/x64/etc.
    if (`$exe.FullName -ne (Join-Path `$dest 'antiword.exe')) {
        Copy-Item -LiteralPath `$exe.FullName -Destination (Join-Path `$dest 'antiword.exe') -Force
    }
}
[Environment]::SetEnvironmentVariable('ANTIWORDHOME', `$dest, 'Machine')
`$machinePath = [Environment]::GetEnvironmentVariable('Path','Machine')
if (`$machinePath -notlike "*`$dest*") {
    [Environment]::SetEnvironmentVariable('Path', (`$machinePath.TrimEnd(';') + ';' + `$dest), 'Machine')
}
"@ | Set-Content -LiteralPath $tempPs -Encoding UTF8
    try {
        Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$tempPs) -Verb RunAs -Wait
    } catch {
        Write-Step "    Program Files Antiword package install skipped or blocked by Windows/UAC: $($_.Exception.Message)"
    }
    Remove-Item -LiteralPath $tempPs -Force -ErrorAction SilentlyContinue
    $installed = Join-Path $dest 'antiword.exe'
    if (Test-Path -LiteralPath $installed) {
        Add-PathFront $dest
        $env:ANTIWORDHOME = $dest
        Write-Step "    Antiword installed/ready: $installed"
        return $true
    }
    return $false
}

function Install-AntiwordZipToProgramFiles {
    param([string]$ZipPath)
    if (-not $ZipPath -or -not (Test-Path -LiteralPath $ZipPath)) { return $false }
    $tmp = Join-Path $env:TEMP ('guolab_antiword_tmp_' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tmp -Force | Out-Null
        Expand-Archive -LiteralPath $ZipPath -DestinationPath $tmp -Force
        $exe = Get-ChildItem -LiteralPath $tmp -Recurse -File -Filter 'antiword.exe' | Select-Object -First 1
        if (-not $exe) {
            Write-Step '    WARNING: antiword.zip did not contain antiword.exe.'
            return $false
        }
        $srcFolder = Split-Path -Parent $exe.FullName
        return (Install-AntiwordFolderToProgramFiles -SourceFolder $srcFolder)
    } catch {
        Write-Step "    WARNING: Could not expand/install antiword.zip: $($_.Exception.Message)"
        return $false
    } finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Download-AntiwordPackage {
    Write-Step '    Antiword automatic internet download is disabled because no stable signed/checksummed upstream Windows artifact is available.'
    return $false
}

function Check-Antiword {
    Write-Blank
    Write-Step '[4/7] Checking Antiword for legacy .doc extraction...'

    # 1) Prefer an existing install if already available.
    $existing = @(Get-AntiwordCandidates)
    if ($existing.Count -gt 0) {
        $antiwordExe = $existing[0]
        Add-PathFront (Split-Path -Parent $antiwordExe)
        Write-Step "    Antiword found: $antiwordExe"
        return $true
    }

    # 2) If the user placed a portable antiword folder/zip beside CV Studio, install it to Program Files.
    $pkg = Find-AntiwordPackageSource
    if ($pkg) {
        Write-Step "    Local Antiword package found: $($pkg.Path)"
        $ok = $false
        if ($pkg.Type -eq 'Zip') { $ok = Install-AntiwordZipToProgramFiles -ZipPath $pkg.Path }
        if ($pkg.Type -eq 'Folder') { $ok = Install-AntiwordFolderToProgramFiles -SourceFolder $pkg.Path }
        if ($ok) { return $true }
        Write-Step '    WARNING: Local Antiword package was found but could not be installed to Program Files.'
    }

    # 3) Clean fallback. Internet auto-download is intentionally disabled.
    Write-Step '    Antiword could not be auto-installed. Native .doc extraction fallback remains active.'
    Write-Step '    This is non-fatal. Legacy .doc files still use CV Studio native extraction fallback.'
    Write-Step '    Optional manual path: C:\Program Files\Antiword\antiword.exe'
    return $true
}

function Check-Tesseract {
    Write-Step '[5/7] Checking Tesseract...'
    $pf86 = ${env:ProgramFiles(x86)}
    $paths = @(
        (Join-Path $Root 'tesseract\tesseract.exe'),
        (Join-Path $env:ProgramFiles 'Tesseract-OCR\tesseract.exe'),
        $(if ($pf86) { Join-Path $pf86 'Tesseract-OCR\tesseract.exe' }),
        (Join-Path $env:LOCALAPPDATA 'Programs\Tesseract-OCR\tesseract.exe')
    )
    $tessExe = Get-FirstExistingFile $paths
    if ($tessExe) { Add-PathFront (Split-Path -Parent $tessExe); Write-Step "    Tesseract found: $tessExe"; return $true }
    Write-Step '    WARNING: Tesseract is optional and was not found.'
    Write-Step '    Automatic unverified installer downloads are disabled. Install Tesseract manually for scanned-image OCR.'
    return $false
}

function Check-PdfOcrRenderer {
    Write-Step '[6/7] Checking PDF OCR renderer...'
    if ($script:IsProtectedPackage) {
        Write-Step '    Built-in PDFium renderer is bundled in the protected runtime.'
        Write-Step '    External Poppler is not required.'
        return $true
    }
    if ($script:PythonCmd) {
        $pdfiumRc = Run-Logged -FilePath $script:PythonCmd -Arguments @('-c','import pypdfium2')
        if ($pdfiumRc -eq 0) {
            Write-Step '    Built-in PDFium renderer is ready.'
            Write-Step '    External Poppler is not required.'
            return $true
        }
    }
    $paths = @(
        (Join-Path $Root 'poppler\Library\bin\pdfinfo.exe'),
        (Join-Path $Root 'poppler\bin\pdfinfo.exe'),
        (Join-Path $env:ProgramFiles 'poppler\Library\bin\pdfinfo.exe'),
        (Join-Path $env:ProgramFiles 'poppler\bin\pdfinfo.exe')
    )
    $cmd = Get-Command pdfinfo -ErrorAction SilentlyContinue
    if ($cmd) { $paths += $cmd.Source }
    $pdfinfo = Get-FirstExistingFile $paths
    if ($pdfinfo) { Add-PathFront (Split-Path -Parent $pdfinfo); Write-Step "    Poppler fallback found: $pdfinfo"; return $true }
    Write-Step '    WARNING: Neither the built-in PDFium package nor a Poppler fallback was found.'
    Write-Step '    Run INSTALL.bat again before using scanned-PDF OCR.'
    return $false
}

function Install-NodePackages {
    Write-Blank
    Write-Step '[7/7] Verifying Node DOCX runtime...'
    $verifyRc = Run-Logged -FilePath 'node' -Arguments @('-e', "const p=require('adm-zip/package.json');if(p.version!=='0.5.17')process.exit(2);require('adm-zip')") -WorkingDirectory $Root
    if ($verifyRc -eq 0) {
        Write-Step '    Required Node package adm-zip 0.5.17 is installed and loadable.'
        return $true
    }
    if ($script:IsProtectedPackage) {
        Write-Step '    ERROR: The protected package bundled adm-zip runtime failed verification.'
        Write-Step '    Re-extract the original protected Windows ZIP. The installer will not run npm against a protected colleague package.'
        return $false
    }
    Write-Step '    Owner/source build dependency is missing. Running pinned npm install...'
    $rc = Run-Logged -FilePath 'npm' -Arguments @('install','--ignore-scripts','--no-audit','--no-fund','--save-exact') -WorkingDirectory $Root
    if ($rc -ne 0) { Write-Step '    ERROR: npm install failed.'; return $false }
    $verifyRc = Run-Logged -FilePath 'node' -Arguments @('-e', "const p=require('adm-zip/package.json');if(p.version!=='0.5.17')process.exit(2);require('adm-zip')") -WorkingDirectory $Root
    if ($verifyRc -ne 0) { Write-Step '    ERROR: adm-zip 0.5.17 could not be loaded after npm install.'; return $false }
    Write-Step '    Node packages ready and verified.'
    return $true
}

function Refresh-IconCache {
    Write-Blank
    Write-Step '[Icon] Refreshing icon cache...'
    try {
        Remove-Item -LiteralPath (Join-Path $env:LOCALAPPDATA 'IconCache.db') -Force -ErrorAction SilentlyContinue
        Remove-Item -Path (Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Explorer\iconcache*') -Force -ErrorAction SilentlyContinue
        Remove-Item -Path (Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Explorer\thumbcache*') -Force -ErrorAction SilentlyContinue
        Start-Process -FilePath 'ie4uinit.exe' -ArgumentList '-show' -WindowStyle Hidden -ErrorAction SilentlyContinue
        Write-Step '    Icon cache refresh requested.'
    } catch { Write-Step "    WARNING: Icon refresh failed: $($_.Exception.Message)" }
}

function Add-DefenderExclusion {
    # Deliberately do not exclude the writable CV Studio directory from Defender.
    # If a false positive occurs, the owner should investigate the exact file
    # instead of weakening scanning for every future file placed in this folder.
    Write-Blank
    Write-Step '[Security] Windows Defender scanning remains enabled for this folder.'
}

Write-Host '============================================'
Write-Host "  The Guok's Lab - First Time Setup"
Write-Host '============================================'
Write-Host ''
Set-Content -LiteralPath $Log -Value "============================================`r`n$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - INSTALL_CORE.ps1 started`r`nRoot: $Root" -Encoding UTF8
Write-Step 'Installer core started.'

$ok = $true
$NativeRuntime = [bool]$script:IsProtectedPackage
if ($NativeRuntime) {
    Write-Step '[1/7] Protected native runtime detected - full Python backend installation is not required.'
} else {
    if (-not (Check-Python)) { $ok = $false }
}
if ($ok -and -not (Check-Node)) { $ok = $false }
if ($ok -and -not $NativeRuntime -and -not (Install-PythonPackages)) { $ok = $false }
if ($ok -and $NativeRuntime) { Write-Step '[3/7] Python packages are bundled in the protected runtime - skipped.' }
if ($ok) { Check-Antiword | Out-Null }
if ($ok) { Check-Tesseract | Out-Null }
if ($ok) { Check-PdfOcrRenderer | Out-Null }
if ($ok -and -not (Install-NodePackages)) { $ok = $false }

if ($ok) {
    # Preserve the currently active root and its signed receipt before this
    # release writes its own root-bound receipt. The old folder is never deleted.
    $script:RollbackContext = Initialize-UpdateRollbackState
    # Finalize this exact version/folder only after mandatory setup succeeds.
    # WriteApproved requires the short-lived HMAC ticket created immediately
    # after the user entered a valid TOTP; calling the receipt script directly
    # without that ticket is rejected.
    $env:GUOLAB_INSTALL_APPROVAL_ISSUED = [string]$script:InstallApprovalIssued
    $env:GUOLAB_INSTALL_APPROVAL_NONCE = [string]$script:InstallApprovalNonce
    $env:GUOLAB_INSTALL_APPROVAL_SIGNATURE = [string]$script:InstallApprovalSignature
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ReceiptScript -Mode WriteApproved
        if ($LASTEXITCODE -ne 0) {
            Write-Step '    ERROR: Mandatory setup succeeded, but the final machine/package receipt could not be created.'
            $ok = $false
        }
    } finally {
        Remove-Item Env:GUOLAB_INSTALL_APPROVAL_ISSUED -ErrorAction SilentlyContinue
        Remove-Item Env:GUOLAB_INSTALL_APPROVAL_NONCE -ErrorAction SilentlyContinue
        Remove-Item Env:GUOLAB_INSTALL_APPROVAL_SIGNATURE -ErrorAction SilentlyContinue
    }
}
$script:InstallApprovalIssued = $null
$script:InstallApprovalNonce = $null
$script:InstallApprovalSignature = $null

if ($ok) {
    $health = Invoke-CvStudioInstallHealthCheck
    if (-not $health.ok) {
        Restore-PreservedPreviousReceipt -Context $script:RollbackContext | Out-Null
        Write-Step '    Previous signed receipt was restored; the existing Desktop launcher was left unchanged.'
        $ok = $false
    } elseif (-not (Save-CvStudioUpdateState -Context $script:RollbackContext -Health $health)) {
        Restore-PreservedPreviousReceipt -Context $script:RollbackContext | Out-Null
        Write-Step '    Rollback state could not be committed. Previous receipt restored; launcher unchanged.'
        $ok = $false
    }
}

if ($ok) {
    Create-Shortcut -Phase 'final' | Out-Null
    Create-RestoreShortcut -Context $script:RollbackContext
    Refresh-IconCache
    Add-DefenderExclusion
}

Write-Blank
if ($ok) {
    Write-Step 'Setup Complete! Click CV Studio on your Desktop to launch.'
    exit 0
} else {
    Write-Step 'Setup failed or was incomplete. No new launch authorization was created. Review install_log.txt.'
    exit 1
}
