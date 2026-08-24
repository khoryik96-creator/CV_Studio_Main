param(
    [string]$Root = $PSScriptRoot,
    [string[]]$Candidates = @(),
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'
$preflight = Join-Path $Root 'UPDATE_PREFLIGHT.ps1'
if (-not (Test-Path -LiteralPath $preflight -PathType Leaf)) {
    exit 8
}

& $preflight `
    -Root $Root `
    -ResolvePythonOnly `
    -PythonCandidates $Candidates `
    -PythonOutputPath $OutputPath
exit $LASTEXITCODE
