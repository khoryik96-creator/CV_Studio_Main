param([string]$Root = $PSScriptRoot)

$ErrorActionPreference = 'Stop'

function Stop-Update {
    param([string]$Message, [int]$Code)
    Write-Host ''
    Write-Host ("ERROR: {0}" -f $Message)
    Write-Host 'The current CV Studio server was left untouched.'
    if ($script:UpdateLog) { Write-Host ("Update log: `"{0}`"" -f $script:UpdateLog) }
    Write-Host ''
    Write-Host 'Press Enter to close this window.'
    try { $null = [Console]::ReadLine() } catch {}
    exit $Code
}

function Write-UpdateLog {
    param([string]$Message)
    if (-not $script:UpdateLog) { return }
    try {
        Add-Content -LiteralPath $script:UpdateLog -Value (
            '{0:yyyy-MM-dd HH:mm:ss.fff} | {1}' -f [DateTime]::Now, $Message
        ) -Encoding UTF8
    } catch {}
}

function Invoke-Preflight {
    param([string]$ScriptPath, [string]$SourceRoot)
    if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) { return 9 }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ScriptPath -Root $SourceRoot
    return [int]$LASTEXITCODE
}

try {
    $Root = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
} catch {
    Stop-Update 'The CV Studio folder path is invalid.' 2
}
Set-Location -LiteralPath $Root

$script:UpdateLog = $null
$stateDir = [string]$env:CVSTUDIO_UPDATE_STATE_DIR
if ([string]::IsNullOrWhiteSpace($stateDir)) {
    $stateDir = Join-Path $env:LOCALAPPDATA 'TheGuoLab\CVStudio'
}
try {
    New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
    $script:UpdateLog = Join-Path $stateDir 'source_update.log'
    if ((Test-Path -LiteralPath $script:UpdateLog -PathType Leaf) -and
            (Get-Item -LiteralPath $script:UpdateLog).Length -ge 1MB) {
        Move-Item -LiteralPath $script:UpdateLog -Destination ($script:UpdateLog + '.1') -Force
    }
} catch {
    $script:UpdateLog = $null
}
Write-UpdateLog 'update_started'

Write-Host '============================================'
Write-Host '  CV Studio - Update & Restart'
Write-Host '============================================'
Write-Host ''

$gitCandidates = @(
    [string](Get-Command git.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
    (Join-Path $env:ProgramFiles 'Git\cmd\git.exe'),
    $(if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} 'Git\cmd\git.exe' })
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique
if ($env:LOCALAPPDATA) {
    $desktopGit = Get-ChildItem -LiteralPath (Join-Path $env:LOCALAPPDATA 'GitHubDesktop') -Directory -Filter 'app-*' -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName 'resources\app\git\cmd\git.exe' } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
    if ($desktopGit) { $gitCandidates = @($gitCandidates) + @([string]$desktopGit) }
}
$git = [string]($gitCandidates | Select-Object -First 1)

$preflight = Join-Path $Root 'UPDATE_PREFLIGHT.ps1'
$updateApplied = $false
$previousCommit = ''
$currentCommit = ''

if (-not $git) {
    Write-UpdateLog 'git_unavailable'
    Write-Host 'Could not find Git automatically.'
    Write-Host 'No files were changed. CV Studio will restart on the current version.'
    Write-Host ''
} else {
    Write-Host ("Using git: `"{0}`"" -f $git)
    Write-Host ''
    & $git rev-parse --is-inside-work-tree *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-UpdateLog 'not_a_git_clone'
        Write-Host 'This folder is not a Git clone, so no files were changed.'
        Write-Host 'CV Studio will restart on the current version.'
        Write-Host ''
    } else {
        $branch = [string]((& $git symbolic-ref --quiet --short HEAD 2>$null | Select-Object -First 1))
        Write-Host 'Current branch:'
        Write-Host $branch
        if ($branch -cne 'master') {
            Write-UpdateLog ("unsupported_branch={0}" -f $branch)
            Stop-Update 'Automatic updates are allowed only from the master branch. Switch to master in GitHub Desktop, then try again.' 14
        }
        & $git diff --quiet --ignore-submodules --
        if ($LASTEXITCODE -ne 0) {
            Write-UpdateLog 'dirty_tracked_worktree'
            Stop-Update 'This master folder contains uncommitted tracked changes. Commit or discard them in GitHub Desktop before updating.' 15
        }
        & $git diff --cached --quiet --ignore-submodules --
        if ($LASTEXITCODE -ne 0) {
            Write-UpdateLog 'dirty_staged_worktree'
            Stop-Update 'This master folder contains staged changes. Commit or discard them in GitHub Desktop before updating.' 15
        }

        Write-Host 'Checking the current CV Studio installation before downloading changes...'
        $preflightRc = Invoke-Preflight -ScriptPath $preflight -SourceRoot $Root
        if ($preflightRc -ne 0) {
            Write-UpdateLog ("current_preflight_failed_{0}" -f $preflightRc)
            Stop-Update 'The current installation is not ready to update. Run INSTALL.bat in this exact folder, then try again.' $preflightRc
        }
        Write-UpdateLog 'current_preflight_passed'

        $previousCommit = [string]((& $git rev-parse HEAD | Select-Object -First 1))
        $currentCommit = $previousCommit
        Write-UpdateLog ("previous_commit={0}" -f $previousCommit)
        Write-Host 'Fetching the latest master version...'
        Write-Host ''
        & $git fetch --no-tags origin 'master:refs/remotes/origin/master'
        $fetchRc = [int]$LASTEXITCODE
        Write-Host ''
        if ($fetchRc -ne 0) {
            Write-UpdateLog ("git_fetch_failed_{0}" -f $fetchRc)
            Write-Host ("The latest master version could not be downloaded (exit code {0})." -f $fetchRc)
            Write-Host 'No source files were changed. CV Studio will restart on the current version.'
            Write-Host ''
        } else {
            & $git merge-base --is-ancestor HEAD refs/remotes/origin/master
            if ($LASTEXITCODE -ne 0) {
                Write-UpdateLog 'master_non_fast_forward'
                Stop-Update 'Local master and GitHub master have diverged. Open GitHub Desktop to review the history safely.' 16
            }

            # The candidate preflight runs before source files are changed, so
            # it cannot safely validate new exact dependency pins against the
            # old checkout. Stop instead of restarting with stale packages.
            $dependencyManifests = @('requirements.txt', 'package.json', 'package-lock.json')
            & $git diff --quiet HEAD refs/remotes/origin/master -- @dependencyManifests
            $dependencyDiffRc = [int]$LASTEXITCODE
            if ($dependencyDiffRc -eq 1) {
                Write-UpdateLog 'candidate_dependency_manifest_changed'
                Stop-Update 'The downloaded master version changes runtime dependencies. No source files were changed. Pull master in GitHub Desktop, then run INSTALL.bat in this exact folder.' 18
            }
            if ($dependencyDiffRc -ne 0) {
                Write-UpdateLog ("candidate_dependency_check_failed_{0}" -f $dependencyDiffRc)
                Stop-Update 'The downloaded master dependency files could not be inspected safely. No source files were changed.' 17
            }

            $candidatePreflight = Join-Path $stateDir 'candidate_update_preflight.ps1'
            try {
                $candidateLines = @(& $git show 'refs/remotes/origin/master:UPDATE_PREFLIGHT.ps1')
                if ($LASTEXITCODE -ne 0 -or $candidateLines.Count -eq 0) {
                    Stop-Update 'The downloaded master updater could not be inspected safely.' 17
                }
                [IO.File]::WriteAllLines(
                    $candidatePreflight,
                    [string[]]$candidateLines,
                    [Text.UTF8Encoding]::new($false)
                )
                Write-Host 'Checking the downloaded updater before changing source files...'
                $candidateRc = Invoke-Preflight -ScriptPath $candidatePreflight -SourceRoot $Root
            } finally {
                Remove-Item -LiteralPath $candidatePreflight -Force -ErrorAction SilentlyContinue
            }
            if ($candidateRc -ne 0) {
                Write-UpdateLog ("candidate_preflight_failed_{0}" -f $candidateRc)
                Stop-Update 'The downloaded master version needs installation work before it can launch. No source files were changed. Pull master in GitHub Desktop, then run INSTALL.bat.' $candidateRc
            }

            & $git merge --ff-only refs/remotes/origin/master
            $mergeRc = [int]$LASTEXITCODE
            if ($mergeRc -ne 0) {
                Write-UpdateLog ("git_merge_failed_{0}" -f $mergeRc)
                Stop-Update 'The downloaded master version could not be applied. Review the repository in GitHub Desktop.' $mergeRc
            }
            $updateApplied = $true
            $currentCommit = [string]((& $git rev-parse HEAD | Select-Object -First 1))
            Write-UpdateLog ("current_commit={0}" -f $currentCommit)
            Write-Host 'Files updated successfully.'
            Write-Host ''
        }
    }
}

Write-Host 'Checking CV Studio before stopping the current server...'
$preflightRc = Invoke-Preflight -ScriptPath $preflight -SourceRoot $Root
if ($preflightRc -ne 0) {
    Write-UpdateLog ("post_update_preflight_failed_{0}" -f $preflightRc)
    Stop-Update 'The files are not ready to launch. Run INSTALL.bat while the current server remains available.' $preflightRc
}
Write-UpdateLog 'post_update_preflight_passed'

$stopHelper = Join-Path $Root 'FORCE_STOP.ps1'
if (-not (Test-Path -LiteralPath $stopHelper -PathType Leaf)) {
    Stop-Update 'FORCE_STOP.ps1 was not found. CV Studio was not restarted because the old server may still be running.' 2
}
Write-Host 'Stopping any running CV Studio server...'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stopHelper
$stopRc = [int]$LASTEXITCODE
if ($stopRc -ne 0) {
    Write-UpdateLog ("stop_failed_{0}" -f $stopRc)
    Stop-Update 'CV Studio could not be stopped safely. Review the message above, then try again.' $stopRc
}

$launcher = Join-Path $Root 'CV Studio.bat'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    Write-Host 'ERROR: CV Studio.bat was not found after stopping the old server.'
    exit 1
}
Write-Host 'Starting CV Studio...'
& $launcher '--wait'
$startRc = [int]$LASTEXITCODE
if ($startRc -ne 0) {
    Write-UpdateLog ("restart_failed_{0}" -f $startRc)
    Write-Host ''
    Write-Host ("ERROR: The updated CV Studio did not start correctly (exit code {0})." -f $startRc)
    Write-Host ("Previous source commit: {0}" -f $previousCommit)
    Write-Host ("Current source commit:  {0}" -f $currentCommit)
    Write-Host 'Use GitHub Desktop History if you need to return to the previous commit.'
    Write-Host 'Local edits were not reset or overwritten.'
    if ($script:UpdateLog) { Write-Host ("Update log: `"{0}`"" -f $script:UpdateLog) }
    Write-Host 'Press Enter to close this window.'
    try { $null = [Console]::ReadLine() } catch {}
    exit $startRc
}

Write-UpdateLog 'restart_succeeded'
if ($updateApplied) { Write-Host 'CV Studio was updated and restarted successfully.' }
else { Write-Host 'CV Studio restarted on the current version.' }
if ($script:UpdateLog) { Write-Host ("Update log: `"{0}`"" -f $script:UpdateLog) }
exit 0
