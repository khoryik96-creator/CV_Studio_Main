param(
    [string]$Root = $PSScriptRoot,
    [switch]$ResolvePythonOnly,
    [string[]]$PythonCandidates = @(),
    [string]$PythonOutputPath = ''
)
$ErrorActionPreference = 'Stop'

function Stop-WithError([string]$Message, [int]$Code) {
    Write-Host ("ERROR: {0}" -f $Message)
    exit $Code
}

function Resolve-ExactPythonRuntime {
    param([string]$SourceRoot, [string[]]$Candidates = @())

    $requirementsPath = Join-Path $SourceRoot 'requirements.txt'
    if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
        return ''
    }
    if ($Candidates.Count -eq 0) {
        $Candidates = @(
            @(
                [string](Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
                $(if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe' }),
                $(if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe' }),
                $(if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe' }),
                $(if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe' }),
                'C:\Python314\python.exe',
                'C:\Python313\python.exe',
                'C:\Python312\python.exe',
                'C:\Python311\python.exe'
            ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique
        )
    } else {
        $Candidates = @(
            $Candidates |
                Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
                Select-Object -Unique
        )
    }

    $probe = @'
import importlib.metadata as metadata
import pathlib
import re
import sys

requirements_path = pathlib.Path(sys.argv[1])
try:
    lines = requirements_path.read_text(encoding="utf-8").splitlines()
except Exception:
    raise SystemExit(3)

pins = []
for raw_line in lines:
    line = raw_line.split("#", 1)[0].strip()
    if not line:
        continue
    if line.count("==") != 1:
        raise SystemExit(3)
    name, expected = (part.strip() for part in line.split("==", 1))
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or not expected or re.search(r"[\s;]", expected):
        raise SystemExit(3)
    pins.append((name, expected))

if not pins:
    raise SystemExit(3)

try:
    for name, expected in pins:
        if metadata.version(name).casefold() != expected.casefold():
            raise SystemExit(2)
    import flask, pdfplumber, docx, pytesseract, pdf2image, pypdfium2
    import PIL, olefile, certifi, reportlab, openpyxl, bs4, pypdf, requests, waitress
except SystemExit:
    raise
except Exception:
    raise SystemExit(2)
'@

    $probePath = [IO.Path]::GetTempFileName()
    $resolved = ''
    try {
        [IO.File]::WriteAllText($probePath, $probe, [Text.UTF8Encoding]::new($false))
        foreach ($candidate in $Candidates) {
            try {
                & ([string]$candidate) $probePath $requirementsPath 2>$null | Out-Null
                if ([int]$LASTEXITCODE -ne 0) { continue }
                $candidatePath = [IO.Path]::GetFullPath([string]$candidate)
                $pythonw = Join-Path (Split-Path -Parent $candidatePath) 'pythonw.exe'
                $resolved = if (Test-Path -LiteralPath $pythonw -PathType Leaf) {
                    [IO.Path]::GetFullPath($pythonw)
                } else {
                    $candidatePath
                }
                break
            } catch {}
        }
    } finally {
        Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue
    }
    return $resolved
}

try {
    $Root = [IO.Path]::GetFullPath($Root).TrimEnd('\','/')
} catch {
    Stop-WithError 'The CV Studio folder path is invalid.' 2
}

if ($ResolvePythonOnly) {
    $resolvedPython = [string](Resolve-ExactPythonRuntime -SourceRoot $Root -Candidates $PythonCandidates)
    if ([string]::IsNullOrWhiteSpace($resolvedPython)) { exit 8 }
    if ([string]::IsNullOrWhiteSpace($PythonOutputPath)) {
        Write-Output $resolvedPython
    } else {
        [IO.File]::WriteAllText(
            [IO.Path]::GetFullPath($PythonOutputPath),
            $resolvedPython,
            [Text.UTF8Encoding]::new($false)
        )
    }
    exit 0
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
$sourcePreflight = [IO.Path]::GetFullPath((Join-Path $Root 'UPDATE_PREFLIGHT.ps1'))
$runningPreflight = [IO.Path]::GetFullPath($MyInvocation.MyCommand.Path)
if ($runningPreflight -eq $sourcePreflight) {
    $required += 'PYTHON_RUNTIME.ps1'
}
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
    $resolvedPython = [string](Resolve-ExactPythonRuntime -SourceRoot $Root)
    if ([string]::IsNullOrWhiteSpace($resolvedPython) -or
            -not (Test-Path -LiteralPath $resolvedPython -PathType Leaf)) {
        Stop-WithError 'Python or one or more exact runtime package versions are missing. Run INSTALL.bat.' 8
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
