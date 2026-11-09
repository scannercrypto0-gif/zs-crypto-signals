# Stage05: EXACT NINE targeted test methods; owner Windows ONLY; never live Telegram.
param(
  [Parameter(Mandatory=$true)]
  [ValidatePattern('^[0-9a-f]{40}$')]
  [string]$PinnedSha,
  [string]$Repo = 'D:\ZS Crypto Signals Latest Version'
)
$ErrorActionPreference='Stop'
$branch='stage05-real-telegram-transport-disabled-20261109'
$base='f064493e77bd4f70029fb8af1837ac9685d07c41'
if (-not (Test-Path -LiteralPath $Repo -PathType Container)) { throw 'GIT_REPOSITORY_NOT_FOUND' }
$repoFull=(Resolve-Path -LiteralPath $Repo).ProviderPath
if (-not [string]::Equals([System.IO.Path]::GetPathRoot($repoFull), 'D:\',
                         [System.StringComparison]::OrdinalIgnoreCase)) {
  throw 'PROJECT_LOCAL_FILES_MUST_BE_ON_D_DRIVE'
}
$runRoot=Join-Path (Split-Path -Parent $repoFull) 'ZS_STAGE05_LOCAL_TEMP'
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
$worktree=Join-Path $runRoot ('zs05-real-offline-' + $PinnedSha.Substring(0,12))
$log=Join-Path $runRoot ('zs05-real-offline-' + $PinnedSha.Substring(0,12) + '.log')
$env:TEMP=$runRoot
$env:TMP=$runRoot
$env:TMPDIR=$runRoot
if (Test-Path -LiteralPath $worktree) { throw 'PINNED_WORKTREE_ALREADY_EXISTS' }
$before=(& git -C $Repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'GIT_BASE_INVALID' }
& git -C $Repo fetch origin "refs/heads/$branch"
if ($LASTEXITCODE -ne 0) { throw 'BRANCH_FETCH_FAILED' }
$fetched=(& git -C $Repo rev-parse FETCH_HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $fetched -ne $PinnedSha) {
  throw "PINNED_SHA_MISMATCH: $fetched"
}
& git -C $Repo merge-base --is-ancestor $base $PinnedSha
if ($LASTEXITCODE -ne 0) { throw 'EXPECTED_MAIN_BASE_NOT_ANCESTOR' }
& git -C $Repo worktree add --detach $worktree $PinnedSha
if ($LASTEXITCODE -ne 0) { throw 'WORKTREE_ADD_FAILED' }
$head=(& git -C $worktree rev-parse HEAD).Trim()
if ($head -ne $PinnedSha) { throw 'HEAD_MISMATCH' }
$dirty=@(& git -C $worktree status --porcelain=v1 --untracked-files=all)
if (($dirty | Where-Object { $_ -and $_.Trim() }).Count -gt 0) {
  throw 'WORKTREE_NOT_CLEAN'
}
$version=(& py -3.12 --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'PYTHON_3_12_UNAVAILABLE' }
$env:PYTHONPATH="$worktree\src;$worktree\tests"
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONNOUSERSITE='1'
# Hard-disable all functions for the owner test process, even if parent shell
# had a value. No secret env vars are needed by these synthetic fake fixtures.
$env:ZS_TELEGRAM_SEND_ENABLED='false'
$env:ZS_SIGNALS_DISPATCH_ENABLED='false'
$env:ZS_ANALYTICS_DISPATCH_ENABLED='false'
$env:ZS_INTERACTIVE_POLLING_ENABLED='false'
$env:ZS_INTERACTIVE_REPLY_ENABLED='false'
foreach ($name in @('ZS_SIGNALS_BOT_TOKEN','ZS_SIGNALS_CHAT_ID_A',
                    'ZS_SIGNALS_CHAT_ID_B','ZS_INTERACTIVE_BOT_TOKEN',
                    'ZS_INTERACTIVE_ALLOWED_USER_IDS',
                    'ZS_INTERACTIVE_ALLOWED_CHAT_IDS',
                    'ZS_ANALYTICS_BOT_TOKEN','ZS_ANALYTICS_CHAT_ID')) {
  Remove-Item -Path ("Env:" + $name) -ErrorAction SilentlyContinue
}
$test=@'
import socket
import sys
import unittest
import urllib.request
import sqlite3

def block(*a, **k):
    raise AssertionError("STAGE05_TEST_NETWORK_FORBIDDEN")
socket.create_connection=block
socket.socket.connect=block
urllib.request.urlopen=block

suite=unittest.defaultTestLoader.loadTestsFromName(
    "test_stage05_real_telegram.Stage05RealTransportTargeted")
print("NEW_STAGE05_METHODS="+str(suite.countTestCases()),flush=True)
if suite.countTestCases()!=9:
    raise SystemExit("EXPECTED_NINE_TARGETED_METHODS")
result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite)
print("NEW_TESTS_RUN="+str(result.testsRun),flush=True)
print("FAILURES="+str(len(result.failures)),flush=True)
print("ERRORS="+str(len(result.errors)),flush=True)
print("REAL_TELEGRAM_HTTP_REQUESTS=0",flush=True)
print("REAL_GITHUB_WRITER=NOT_CALLED",flush=True)
print("REAL_SQL_SERVER=NOT_CONNECTED",flush=True)
print("LIVE_SWITCHES=ALL_FALSE",flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
'@
$prior=$ErrorActionPreference
$ErrorActionPreference='Continue'
try {
  $test | & py -3.12 - 2>&1 | Tee-Object -FilePath $log
  $exit=$LASTEXITCODE
} finally {
  $ErrorActionPreference=$prior
}
$dirty=@(& git -C $worktree status --porcelain=v1 --untracked-files=all)
if (($dirty | Where-Object { $_ -and $_.Trim() }).Count -gt 0) {
  Write-Output 'WORKTREE_DIRTY_AFTER_TEST=true'
  $exit=4
}
$after=(& git -C $Repo rev-parse HEAD).Trim()
Write-Output "UTC_FINISHED=$((Get-Date).ToUniversalTime().ToString('o'))"
Write-Output "PINNED_SHA=$head"
Write-Output "PYTHON_VERSION=$version"
Write-Output 'DEPENDENCIES=PYTHON_3_12_STDLIB_ONLY'
Write-Output "LOG_FILE=$log"
Write-Output "LOG_SHA256=$((Get-FileHash -LiteralPath $log -Algorithm SHA256).Hash.ToLowerInvariant())"
Write-Output "EXIT_CODE=$exit"
Write-Output "ORIGINAL_REPOSITORY_HEAD_UNCHANGED=$(([string]::Equals($before,$after)).ToString().ToLowerInvariant())"
Write-Output 'TELEGRAM_LIVE_CONNECTIVITY=NOT_TESTED_OWNER_HOLD'
Write-Output 'PRODUCTION=NOT_AUTHORIZED'
exit $exit
