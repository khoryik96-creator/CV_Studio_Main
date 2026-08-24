param(
    [string]$Root = $PSScriptRoot,
    [string[]]$Candidates = @(),
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'

try {
    $Root = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
} catch {
    exit 8
}

$requirementsPath = Join-Path $Root 'requirements.txt'
if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
    exit 8
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
            & ([string]$candidate) $probePath $requirementsPath 2>$null
            $probeRc = [int]$LASTEXITCODE
            if ($probeRc -ne 0) { continue }
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

if ([string]::IsNullOrWhiteSpace($resolved)) {
    exit 8
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    Write-Output $resolved
} else {
    [IO.File]::WriteAllText(
        [IO.Path]::GetFullPath($OutputPath),
        $resolved,
        [Text.UTF8Encoding]::new($false)
    )
}
exit 0
