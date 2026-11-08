# Stage03 C1-C4 closure accounting: exactly three NEW tests.
# Read-only synthetic validation on owner's Windows host; no market calls.
param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$PinnedSha,
    [string]$Repo = 'D:\ZS Crypto Signals Latest Version'
)
$ErrorActionPreference = 'Stop'
$sourceBranch = 'stage03-c1c4-closure-accounting-20261108'
$workspace = Join-Path $env:TEMP ('zs03-c1c4-' + $PinnedSha.Substring(0, 12))
$log = Join-Path $env:TEMP ('zs03-c1c4-' + $PinnedSha.Substring(0, 12) + '.log')

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) {
    throw "REPOSITORY_DIRECTORY_NOT_FOUND: $Repo"
}
if (Test-Path -LiteralPath $workspace) {
    throw "ISOLATED_WORKTREE_ALREADY_EXISTS: $workspace"
}
$originalHead = (& git -C $Repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'NOT_A_GIT_REPOSITORY' }
& git -C $Repo fetch origin "refs/heads/$sourceBranch"
if ($LASTEXITCODE -ne 0) { throw 'SOURCE_BRANCH_FETCH_FAILED' }
$fetched = (& git -C $Repo rev-parse FETCH_HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $fetched -ne $PinnedSha) {
    throw "PINNED_HEAD_MISMATCH: $fetched"
}
& git -C $Repo worktree add --detach $workspace $PinnedSha
if ($LASTEXITCODE -ne 0) { throw 'WORKTREE_CREATION_FAILED' }
$head = (& git -C $workspace rev-parse HEAD).Trim()
if ($head -ne $PinnedSha) { throw 'WORKTREE_SHA_MISMATCH' }
$dirtyBefore = @(& git -C $workspace status --porcelain=v1 --untracked-files=all)
if (($dirtyBefore | Where-Object { $_ -and $_.Trim() }).Count -gt 0) {
    throw 'WORKTREE_DIRTY_BEFORE_TEST'
}
$pythonVersion = (& py -3.12 --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'PYTHON_312_NOT_AVAILABLE' }

$env:PYTHONPATH = "$workspace\src;$workspace\tests"
$env:PYTHONDONTWRITEBYTECODE = '1'
$script = @'
import socket
import sys
import unittest
import urllib.request

def no_network(*args, **kwargs):
    raise AssertionError("ZS03_C1C4_NETWORK_FORBIDDEN")
socket.create_connection = no_network
socket.socket.connect = no_network
urllib.request.urlopen = no_network

suite = unittest.defaultTestLoader.loadTestsFromName(
    "test_stage03_r2_closure.C1C4ClosureAccountingOnly"
)
print("TEST_COUNT=" + str(suite.countTestCases()), flush=True)
if suite.countTestCases() != 3:
    print("EXPECTED_EXACTLY_3_NEW_TESTS", flush=True)
    raise SystemExit(3)
result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
print("NEW_TESTS_RUN=" + str(result.testsRun), flush=True)
print("FAILURES=" + str(len(result.failures)), flush=True)
print("ERRORS=" + str(len(result.errors)), flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
'@
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $script | & py -3.12 - 2>&1 | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}
$dirtyAfter = @(& git -C $workspace status --porcelain=v1 --untracked-files=all)
if (($dirtyAfter | Where-Object { $_ -and $_.Trim() }).Count -gt 0) {
    Write-Output 'WORKTREE_DIRTY_AFTER_TEST=true'
    $code = 4
}
Write-Output "UTC_FINISHED=$((Get-Date).ToUniversalTime().ToString('o'))"
Write-Output "PINNED_SHA=$head"
Write-Output "PYTHON_VERSION=$pythonVersion"
Write-Output "LOG_FILE=$log"
Write-Output "LOG_SHA256=$((Get-FileHash -LiteralPath $log -Algorithm SHA256).Hash.ToLowerInvariant())"
Write-Output "EXIT_CODE=$code"
Write-Output "MAIN_BRANCH_UNCHANGED=$(([string]::Equals($originalHead, (& git -C $Repo rev-parse HEAD).Trim())).ToString().ToLowerInvariant())"
Write-Output 'NO_MARKET_REQUESTS=SOCKET_AND_URLLIB_BLOCKED'
exit $code
