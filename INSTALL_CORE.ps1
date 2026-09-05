param(
    [switch]$AntiwordSelfTestOnly,
    [string]$AntiwordSelfTestStateRoot = ''
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Root.EndsWith('\')) { $Root += '\' }
$Log = Join-Path $Root 'install_log.txt'
$InstallVersion = 'v24.6.380'
$AntiwordVersion = '1.3.5'
$AntiwordRuntimeFileCount = 37
$AntiwordManifestSha256 = '7d365a89f268a2fc34f815b369474124bc6a1aac02e9b0b57e6dfd5eb5368da0'
$AntiwordExecutableSha256 = '2cbab2831854ccd5141ea328824a77cb889586db2e97129873d543a52cf3e15c'
$AntiwordFixtureSha256 = 'f430cdfe9446c4b943074d4bf804232761c284f2caa3d4125006b158d8b14af8'
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

function Get-InstallerFileSha256 {
    param([string]$Path)
    $stream = [IO.File]::OpenRead([IO.Path]::GetFullPath($Path))
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant()
    } finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

function Get-InstallerAuthenticodeSignature {
    param([string]$Path)
    # Resolve the built-in module from PSHOME. An untrusted HOME environment can
    # break normal module auto-loading and must not disable installer checks.
    $securityModule = Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1'
    Import-Module -Name $securityModule -ErrorAction Stop
    return Microsoft.PowerShell.Security\Get-AuthenticodeSignature -LiteralPath $Path
}


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

$ReceiptScript = Join-Path $Root 'INSTALL_RECEIPT.ps1'
if (-not $AntiwordSelfTestOnly) {
    if (-not (Confirm-InstallerAccess)) {
        Write-Host 'Access denied. Installation was not started.'
        try { Add-Content -LiteralPath $Log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Installer access denied." -Encoding UTF8 } catch {}
        exit 13
    }
    if (-not (Test-Path -LiteralPath $ReceiptScript)) {
        Write-Host 'Access granted, but INSTALL_RECEIPT.ps1 is missing. Re-extract the ZIP and run INSTALL.bat again.'
        $script:InstallApprovalIssued = $null
        $script:InstallApprovalNonce = $null
        $script:InstallApprovalSignature = $null
        exit 13
    }
    # The code is validated here, but the machine/package receipt is
    # deliberately finalized only after every mandatory dependency step
    # succeeds. A failed or partial install must never become launch-authorized.
    $script:InstallerAccessApproved = $true
} else {
    # Dependency QA cannot issue a receipt or reach the installer main block.
    $script:InstallerAccessApproved = $false
}

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

function Repair-CvStudioStartupRegistration {
    # Preserve an existing enabled CV Studio startup preference when a release
    # is installed from a new folder. Only the product-owned Run value and the
    # exact historical wscript + START_HIDDEN.vbs shape are eligible.
    $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    $valueName = 'GUOLabCVStudio'
    try {
        $current = [string](Get-ItemPropertyValue -LiteralPath $runKey -Name $valueName -ErrorAction Stop)
    } catch {
        return $true
    }
    $expected = 'wscript.exe "{0}"' -f (Join-Path $Root 'START_HIDDEN.vbs')
    if ($current.Trim() -ieq $expected) { return $true }
    if ($current -notmatch '(?i)^\s*(?:"(?:[^"\r\n]*[\\/])?wscript(?:\.exe)?"|(?:[^\s"\r\n]*[\\/])?wscript(?:\.exe)?)\s+"[^"\r\n]+[\\/]START_HIDDEN\.vbs"\s*$') {
        Write-Step '    WARNING: The Windows startup value is not a recognized CV Studio command and was left unchanged.'
        return $true
    }
    try {
        Set-ItemProperty -LiteralPath $runKey -Name $valueName -Value $expected -Type String -ErrorAction Stop
        Write-Step "    Windows startup location updated to this CV Studio folder."
        return $true
    } catch {
        Write-Step "    WARNING: Windows startup location could not be updated: $($_.Exception.Message)"
        return $false
    }
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
                $diag = Invoke-RestMethod -Uri ("http://localhost:{0}/diagnostics/runtime" -f $port) -Headers $headers -Method Get -TimeoutSec 15
                $report.checks.status = [bool]($status.healthy -and [string]$status.version -eq $InstallVersion)
                $report.checks.instance = [bool]([string]$instance.version -eq $InstallVersion -and (Normalize-InstallRoot ([string]$instance.root)) -eq (Normalize-InstallRoot $Root))
                $report.checks.diagnostics = [bool]($diag.ok -and [string]$diag.version -eq $InstallVersion -and $diag.install_receipt.valid)
                $report.checks.request_id = [bool]([string]$diag.request_id)
                $report.checks.antiword = [bool](
                    $diag.dependencies.antiword -and
                    $diag.dependencies.antiword_health.available -and
                    $diag.dependencies.antiword_health.trusted -and
                    $diag.dependencies.antiword_health.functional
                )
                $report.ok = [bool](
                    $report.checks.status -and
                    $report.checks.instance -and
                    $report.checks.diagnostics -and
                    $report.checks.request_id -and
                    $report.checks.antiword
                )
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
        $actual = Get-InstallerFileSha256 -Path $OutFile
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
    Set-Content -LiteralPath (Join-Path $stampDir '.deps_ok') -Value 'v24.6.380-bundled-pdfium-ocr-antiword' -Encoding ASCII
    Write-Step '    Python packages ready.'
    return $true
}

function Get-AntiwordVendorRoot {
    $candidates = @(
        (Join-Path $Root 'vendor\antiword'),
        (Join-Path $Root 'runtime\native\vendor\antiword')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $candidate 'windows-x64\SHA256SUMS') -PathType Leaf) {
            return $candidate
        }
    }
    return ''
}

function Initialize-AntiwordRuntimeLock {
    if ('CVStudioAntiwordRuntimeLock' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class CVStudioAntiwordRuntimeLock
{
    private const uint GENERIC_READ = 0x80000000;
    private const uint FILE_LIST_DIRECTORY = 0x00000001;
    private const uint FILE_READ_ATTRIBUTES = 0x00000080;
    private const uint FILE_SHARE_READ = 0x00000001;
    private const uint OPEN_EXISTING = 3;
    private const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
    private const uint FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        IntPtr securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        IntPtr templateFile);

    public static SafeFileHandle Open(string path, bool directory)
    {
        uint access = directory
            ? FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES
            : GENERIC_READ;
        uint flags = FILE_FLAG_OPEN_REPARSE_POINT;
        if (directory) { flags |= FILE_FLAG_BACKUP_SEMANTICS; }
        SafeFileHandle handle = CreateFile(
            path,
            access,
            FILE_SHARE_READ,
            IntPtr.Zero,
            OPEN_EXISTING,
            flags,
            IntPtr.Zero);
        if (handle.IsInvalid)
        {
            int error = Marshal.GetLastWin32Error();
            handle.Dispose();
            throw new Win32Exception(error, "runtime-lock-failed");
        }
        return handle;
    }
}
'@
}

function Add-AntiwordRuntimeLock {
    param(
        [System.Collections.Generic.List[Microsoft.Win32.SafeHandles.SafeFileHandle]]$Handles,
        [System.Collections.Generic.HashSet[string]]$LockedPaths,
        [string]$Path,
        [bool]$Directory
    )
    $fullPath = [IO.Path]::GetFullPath($Path)
    if (-not $LockedPaths.Add($fullPath)) { return }
    $Handles.Add([CVStudioAntiwordRuntimeLock]::Open($fullPath, $Directory))
}

function Invoke-AntiwordFunctionalCheck {
    param(
        [string]$Executable,
        [string]$FixturePath,
        [int]$TimeoutMilliseconds = 12000
    )
    $process = New-Object System.Diagnostics.Process
    $started = $false
    try {
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $Executable
        $startInfo.Arguments = '-t "' + $FixturePath + '"'
        $startInfo.WorkingDirectory = Split-Path -Parent $Executable
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $null = $startInfo.EnvironmentVariables.Remove('ANTIWORDHOME')
        # HOME is the locked executable file, so $HOME/.antiword cannot be
        # created to shadow the pinned global mapping resources.
        $startInfo.EnvironmentVariables['HOME'] = $Executable
        $process.StartInfo = $startInfo
        if (-not $process.Start()) { throw 'functional-execution-failed' }
        $started = $true
        $outputTask = $process.StandardOutput.ReadToEndAsync()
        $errorTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutMilliseconds)) {
            try { $process.Kill() } catch {}
            try { $null = $process.WaitForExit(2000) } catch {}
            throw 'functional-execution-timeout'
        }
        $output = $outputTask.Result
        $errorOutput = $errorTask.Result
        return @{
            ExitCode = [int]$process.ExitCode
            Output = [string]($output + $errorOutput)
        }
    } catch {
        if ($started) {
            try {
                if (-not $process.HasExited) {
                    $process.Kill()
                    $null = $process.WaitForExit(2000)
                }
            } catch {}
        }
        throw
    } finally {
        $process.Dispose()
    }
}

function Test-AntiwordRuntime {
    param(
        [string]$RuntimeRoot,
        [string]$FixturePath,
        [scriptblock]$ProtectedIntervalProbe = $null,
        [int]$FunctionalTimeoutMilliseconds = 12000
    )
    $script:AntiwordFailure = ''
    $lockHandles = [System.Collections.Generic.List[Microsoft.Win32.SafeHandles.SafeFileHandle]]::new()
    $lockedPaths = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    try {
        if (-not $RuntimeRoot -or -not (Test-Path -LiteralPath $RuntimeRoot -PathType Container)) {
            throw 'runtime-missing'
        }
        Initialize-AntiwordRuntimeLock
        Add-AntiwordRuntimeLock -Handles $lockHandles -LockedPaths $lockedPaths -Path $RuntimeRoot -Directory $true
        if (((Get-Item -LiteralPath $RuntimeRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'runtime-link-rejected'
        }
        $manifest = Join-Path $RuntimeRoot 'SHA256SUMS'
        $exe = Join-Path $RuntimeRoot 'bin\antiword.exe'
        if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw 'manifest-missing' }
        Add-AntiwordRuntimeLock -Handles $lockHandles -LockedPaths $lockedPaths -Path $manifest -Directory $false
        if (((Get-Item -LiteralPath $manifest -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'manifest-link-rejected'
        }
        if ((Get-InstallerFileSha256 -Path $manifest) -ne $AntiwordManifestSha256) {
            throw 'manifest-integrity-failed'
        }
        if (-not (Test-Path -LiteralPath $FixturePath -PathType Leaf)) { throw 'functional-fixture-missing' }

        $expected = @{}
        foreach ($line in @(Get-Content -LiteralPath $manifest -Encoding UTF8)) {
            if ($line -notmatch '^([0-9a-fA-F]{64})  ([^\r\n]+)$') { throw 'manifest-invalid' }
            $relative = [string]$Matches[2]
            if ($relative.StartsWith('/') -or $relative.Contains('..') -or -not ($relative.StartsWith('bin/') -or $relative.StartsWith('share/'))) {
                throw 'manifest-path-invalid'
            }
            if ($expected.ContainsKey($relative)) { throw 'manifest-duplicate-path' }
            $expected[$relative] = ([string]$Matches[1]).ToLowerInvariant()
        }
        if ($expected.Count -ne $AntiwordRuntimeFileCount) { throw 'manifest-file-count-invalid' }

        $directories = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        $null = $directories.Add((Join-Path $RuntimeRoot 'bin'))
        $null = $directories.Add((Join-Path $RuntimeRoot 'share'))
        $null = $directories.Add((Split-Path -Parent $FixturePath))
        foreach ($relative in $expected.Keys) {
            $parent = Split-Path -Parent (Join-Path $RuntimeRoot ($relative.Replace('/','\')))
            while ($parent -and -not $parent.Equals($RuntimeRoot, [StringComparison]::OrdinalIgnoreCase)) {
                $null = $directories.Add($parent)
                $parent = Split-Path -Parent $parent
            }
        }
        foreach ($directory in @($directories | Sort-Object { ([IO.Path]::GetFullPath($_)).Length })) {
            Add-AntiwordRuntimeLock -Handles $lockHandles -LockedPaths $lockedPaths -Path $directory -Directory $true
        }
        Add-AntiwordRuntimeLock -Handles $lockHandles -LockedPaths $lockedPaths -Path $FixturePath -Directory $false
        if (((Get-Item -LiteralPath $FixturePath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'functional-fixture-link-rejected'
        }
        if ((Get-InstallerFileSha256 -Path $FixturePath) -ne $AntiwordFixtureSha256) {
            throw 'functional-fixture-integrity-failed'
        }
        foreach ($relative in @($expected.Keys | Sort-Object)) {
            $path = Join-Path $RuntimeRoot ($relative.Replace('/','\'))
            Add-AntiwordRuntimeLock -Handles $lockHandles -LockedPaths $lockedPaths -Path $path -Directory $false
        }

        $rootFull = [IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\') + '\'
        $actual = @{}
        foreach ($folderName in @('bin','share')) {
            $folder = Join-Path $RuntimeRoot $folderName
            if (-not (Test-Path -LiteralPath $folder -PathType Container)) { throw 'runtime-layout-invalid' }
            if (((Get-Item -LiteralPath $folder -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'runtime-link-rejected'
            }
            $pendingDirectories = [System.Collections.Generic.Stack[string]]::new()
            $pendingDirectories.Push($folder)
            while ($pendingDirectories.Count -gt 0) {
                $currentFolder = $pendingDirectories.Pop()
                foreach ($entry in @(Get-ChildItem -LiteralPath $currentFolder -Force)) {
                    if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                        throw 'runtime-link-rejected'
                    }
                    $full = [IO.Path]::GetFullPath($entry.FullName)
                    if (-not $full.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
                        throw 'runtime-path-escaped'
                    }
                    if ($entry.PSIsContainer) {
                        $pendingDirectories.Push($full)
                        continue
                    }
                    $relative = $full.Substring($rootFull.Length).Replace('\','/')
                    $actual[$relative] = $true
                }
            }
        }
        if ($actual.Count -ne $expected.Count) { throw 'runtime-file-set-invalid' }
        foreach ($relative in $expected.Keys) {
            if (-not $actual.ContainsKey($relative)) { throw 'runtime-file-set-invalid' }
            $path = Join-Path $RuntimeRoot ($relative.Replace('/','\'))
            $actualHash = Get-InstallerFileSha256 -Path $path
            if ($actualHash -ne $expected[$relative]) { throw 'runtime-integrity-failed' }
        }
        if ((Get-InstallerFileSha256 -Path $exe) -ne $AntiwordExecutableSha256) {
            throw 'executable-integrity-failed'
        }
        $signature = Get-InstallerAuthenticodeSignature -Path $exe
        if ([string]$signature.Status -ne 'NotSigned') { throw 'unexpected-authenticode-state' }

        if ($ProtectedIntervalProbe) {
            & $ProtectedIntervalProbe $exe (Join-Path $RuntimeRoot 'share\antiword\UTF-8.txt')
        }
        $functionalResult = Invoke-AntiwordFunctionalCheck -Executable $exe -FixturePath $FixturePath -TimeoutMilliseconds $FunctionalTimeoutMilliseconds
        $output = [string]$functionalResult.Output
        $exitCode = [int]$functionalResult.ExitCode
        if ($exitCode -ne 0 -or $output -notmatch 'Universal Declaration of Human Rights' -or $output -notmatch 'All people everywhere have the same human rights') {
            throw 'functional-output-failed'
        }
        return $true
    } catch {
        $failure = [string]$_.Exception.Message
        if ($AntiwordSelfTestOnly) {
            Write-Host ('Antiword runtime verification detail: ' + $failure)
        }
        if ($failure -match '^(runtime|manifest|functional|executable|unexpected-authenticode)-[a-z0-9-]+$') {
            $script:AntiwordFailure = $failure
        } else {
            $script:AntiwordFailure = 'verification-failed'
        }
        return $false
    } finally {
        for ($index = $lockHandles.Count - 1; $index -ge 0; $index--) {
            $lockHandles[$index].Dispose()
        }
    }
}

function Install-VerifiedAntiwordRuntime {
    $vendor = Get-AntiwordVendorRoot
    if (-not $vendor) {
        $script:AntiwordFailure = 'bundled-runtime-missing'
        return $false
    }
    $source = Join-Path $vendor 'windows-x64'
    $sourceFixture = Join-Path $vendor 'fixtures\UDHR-english.doc'
    if (-not (Test-AntiwordRuntime -RuntimeRoot $source -FixturePath $sourceFixture)) {
        return $false
    }

    $dependencyBase = Join-Path $env:LOCALAPPDATA ("TheGuoLab\CVStudio\dependencies\antiword\{0}" -f $AntiwordVersion)
    $destination = Join-Path $dependencyBase 'windows-x64'
    $destinationFixture = Join-Path $destination 'fixtures\UDHR-english.doc'
    if (Test-AntiwordRuntime -RuntimeRoot $destination -FixturePath $destinationFixture) {
        Write-Step '    Managed Antiword 1.3.5 is hash-verified and functional.'
        return $true
    }

    $stage = ''
    try {
        New-Item -ItemType Directory -Path $dependencyBase -Force | Out-Null
        $stage = Join-Path $dependencyBase ('windows-x64.stage.' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $stage -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $source 'bin') -Destination $stage -Recurse -Force
        Copy-Item -LiteralPath (Join-Path $source 'share') -Destination $stage -Recurse -Force
        Copy-Item -LiteralPath (Join-Path $source 'SHA256SUMS') -Destination (Join-Path $stage 'SHA256SUMS') -Force
        New-Item -ItemType Directory -Path (Join-Path $stage 'fixtures') -Force | Out-Null
        Copy-Item -LiteralPath $sourceFixture -Destination (Join-Path $stage 'fixtures\UDHR-english.doc') -Force
        if (-not (Test-AntiwordRuntime -RuntimeRoot $stage -FixturePath (Join-Path $stage 'fixtures\UDHR-english.doc'))) {
            throw ('staged-runtime-' + $script:AntiwordFailure)
        }
        if (Test-Path -LiteralPath $destination) {
            $backup = Join-Path $dependencyBase (
                'windows-x64.invalid.' +
                (Get-Date -Format 'yyyyMMddHHmmss') +
                '.' +
                [guid]::NewGuid().ToString('N')
            )
            Move-Item -LiteralPath $destination -Destination $backup -Force
        }
        Move-Item -LiteralPath $stage -Destination $destination
        if (-not (Test-AntiwordRuntime -RuntimeRoot $destination -FixturePath $destinationFixture)) {
            throw ('installed-runtime-' + $script:AntiwordFailure)
        }
        Write-Step '    Managed Antiword 1.3.5 was repaired from the pinned bundled runtime.'
        return $true
    } catch {
        $failure = [string]$_.Exception.Message
        if ($failure -match '^(staged-runtime|installed-runtime)-[a-z0-9-]+$') {
            $script:AntiwordFailure = $failure
        } else {
            $script:AntiwordFailure = 'install-or-repair-failed'
        }
        return $false
    } finally {
        if ($stage -and (Test-Path -LiteralPath $stage)) {
            Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Check-Antiword {
    Write-Blank
    Write-Step '[4/7] Installing and verifying mandatory Antiword for legacy .doc extraction...'
    if (Install-VerifiedAntiwordRuntime) {
        Write-Step '    Antiword trust: exact SHA-256 allowlist (upstream binary is unsigned).'
        Write-Step '    Antiword functional test: genuine legacy Word .doc passed.'
        return $true
    }
    Write-Step ("    ERROR: Mandatory Antiword verification failed ({0})." -f $script:AntiwordFailure)
    Write-Step '    Re-extract this exact CV Studio release and run INSTALL.bat again.'
    return $false
}

function Assert-AntiwordPathProtected {
    param(
        [string]$Target,
        [string]$Replacement
    )
    $stream = $null
    $writeBlocked = $false
    try {
        $stream = [IO.File]::Open(
            $Target,
            [IO.FileMode]::Open,
            [IO.FileAccess]::ReadWrite,
            [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
        )
    } catch [IO.IOException] {
        $writeBlocked = $true
    } catch [UnauthorizedAccessException] {
        $writeBlocked = $true
    } finally {
        if ($stream) { $stream.Dispose() }
    }
    if (-not $writeBlocked) { throw 'protected-write-was-not-blocked' }

    $deleteBlocked = $false
    try {
        [IO.File]::Delete($Target)
    } catch [IO.IOException] {
        $deleteBlocked = $true
    } catch [UnauthorizedAccessException] {
        $deleteBlocked = $true
    }
    if (-not $deleteBlocked -or -not (Test-Path -LiteralPath $Target -PathType Leaf)) {
        throw 'protected-delete-was-not-blocked'
    }

    $moved = $Target + '.unexpected-move'
    $renameBlocked = $false
    try {
        [IO.File]::Move($Target, $moved)
    } catch [IO.IOException] {
        $renameBlocked = $true
    } catch [UnauthorizedAccessException] {
        $renameBlocked = $true
    }
    if (-not $renameBlocked -or -not (Test-Path -LiteralPath $Target -PathType Leaf)) {
        throw 'protected-rename-was-not-blocked'
    }

    $backup = $Target + '.unexpected-backup'
    $replaceBlocked = $false
    try {
        [IO.File]::Replace($Replacement, $Target, $backup, $true)
    } catch [IO.IOException] {
        $replaceBlocked = $true
    } catch [UnauthorizedAccessException] {
        $replaceBlocked = $true
    }
    if (-not $replaceBlocked -or -not (Test-Path -LiteralPath $Target -PathType Leaf)) {
        throw 'protected-atomic-replacement-was-not-blocked'
    }
}

function Assert-AntiwordPathReleased {
    param([string]$Target)
    # Windows can briefly retain the executable image after Process.Dispose(),
    # especially while antivirus scanning is active. Retry only this release
    # assertion for a short bounded interval; a persistent lock still fails.
    $deadline = [DateTime]::UtcNow.AddSeconds(5)
    while ($true) {
        $stream = $null
        try {
            $stream = [IO.File]::Open(
                $Target,
                [IO.FileMode]::Open,
                [IO.FileAccess]::ReadWrite,
                [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
            )
            break
        } catch [IO.IOException] {
            if ([DateTime]::UtcNow -ge $deadline) { throw }
            Start-Sleep -Milliseconds 50
        } catch [UnauthorizedAccessException] {
            if ([DateTime]::UtcNow -ge $deadline) { throw }
            Start-Sleep -Milliseconds 50
        } finally {
            if ($stream) { $stream.Dispose() }
        }
    }
    $moved = $Target + '.release-check'
    while ($true) {
        try {
            [IO.File]::Move($Target, $moved)
            break
        } catch [IO.IOException] {
            if ([DateTime]::UtcNow -ge $deadline) { throw }
            Start-Sleep -Milliseconds 50
        } catch [UnauthorizedAccessException] {
            if ([DateTime]::UtcNow -ge $deadline) { throw }
            Start-Sleep -Milliseconds 50
        }
    }
    [IO.File]::Move($moved, $Target)
}

function Invoke-AntiwordInstallerSelfTest {
    param([string]$StateRoot)
    if (-not $StateRoot) { throw 'Antiword self-test requires an explicit temporary state root.' }
    $stateFull = [IO.Path]::GetFullPath($StateRoot)
    $tempFull = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $stateLeaf = Split-Path -Leaf $stateFull
    if (
        -not $stateFull.StartsWith($tempFull, [StringComparison]::OrdinalIgnoreCase) -or
        -not $stateLeaf.StartsWith('cvstudio-antiword-installer-self-test-')
    ) {
        throw 'Antiword self-test state must be inside the operating-system temporary directory.'
    }
    if (Test-Path -LiteralPath $stateFull) {
        throw 'Antiword self-test requires a fresh, non-existent temporary state directory.'
    }
    $priorLocalAppData = $env:LOCALAPPDATA
    $priorRoot = $Root
    $priorLog = $Log
    try {
        New-Item -ItemType Directory -Path $stateFull -Force | Out-Null
        if (((Get-Item -LiteralPath $stateFull -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Antiword self-test state cannot be a reparse point.'
        }
        $env:LOCALAPPDATA = $stateFull
        $script:Log = Join-Path $stateFull 'antiword-installer-self-test.log'
        $vendor = Get-AntiwordVendorRoot
        if (-not $vendor) { throw 'bundled-runtime-missing' }
        $source = Join-Path $vendor 'windows-x64'
        $sourceFixture = Join-Path $vendor 'fixtures\UDHR-english.doc'
        if (-not (Test-AntiwordRuntime -RuntimeRoot $source -FixturePath $sourceFixture)) {
            throw ('bundled-runtime-' + $script:AntiwordFailure)
        }
        if (-not (Install-VerifiedAntiwordRuntime)) {
            throw ('initial-install-' + $script:AntiwordFailure)
        }
        $managed = Join-Path $stateFull 'TheGuoLab\CVStudio\dependencies\antiword\1.3.5\windows-x64'
        $fixture = Join-Path $managed 'fixtures\UDHR-english.doc'
        $firstHash = Get-InstallerFileSha256 -Path (Join-Path $managed 'bin\antiword.exe')
        if (-not (Install-VerifiedAntiwordRuntime)) {
            throw ('idempotent-install-' + $script:AntiwordFailure)
        }
        $secondHash = Get-InstallerFileSha256 -Path (Join-Path $managed 'bin\antiword.exe')
        if ($firstHash -ne $secondHash) { throw 'idempotent-install-changed-executable' }
        $managedExe = Join-Path $managed 'bin\antiword.exe'
        $managedResource = Join-Path $managed 'share\antiword\UTF-8.txt'
        $replacementRoot = Join-Path $stateFull 'replacement-attempts'
        New-Item -ItemType Directory -Path $replacementRoot -Force | Out-Null
        $exeReplacement = Join-Path $replacementRoot 'antiword-replacement.exe'
        $resourceReplacement = Join-Path $replacementRoot 'UTF-8-replacement.txt'
        Copy-Item -LiteralPath $managedExe -Destination $exeReplacement
        Copy-Item -LiteralPath $managedResource -Destination $resourceReplacement
        $replacementProbe = {
            param($lockedExe, $lockedResource)
            Assert-AntiwordPathProtected -Target $lockedExe -Replacement $exeReplacement
            Assert-AntiwordPathProtected -Target $lockedResource -Replacement $resourceReplacement
        }
        if (-not (Test-AntiwordRuntime -RuntimeRoot $managed -FixturePath $fixture -ProtectedIntervalProbe $replacementProbe)) {
            throw ('protected-interval-' + $script:AntiwordFailure)
        }
        Assert-AntiwordPathReleased -Target $managedExe
        Assert-AntiwordPathReleased -Target $managedResource
        if (-not (Test-AntiwordRuntime -RuntimeRoot $managed -FixturePath $fixture -FunctionalTimeoutMilliseconds 0)) {
            if ($script:AntiwordFailure -ne 'functional-execution-timeout') {
                throw ('timeout-wrong-failure-' + $script:AntiwordFailure)
            }
        } else {
            throw 'zero-timeout-functional-check-unexpectedly-completed'
        }
        Assert-AntiwordPathReleased -Target $managedExe
        Assert-AntiwordPathReleased -Target $managedResource
        if (-not (Test-AntiwordRuntime -RuntimeRoot $managed -FixturePath $fixture)) {
            throw ('post-timeout-runtime-' + $script:AntiwordFailure)
        }
        Add-Content -LiteralPath (Join-Path $managed 'share\antiword\UTF-8.txt') -Value 'self-test-corruption'
        if (Test-AntiwordRuntime -RuntimeRoot $managed -FixturePath $fixture) {
            throw 'corrupt-runtime-was-accepted'
        }
        Assert-AntiwordPathReleased -Target $managedExe
        Assert-AntiwordPathReleased -Target $managedResource
        if (-not (Install-VerifiedAntiwordRuntime)) {
            throw ('repair-' + $script:AntiwordFailure)
        }
        if (-not (Test-AntiwordRuntime -RuntimeRoot $managed -FixturePath $fixture)) {
            throw ('repaired-runtime-' + $script:AntiwordFailure)
        }
        $managedMapping = Join-Path $managed 'share\antiword'
        $externalMapping = Join-Path $stateFull 'valid-external-antiword-mapping'
        Move-Item -LiteralPath $managedMapping -Destination $externalMapping
        try {
            New-Item -ItemType Junction -Path $managedMapping -Target $externalMapping | Out-Null
            if (Test-AntiwordRuntime -RuntimeRoot $managed -FixturePath $fixture) {
                throw 'nested-runtime-junction-was-accepted'
            }
            if ($script:AntiwordFailure -ne 'runtime-link-rejected') {
                throw ('nested-runtime-junction-wrong-failure-' + $script:AntiwordFailure)
            }
        } finally {
            if (Test-Path -LiteralPath $managedMapping) {
                [IO.Directory]::Delete($managedMapping)
            }
            if (Test-Path -LiteralPath $externalMapping) {
                Move-Item -LiteralPath $externalMapping -Destination $managedMapping
            }
        }
        if (-not (Test-AntiwordRuntime -RuntimeRoot $managed -FixturePath $fixture)) {
            throw ('junction-restored-runtime-' + $script:AntiwordFailure)
        }
        $script:Root = Join-Path $stateFull 'missing-package\'
        New-Item -ItemType Directory -Path $script:Root -Force | Out-Null
        if (Install-VerifiedAntiwordRuntime) { throw 'missing-bundle-reported-success' }
        Write-Host 'Antiword installer self-test passed: verify, protected execution, blocked replacement, released timeout/failure locks, install, idempotency, corruption rejection, repair, nested reparse rejection and missing-bundle failure.'
    } finally {
        $script:Root = $priorRoot
        $script:Log = $priorLog
        if ($null -eq $priorLocalAppData) {
            Remove-Item Env:LOCALAPPDATA -ErrorAction SilentlyContinue
        } else {
            $env:LOCALAPPDATA = $priorLocalAppData
        }
    }
}

if ($AntiwordSelfTestOnly) {
    try {
        Invoke-AntiwordInstallerSelfTest -StateRoot $AntiwordSelfTestStateRoot
        exit 0
    } catch {
        Write-Host ('Antiword installer self-test failed: ' + [string]$_.Exception.Message)
        exit 1
    }
}

function Check-Tesseract {
    Write-Step '[5/7] Installing and verifying mandatory Tesseract...'
    $pf86 = ${env:ProgramFiles(x86)}
    $findTesseract = {
        $paths = @(
            (Get-Command tesseract.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
            (Join-Path $Root 'tesseract\tesseract.exe'),
            (Join-Path $env:ProgramFiles 'Tesseract-OCR\tesseract.exe'),
            $(if ($pf86) { Join-Path $pf86 'Tesseract-OCR\tesseract.exe' }),
            (Join-Path $env:LOCALAPPDATA 'Programs\Tesseract-OCR\tesseract.exe')
        ) | Where-Object { $_ }
        return Get-FirstExistingFile $paths
    }
    $tessExe = & $findTesseract
    if (-not $tessExe) {
        Write-Step '    Tesseract was not found. Installing it through the available Windows package manager...'
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        $choco = Get-Command choco.exe -ErrorAction SilentlyContinue
        try {
            if ($winget) {
                & $winget.Source install --id UB-Mannheim.TesseractOCR --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
                if ($LASTEXITCODE -ne 0) { throw "winget exited with code $LASTEXITCODE" }
            } elseif ($choco) {
                $installed = $false
                foreach ($attempt in 1..3) {
                    & $choco.Source install tesseract --version=5.5.0.20241111 --yes --no-progress
                    if ($LASTEXITCODE -eq 0) { $installed = $true; break }
                    Start-Sleep -Seconds (5 * $attempt)
                }
                if (-not $installed) { throw 'Chocolatey failed after three attempts.' }
            } else {
                throw 'Neither winget nor Chocolatey is available.'
            }
        } catch {
            Write-Step "    ERROR: Automatic Tesseract installation failed: $($_.Exception.Message)"
            Write-Step '    Install Tesseract OCR with English language data, then run INSTALL.bat again.'
            return $false
        }
        $env:PATH = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';' + $env:PATH
        $tessExe = & $findTesseract
    }
    if ($tessExe) {
        try {
            $versionOutput = (& $tessExe --version 2>&1 | Out-String)
            $languageOutput = (& $tessExe --list-langs 2>&1 | Out-String)
            if ($LASTEXITCODE -eq 0 -and $versionOutput -match '(?i)tesseract\s+v?[0-9]' -and $languageOutput -match '(?m)^eng\s*$') {
                Add-PathFront (Split-Path -Parent $tessExe)
                Write-Step "    Tesseract ready with English language data: $tessExe"
                return $true
            }
        } catch {}
        Write-Step "    ERROR: Tesseract was found but failed its version/English-language functional check: $tessExe"
        return $false
    }
    Write-Step '    ERROR: Tesseract with English language data is mandatory and was not found.'
    Write-Step '    Install Tesseract OCR with English language data, then run INSTALL.bat again.'
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
    # A fresh owner/source ZIP deliberately does not contain node_modules. Do not
    # run Node's require() probe until the package exists: its expected
    # MODULE_NOT_FOUND stack trace looks like an installation failure even though
    # the fallback npm install below succeeds. Protected packages are validated at
    # startup and always bundle this exact file, so a failed protected probe still
    # remains a visible, fail-closed packaging error.
    if (Test-Path -LiteralPath $script:ProtectedAdmZipPackage -PathType Leaf) {
        $verifyRc = Run-Logged -FilePath 'node' -Arguments @('-e', "const p=require('adm-zip/package.json');if(p.version!=='0.6.0')process.exit(2);require('adm-zip')") -WorkingDirectory $Root
        if ($verifyRc -eq 0) {
            Write-Step '    Required Node package adm-zip 0.6.0 is installed and loadable.'
            return $true
        }
    } else {
        $verifyRc = 1
    }
    if ($script:IsProtectedPackage) {
        Write-Step '    ERROR: The protected package bundled adm-zip runtime failed verification.'
        Write-Step '    Re-extract the original protected Windows ZIP. The installer will not run npm against a protected colleague package.'
        return $false
    }
    Write-Step '    Owner/source build dependency is missing. Running pinned npm install...'
    $rc = Run-Logged -FilePath 'npm' -Arguments @('install','--ignore-scripts','--no-audit','--no-fund','--save-exact') -WorkingDirectory $Root
    if ($rc -ne 0) { Write-Step '    ERROR: npm install failed.'; return $false }
    $verifyRc = Run-Logged -FilePath 'node' -Arguments @('-e', "const p=require('adm-zip/package.json');if(p.version!=='0.6.0')process.exit(2);require('adm-zip')") -WorkingDirectory $Root
    if ($verifyRc -ne 0) { Write-Step '    ERROR: adm-zip 0.6.0 could not be loaded after npm install.'; return $false }
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
if ($ok -and -not (Check-Antiword)) { $ok = $false }
if ($ok -and -not (Check-Tesseract)) { $ok = $false }
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
    Repair-CvStudioStartupRegistration | Out-Null
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
