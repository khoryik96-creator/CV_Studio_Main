param([string]$Root = $PSScriptRoot)
$ErrorActionPreference = 'Stop'

function Stop-WithError([string]$Message, [int]$Code) {
    Write-Host ("ERROR: {0}" -f $Message)
    exit $Code
}

try {
    $Root = [IO.Path]::GetFullPath($Root).TrimEnd('\','/')
} catch {
    Stop-WithError 'The CV Studio folder path is invalid.' 2
}
$programFilesX86 = [string]${env:ProgramFiles(x86)}

$required = @(
    'CV Studio.bat',
    'START_HIDDEN.vbs',
    'FORCE_STOP.ps1',
    'INSTALL_RECEIPT.ps1',
    'package.json',
    'requirements.txt'
)
$missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $Root $_) -PathType Leaf) })
if ($missing.Count -gt 0) {
    Stop-WithError ("Required update file(s) are missing: {0}" -f ($missing -join ', ')) 2
}

$receiptVerifier = Join-Path $Root 'INSTALL_RECEIPT.ps1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $receiptVerifier -Mode Verify | Out-Null
if ($LASTEXITCODE -ne 0) {
    Stop-WithError 'CV Studio authorization is not valid for this folder. Run INSTALL.bat before updating.' 13
}

$nodeCandidates = @(
    @(
        (Join-Path $Root 'node\node.exe'),
        [string](Get-Command node.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
        (Join-Path $env:ProgramFiles 'nodejs\node.exe'),
        $(if ($programFilesX86) { Join-Path $programFilesX86 'nodejs\node.exe' }),
        $(if ($env:APPDATA) { Join-Path $env:APPDATA 'nvm\current\node.exe' })
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique
)
if ($nodeCandidates.Count -eq 0) {
    Stop-WithError 'Node.js is unavailable. Run INSTALL.bat while the current server is still running.' 6
}
$node = [string]$nodeCandidates[0]
$nodeProbe = @'
const path=require('path');
const root=process.argv[1];
const pkg=require(path.join(root,'node_modules','adm-zip','package.json'));
if(pkg.version!=='0.6.0') process.exit(2);
const AdmZip=require(path.join(root,'node_modules','adm-zip'));
const zip=new AdmZip(); zip.addFile('probe.txt',Buffer.from('ok'));
if(new AdmZip(zip.toBuffer()).readAsText('probe.txt')!=='ok') process.exit(3);
'@
& $node -e $nodeProbe $Root
if ($LASTEXITCODE -ne 0) {
    Stop-WithError 'The required adm-zip 0.6.0 runtime is missing or damaged. Run INSTALL.bat.' 6
}

$nativeRuntime = Join-Path $Root 'runtime\native\CVStudio.exe'
if (-not (Test-Path -LiteralPath $nativeRuntime -PathType Leaf)) {
    $pythonCandidates = @(
        @(
            [string](Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
            'C:\Python314\python.exe',
            'C:\Python313\python.exe',
            'C:\Python312\python.exe',
            'C:\Python311\python.exe'
        ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique
    )
    if ($pythonCandidates.Count -eq 0) {
        Stop-WithError 'Python is unavailable. Run INSTALL.bat while the current server is still running.' 8
    }
    $imports = 'import flask,pdfplumber,docx,pytesseract,pdf2image,pypdfium2,PIL,olefile,certifi,reportlab,openpyxl,bs4,pypdf,requests,waitress'
    $python = $null
    foreach ($candidate in $pythonCandidates) {
        try {
            & ([string]$candidate) -c $imports 2>$null
            if ($LASTEXITCODE -eq 0) { $python = [string]$candidate; break }
        } catch {}
    }
    if (-not $python) {
        Stop-WithError 'One or more Python runtime packages are missing. Run INSTALL.bat.' 8
    }
}

$tesseractCandidates = @(
    @(
        (Join-Path $Root 'tesseract\tesseract.exe'),
        [string](Get-Command tesseract.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
        (Join-Path $env:ProgramFiles 'Tesseract-OCR\tesseract.exe'),
        $(if ($programFilesX86) { Join-Path $programFilesX86 'Tesseract-OCR\tesseract.exe' }),
        (Join-Path $env:LOCALAPPDATA 'Programs\Tesseract-OCR\tesseract.exe')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique
)
if ($tesseractCandidates.Count -eq 0) {
    Stop-WithError 'Tesseract is unavailable. Run INSTALL.bat while the current server is still running.' 10
}
$languages = @(& ([string]$tesseractCandidates[0]) --list-langs 2>$null)
if ($LASTEXITCODE -ne 0 -or -not ($languages -contains 'eng')) {
    Stop-WithError 'Tesseract English language data is unavailable. Run INSTALL.bat.' 10
}

Write-Host 'Update preflight passed. The current server can now be restarted safely.'
exit 0
