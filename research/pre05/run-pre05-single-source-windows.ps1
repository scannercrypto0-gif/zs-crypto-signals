# PRE05 00-04: exact 3 NEW synthetic research integration tests on owner's Windows.
# Does not run GitHub Actions, market APIs, real GitHub evidence writer,
# production scheduler, Telegram, trades, or Stage05.
param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$PinnedSha,
    [string]$Repo = 'D:\ZS Crypto Signals Latest Version'
)
$ErrorActionPreference = 'Stop'
$branch = 'pre05-stages00-04-single-source-offline-e2e-20261109'
$base = '3d210cf9aac8a789b3a3208a6b37a2d0ffad810b'
$workspace = Join-Path $env:TEMP ('zs-pre05-e2e-' + $PinnedSha.Substring(0,12))
$log = Join-Path $env:TEMP ('zs-pre05-e2e-' + $PinnedSha.Substring(0,12) + '.log')

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) {
    throw "REPOSITORY_NOT_FOUND: $Repo"
}
if (Test-Path -LiteralPath $workspace) {
    throw "ISOLATED_WORKTREE_ALREADY_EXISTS: $workspace"
}
$original = (& git -C $Repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'GIT_REPOSITORY_INVALID' }
& git -C $Repo fetch origin "refs/heads/$branch"
if ($LASTEXITCODE -ne 0) { throw 'BRANCH_FETCH_FAILED' }
$fetched = (& git -C $Repo rev-parse FETCH_HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $fetched -ne $PinnedSha) {
    throw "PINNED_HEAD_MISMATCH: $fetched"
}
$parent = (& git -C $Repo rev-list --max-parents=1 -n 1 $PinnedSha | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $parent) { throw 'HEAD_NOT_READABLE' }
& git -C $Repo merge-base --is-ancestor $base $PinnedSha
if ($LASTEXITCODE -ne 0) { throw 'FROZEN_MAIN_BASE_NOT_ANCESTOR' }
& git -C $Repo worktree add --detach $workspace $PinnedSha
if ($LASTEXITCODE -ne 0) { throw 'WORKTREE_ADD_FAILED' }
$head = (& git -C $workspace rev-parse HEAD).Trim()
if ($head -ne $PinnedSha) { throw 'WORKTREE_HEAD_MISMATCH' }
$before = @(& git -C $workspace status --porcelain=v1 --untracked-files=all)
if (($before | Where-Object { $_ -and $_.Trim() }).Count -gt 0) {
    throw 'WORKTREE_DIRTY_BEFORE'
}
$py = (& py -3.12 --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'PYTHON_312_NOT_AVAILABLE' }
$env:PYTHONPATH = "$workspace\src;$workspace\tests"
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONNOUSERSITE = '1'

$tests = @'
import socket
import sys
import unittest
import urllib.request
import sqlite3

def forbidden(*args, **kwargs):
    raise AssertionError("PRE05_NETWORK_FORBIDDEN")
socket.create_connection = forbidden
socket.socket.connect = forbidden
urllib.request.urlopen = forbidden

suite = unittest.defaultTestLoader.loadTestsFromName(
    "test_pre05_offline_full_chain.Pre05SingleSourceTargeted"
)
print("MATRIX_NEW_TEST_METHODS=" + str(suite.countTestCases()), flush=True)
if suite.countTestCases() != 3:
    raise SystemExit("EXACTLY_THREE_NEW_METHODS_REQUIRED")
result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
print("NEW_TESTS_RUN=" + str(result.testsRun), flush=True)
print("FAILURES=" + str(len(result.failures)), flush=True)
print("ERRORS=" + str(len(result.errors)), flush=True)
print("SQLITE_VERSION=" + sqlite3.sqlite_version, flush=True)
print("NETWORK_SOCKET_URLLIB_GUARDED=true", flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
'@
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $tests | & py -3.12 - 2>&1 | Tee-Object -FilePath $log
    $exit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
$after = @(& git -C $workspace status --porcelain=v1 --untracked-files=all)
if (($after | Where-Object { $_ -and $_.Trim() }).Count -gt 0) {
    Write-Output 'WORKTREE_DIRTY_AFTER=true'
    $exit = 4
}
$current = (& git -C $Repo rev-parse HEAD).Trim()
$hash = (Get-FileHash -LiteralPath $log -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Output "UTC_FINISHED=$((Get-Date).ToUniversalTime().ToString('o'))"
Write-Output "CWD=$workspace"
Write-Output "FROZEN_BASE_MAIN=$base"
Write-Output "PINNED_SHA=$head"
Write-Output "PYTHON_VERSION=$py"
Write-Output 'DEPENDENCIES=PYTHON_3_12_STANDARD_LIBRARY_ONLY'
Write-Output "LOG_FILE=$log"
Write-Output "LOG_SHA256=$hash"
Write-Output "EXIT_CODE=$exit"
Write-Output "OWNER_REPOSITORY_HEAD_UNCHANGED=$(([string]::Equals($original, $current)).ToString().ToLowerInvariant())"
Write-Output 'PRODUCTION_OR_GITHUB_WRITER=NOT_CALLED'
Write-Output 'DEVICE_REBOOT=NOT_TESTED'
exit $exit
