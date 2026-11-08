# Narrow Stage03 N03 V0.2 local validation; 3 new + 1 impacted test.
# Run only on the owner's Windows machine. No production/market calls.
param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$PinnedSha,
    [string]$Repo = 'D:\ZS Crypto Signals Latest Version'
)
$ErrorActionPreference = 'Stop'
$branch = 'stage03-c1c4-closure-accounting-20261108'
$workspace = Join-Path $env:TEMP ('zs03-n03-v02-' + $PinnedSha.Substring(0,12))
$log = Join-Path $env:TEMP ('zs03-n03-v02-' + $PinnedSha.Substring(0,12) + '.log')

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) {
    throw "REPOSITORY_DIRECTORY_NOT_FOUND: $Repo"
}
if (Test-Path -LiteralPath $workspace) {
    throw "WORKTREE_EXISTS_REFUSE_REUSE: $workspace"
}
$originalHead = (& git -C $Repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'GIT_REPOSITORY_INVALID' }
& git -C $Repo fetch origin "refs/heads/$branch"
if ($LASTEXITCODE -ne 0) { throw 'GIT_FETCH_FAILED' }
$remoteHead = (& git -C $Repo rev-parse FETCH_HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $remoteHead -ne $PinnedSha) {
    throw "REF_MOVED_OR_WRONG_SHA: $remoteHead"
}
& git -C $Repo worktree add --detach $workspace $PinnedSha
if ($LASTEXITCODE -ne 0) { throw 'WORKTREE_ADD_FAILED' }
$actualHead = (& git -C $workspace rev-parse HEAD).Trim()
if ($actualHead -ne $PinnedSha) { throw 'WORKTREE_SHA_MISMATCH' }
$dirty = @(& git -C $workspace status --porcelain=v1 --untracked-files=all)
if (($dirty | Where-Object { $_ -and $_.Trim() }).Count -ne 0) {
    throw 'WORKTREE_NOT_CLEAN'
}
$pythonVersion = (& py -3.12 --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'PYTHON_312_NOT_FOUND' }
$env:PYTHONPATH = "$workspace\src;$workspace\tests"
$env:PYTHONDONTWRITEBYTECODE = '1'
$testScript = @'
import socket
import sys
import unittest
import urllib.request

def no_network(*args, **kwargs):
    raise AssertionError("ZS03_N03_V02_NO_NETWORK")
socket.create_connection = no_network
socket.socket.connect = no_network
urllib.request.urlopen = no_network

only_changed = [
    "test_stage03_n03_finalization.N03FinalizationOnly",
    "test_stage03_r2_closure.C1C4ClosureAccountingOnly.test_intraday_single_e2e_research_not_qualification_and_pending_semantics",
]
suite = unittest.defaultTestLoader.loadTestsFromNames(only_changed)
print("TEST_COUNT=" + str(suite.countTestCases()), flush=True)
if suite.countTestCases() != 4:
    print("EXPECTED_3_NEW_PLUS_1_IMPACTED_TEST", flush=True)
    raise SystemExit(3)
outcome = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
print("NEW_TEST_METHODS=3", flush=True)
print("IMPACTED_CHANGED_METHODS=1", flush=True)
print("TESTS_RUN=" + str(outcome.testsRun), flush=True)
print("FAILURES=" + str(len(outcome.failures)), flush=True)
print("ERRORS=" + str(len(outcome.errors)), flush=True)
raise SystemExit(0 if outcome.wasSuccessful() else 1)
'@
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $testScript | & py -3.12 - 2>&1 | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
$dirtyAfter = @(& git -C $workspace status --porcelain=v1 --untracked-files=all)
if (($dirtyAfter | Where-Object { $_ -and $_.Trim() }).Count -ne 0) {
    Write-Output 'WORKTREE_DIRTY_AFTER_TEST=true'
    $code = 4
}
$currentHead = (& git -C $Repo rev-parse HEAD).Trim()
Write-Output "UTC_FINISHED=$((Get-Date).ToUniversalTime().ToString('o'))"
Write-Output "PINNED_SHA=$actualHead"
Write-Output "PYTHON_VERSION=$pythonVersion"
Write-Output "LOG_FILE=$log"
Write-Output "LOG_SHA256=$((Get-FileHash -LiteralPath $log -Algorithm SHA256).Hash.ToLowerInvariant())"
Write-Output "EXIT_CODE=$code"
Write-Output "ORIGINAL_REPOSITORY_HEAD_UNCHANGED=$(([string]::Equals($originalHead, $currentHead)).ToString().ToLowerInvariant())"
Write-Output 'MARKET_API_CALLS=NOT_ATTEMPTED_SOCKET_AND_URLLIB_GUARDED'
exit $code
