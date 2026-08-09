param(
    [ValidateSet('Verify','Write','WriteApproved','Delete')]
    [string]$Mode = 'Verify'
)

$ErrorActionPreference = 'Stop'
$Schema = 2
$Version = 'v24.6.289'
$Product = 'TheGuoLab-CVStudio'

function Get-TotpSecret {
    [byte[]]$mask = @(147, 57, 36, 83, 116, 245, 122, 57, 165, 162, 176, 168, 249, 50, 204, 128, 45, 174, 232, 56)
    [byte[]]$masked = @(49, 16, 244, 145, 19, 123, 118, 27, 71, 171, 180, 177, 120, 122, 255, 68, 100, 150, 118, 10)
    if ($mask.Length -ne $masked.Length) { throw 'Installer verifier is invalid.' }
    [byte[]]$secret = New-Object byte[] $mask.Length
    for ($i = 0; $i -lt $mask.Length; $i++) { $secret[$i] = [byte]($mask[$i] -bxor $masked[$i]) }
    return $secret
}

function Get-TotpCode {
    param([byte[]]$Secret, [Int64]$Counter)
    [byte[]]$counterBytes = [BitConverter]::GetBytes($Counter)
    if ([BitConverter]::IsLittleEndian) { [Array]::Reverse($counterBytes) }
    $hmac = New-Object Security.Cryptography.HMACSHA1
    try {
        $hmac.Key = $Secret
        [byte[]]$digest = $hmac.ComputeHash($counterBytes)
    } finally { $hmac.Dispose() }
    $offset = $digest[$digest.Length - 1] -band 0x0F
    [Int64]$binary = (([Int64]($digest[$offset] -band 0x7F)) -shl 24) -bor
                       (([Int64]($digest[$offset + 1] -band 0xFF)) -shl 16) -bor
                       (([Int64]($digest[$offset + 2] -band 0xFF)) -shl 8) -bor
                       ([Int64]($digest[$offset + 3] -band 0xFF))
    return ([Int64]($binary % 1000000)).ToString('D6')
}

function Test-TotpCode {
    param([string]$Code)
    if ([string]::IsNullOrWhiteSpace($Code) -or $Code -notmatch '^\d{6}$') { return $false }
    [byte[]]$secret = Get-TotpSecret
    try {
        $epoch = [DateTime]::SpecifyKind([DateTime]'1970-01-01 00:00:00', [DateTimeKind]::Utc)
        [Int64]$unixSeconds = [Int64][Math]::Floor(([DateTime]::UtcNow - $epoch).TotalSeconds)
        [Int64]$counter = [Int64][Math]::Floor($unixSeconds / 30)
        foreach ($delta in @(-1, 0, 1)) {
            if ((Get-TotpCode -Secret $secret -Counter ($counter + $delta)) -eq $Code) { return $true }
        }
        return $false
    } finally { if ($secret) { [Array]::Clear($secret, 0, $secret.Length) } }
}

function Get-ReceiptSigningKey {
    [byte[]]$secret = Get-TotpSecret
    try {
        [byte[]]$suffix = [Text.Encoding]::UTF8.GetBytes('|CVStudio|install-receipt-v1')
        [byte[]]$material = New-Object byte[] ($secret.Length + $suffix.Length)
        [Array]::Copy($secret, 0, $material, 0, $secret.Length)
        [Array]::Copy($suffix, 0, $material, $secret.Length, $suffix.Length)
        $sha = [Security.Cryptography.SHA256]::Create()
        try { return $sha.ComputeHash($material) } finally { $sha.Dispose(); [Array]::Clear($material, 0, $material.Length) }
    } finally { [Array]::Clear($secret, 0, $secret.Length) }
}

function Get-MachineHash {
    $value = ''
    try { $value = [string](Get-ItemPropertyValue -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Cryptography' -Name MachineGuid -ErrorAction Stop) } catch {}
    if ([string]::IsNullOrWhiteSpace($value)) { $value = [string]$env:COMPUTERNAME }
    if ([string]::IsNullOrWhiteSpace($value)) { $value = 'unknown' }
    $source = 'windows|' + $value.Trim().ToLowerInvariant()
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($source))).Replace('-','').ToLowerInvariant()) } finally { $sha.Dispose() }
}

function Get-ReceiptPath {
    $base = [Environment]::GetFolderPath('LocalApplicationData')
    if ([string]::IsNullOrWhiteSpace($base)) { $base = Join-Path $HOME 'AppData\Local' }
    return Join-Path $base 'TheGuoLab\CVStudio\install_receipt.json'
}

function Get-PackageRootHash {
    $root = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\','/').ToLowerInvariant()
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($root))).Replace('-','').ToLowerInvariant()) } finally { $sha.Dispose() }
}

function Get-Signature {
    param([int]$ReceiptSchema, [string]$ReceiptProduct, [string]$Machine, [string]$ReceiptVersion, [string]$RootHash, [string]$IssuedAt)
    $message = '{0}|{1}|{2}|{3}|{4}|{5}' -f $ReceiptSchema, $ReceiptProduct, $Machine, $ReceiptVersion, $RootHash, $IssuedAt
    [byte[]]$key = Get-ReceiptSigningKey
    $hmac = New-Object Security.Cryptography.HMACSHA256
    try {
        $hmac.Key = $key
        return ([BitConverter]::ToString($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($message))).Replace('-','').ToLowerInvariant())
    } finally { $hmac.Dispose(); [Array]::Clear($key, 0, $key.Length) }
}

function Test-ApprovedInstallTicket {
    $issuedText = [string]$env:GUOLAB_INSTALL_APPROVAL_ISSUED
    $nonce = [string]$env:GUOLAB_INSTALL_APPROVAL_NONCE
    $received = ([string]$env:GUOLAB_INSTALL_APPROVAL_SIGNATURE).ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($issuedText) -or [string]::IsNullOrWhiteSpace($nonce) -or [string]::IsNullOrWhiteSpace($received)) { return $false }
    try {
        $issued = [DateTime]::Parse($issuedText, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
    } catch { return $false }
    $age = ([DateTime]::UtcNow - $issued).TotalSeconds
    if ($age -lt -120 -or $age -gt 7200) { return $false }
    $rootHash = Get-PackageRootHash
    $message = 'approve|{0}|{1}|{2}|{3}' -f $Version, $rootHash, $issuedText, $nonce
    [byte[]]$key = Get-ReceiptSigningKey
    $hmac = New-Object Security.Cryptography.HMACSHA256
    try {
        $hmac.Key = $key
        $expected = ([BitConverter]::ToString($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($message))).Replace('-','').ToLowerInvariant())
    } finally { $hmac.Dispose(); [Array]::Clear($key, 0, $key.Length) }
    [byte[]]$actualBytes = [Text.Encoding]::ASCII.GetBytes($received)
    [byte[]]$expectedBytes = [Text.Encoding]::ASCII.GetBytes($expected)
    if ($actualBytes.Length -ne $expectedBytes.Length) { return $false }
    $difference = 0
    for ($i = 0; $i -lt $actualBytes.Length; $i++) { $difference = $difference -bor ($actualBytes[$i] -bxor $expectedBytes[$i]) }
    return ($difference -eq 0)
}

function Test-Receipt {
    $path = Get-ReceiptPath
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    try { $data = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $false }
    if ([int]$data.schema -ne $Schema -or [string]$data.product -ne $Product) { return $false }
    $machine = Get-MachineHash
    if ([string]$data.machine -ne $machine) { return $false }
    if ([string]$data.version -ne $Version) { return $false }
    $rootHash = Get-PackageRootHash
    if ([string]$data.rootHash -ne $rootHash) { return $false }
    $expected = Get-Signature -ReceiptSchema $Schema -ReceiptProduct $Product -Machine $machine -ReceiptVersion $Version -RootHash $rootHash -IssuedAt ([string]$data.issuedAt)
    [byte[]]$actualBytes = [Text.Encoding]::ASCII.GetBytes(([string]$data.signature).ToLowerInvariant())
    [byte[]]$expectedBytes = [Text.Encoding]::ASCII.GetBytes($expected)
    if ($actualBytes.Length -ne $expectedBytes.Length) { return $false }
    $difference = 0
    for ($i = 0; $i -lt $actualBytes.Length; $i++) {
        $difference = $difference -bor ($actualBytes[$i] -bxor $expectedBytes[$i])
    }
    return ($difference -eq 0)
}

if ($Mode -eq 'Verify') {
    if (Test-Receipt) { exit 0 }
    exit 13
}
if ($Mode -eq 'Delete') {
    Remove-Item -LiteralPath (Get-ReceiptPath) -Force -ErrorAction SilentlyContinue
    exit 0
}
if ($Mode -eq 'Write') {
    $code = [string]$env:GUOLAB_INSTALL_TOTP_CODE
    if (-not (Test-TotpCode -Code $code)) { exit 13 }
} elseif ($Mode -eq 'WriteApproved') {
    if (-not (Test-ApprovedInstallTicket)) { exit 13 }
} else {
    exit 13
}
$machine = Get-MachineHash
$rootHash = Get-PackageRootHash
$issuedAt = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
$signature = Get-Signature -ReceiptSchema $Schema -ReceiptProduct $Product -Machine $machine -ReceiptVersion $Version -RootHash $rootHash -IssuedAt $issuedAt
$receipt = [ordered]@{
    schema = $Schema
    product = $Product
    machine = $machine
    version = $Version
    rootHash = $rootHash
    issuedAt = $issuedAt
    signature = $signature
}
$path = Get-ReceiptPath
$folder = Split-Path -Parent $path
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$temp = $path + '.tmp'
$receipt | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $temp -Encoding UTF8
Move-Item -LiteralPath $temp -Destination $path -Force
if (-not (Test-Receipt)) { exit 13 }
exit 0
