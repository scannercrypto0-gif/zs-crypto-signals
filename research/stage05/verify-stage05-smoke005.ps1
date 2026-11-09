# ZS Stage05 Windows PowerShell 5.1 offline verification only.
# NEVER invokes Telegram or reads bot credentials. NO --execute.
param(
    [string]$Repository = 'D:\ZS Crypto Signals Latest Version',
    [string]$Root = 'D:\ZS_STAGE05_LOCAL_TEMP'
)
$ErrorActionPreference = 'Stop'
$head = 'a15f3399233f211d6b73378d9b0b7f0d78c6a41d'
$tree = '8566977aeacd38ef59ba120f4f36318b1d382f16'
$blob = 'fc1605cba716edd591eb7352e86acd584fc27c20'
$expectedSha256 = '255c8a8213171448ef6631113cc28702d99e30f46b3c383c2a5c75c38f98b9a7'
$branch = 'stage05-real-telegram-transport-disabled-20261109'
$relative = 'research/stage05/zs05_three_bot_smoke_windows.py'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')
$runDir = Join-Path $Root ('zs05-smoke005-' + $head.Substring(0,12) + '-' + $stamp)
$worktree = Join-Path $runDir 'repo'
$log = Join-Path $runDir 'validation.log'
$original = $null
$worktreeCreated = $false
$result = 'FAIL'
$exitCode = 1
$tests = 'NOT_RUN'
$dry = 'NOT_RUN'
$restored = 'NO'
$beforeHash = 'NOT_CHECKED'
$rawGitHash = 'NOT_CHECKED'
$actualHash = 'NOT_CHECKED'
$originalUnchanged = 'UNKNOWN'
$gitConfig = 'UNAVAILABLE'
$pythonVersion = 'UNKNOWN'
function GitValue([string[]] $gitArgs) {
    $output = & git -C $Repository @gitArgs 2>$null
    if ($LASTEXITCODE -ne 0) { throw ('GIT_COMMAND_FAILED: ' + ($gitArgs -join ' ')) }
    return (($output | Out-String).Trim())
}
function HashFile([string] $path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function FileLength([string] $path) {
    return ([System.IO.FileInfo]::new($path)).Length
}
try {
    if (-not [string]::Equals([System.IO.Path]::GetPathRoot($Repository), 'D:\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'REPOSITORY_MUST_BE_D_DRIVE' }
    if (-not [string]::Equals([System.IO.Path]::GetPathRoot($Root), 'D:\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'LOG_ROOT_MUST_BE_D_DRIVE' }
    if (-not (Test-Path -LiteralPath $Repository -PathType Container)) { throw 'REPOSITORY_NOT_FOUND' }
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    $original = GitValue -gitArgs @('rev-parse','HEAD')
    $priorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & git -C $Repository fetch origin ('refs/heads/' + $branch) 2>&1 | Out-Null
        $fetchExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $priorPreference }
    if ($fetchExit -ne 0) { throw 'PINNED_FETCH_FAILED' }
    if ((GitValue -gitArgs @('rev-parse','FETCH_HEAD')) -ne $head) { throw 'FETCH_HEAD_MISMATCH' }
    if ((GitValue -gitArgs @('rev-parse',($head + '^{tree}'))) -ne $tree) { throw 'TREE_MISMATCH' }
    if ((GitValue -gitArgs @('rev-parse',($head + ':' + $relative))) -ne $blob) { throw 'GIT_BLOB_MISMATCH' }
    $gitConfig = ((& git -C $Repository config --get core.autocrlf 2>$null | Out-String).Trim())
    if (-not $gitConfig) { $gitConfig = 'UNSET' }
    $priorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & git -C $Repository worktree add --detach $worktree $head 2>&1 | Out-Null
        $worktreeExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $priorPreference }
    if ($worktreeExit -ne 0) { throw 'ISOLATED_WORKTREE_CREATE_FAILED' }
    $worktreeCreated = $true
    if ((& git -C $worktree rev-parse HEAD | Out-String).Trim() -ne $head) { throw 'WORKTREE_HEAD_MISMATCH' }
    $script = Join-Path $worktree 'research\stage05\zs05_three_bot_smoke_windows.py'
    $test = Join-Path $worktree 'research\stage05\test_zs05_three_bot_smoke.py'
    if (-not (Test-Path -LiteralPath $script -PathType Leaf) -or -not (Test-Path -LiteralPath $test -PathType Leaf)) { throw 'PINNED_FILES_MISSING' }
    $beforeHash = HashFile $script
    # git cat-file -p outputs raw bytes; redirect natively through cmd.exe so PowerShell text pipelines never transcode it.
    $gitRaw = Join-Path $runDir 'github-exact-script.py'
    $gitSpec = $head + ':' + $relative
    $rawCommand = 'git -C "' + $Repository + '" cat-file blob ' + $blob + ' > "' + $gitRaw + '"'
    & cmd.exe /d /s /c $rawCommand
    if ($LASTEXITCODE -ne 0) { throw 'GIT_RAW_EXTRACTION_FAILED' }
    $rawGitHash = HashFile $gitRaw
    if ($rawGitHash -ne $expectedSha256 -or (FileLength $gitRaw) -ne 22925) { throw 'GIT_RAW_SHA_OR_BYTES_MISMATCH' }
    if ($beforeHash -ne $expectedSha256) {
        $first = [System.IO.File]::ReadAllBytes($script)
        $raw = [System.IO.File]::ReadAllBytes($gitRaw)
        $firstCRLF = [System.Text.Encoding]::UTF8.GetString($first).Contains("`r`n")
        $rawCRLF = [System.Text.Encoding]::UTF8.GetString($raw).Contains("`r`n")
        $diagnosis = 'CHECKOUT_MISMATCH: local_bytes=' + $first.Length + '; git_bytes=' + $raw.Length + '; local_CRLF=' + $firstCRLF + '; git_CRLF=' + $rawCRLF
        Add-Content -LiteralPath $log -Value $diagnosis -Encoding UTF8
        # Restore only exact previously verified Git bytes, solely inside detached worktree.
        [System.IO.File]::WriteAllBytes($script, $raw)
        $restored = 'YES_EXACT_GIT_BYTES_IN_ISOLATED_WORKTREE'
    }
    $actualHash = HashFile $script
    if ($actualHash -ne $expectedSha256) { throw 'SCRIPT_SHA_MISMATCH_AFTER_RESTORE' }
    if ((FileLength $script) -ne 22925) { throw 'SCRIPT_LENGTH_MISMATCH' }
    $pythonVersion = (& py -3.12 --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $pythonVersion -notmatch '^Python 3\.12\.') { throw 'PYTHON_312_REQUIRED' }
    $env:TEMP = $runDir; $env:TMP=$runDir; $env:TMPDIR=$runDir
    $env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONNOUSERSITE='1'
    # Defense in depth: no Telegram secrets or activation switches inside these test processes.
    foreach ($name in @('ZS_SIGNALS_BOT_TOKEN','ZS_INTERACTIVE_BOT_TOKEN','ZS_ANALYTICS_BOT_TOKEN','ZS_SIGNALS_CHAT_ID_A','ZS_SIGNALS_CHAT_ID_B','ZS_ANALYTICS_CHAT_ID','ZS_INTERACTIVE_ALLOWED_USER_IDS','ZS_INTERACTIVE_ALLOWED_CHAT_IDS')) {
        Remove-Item ('Env:' + $name) -ErrorAction SilentlyContinue
    }
    foreach ($name in @('ZS_TELEGRAM_SEND_ENABLED','ZS_SIGNALS_DISPATCH_ENABLED','ZS_ANALYTICS_DISPATCH_ENABLED','ZS_INTERACTIVE_POLLING_ENABLED','ZS_INTERACTIVE_REPLY_ENABLED')) { Set-Item ('Env:' + $name) 'false' }
    $out = Join-Path $runDir 'unittest.txt'
    $err = Join-Path $runDir 'unittest-stderr.txt'
    # Start-Process gives separate stdout/stderr files and a REAL exit code on Windows PowerShell 5.1.
    $p = Start-Process -FilePath 'py.exe' -ArgumentList @('-3.12', ('"'+$test+'"')) -PassThru -Wait -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err
    if ($p.ExitCode -ne 0) { throw ('SMOKE_TEST_EXIT_CODE_' + $p.ExitCode) }
    $testText = (Get-Content -LiteralPath $out -Raw -ErrorAction SilentlyContinue) + "`n" + (Get-Content -LiteralPath $err -Raw -ErrorAction SilentlyContinue)
    if ($testText -notmatch 'Ran 9 tests' -or $testText -notmatch '(?m)^OK\s*$' -or $testText -match '(?m)^FAILED') { throw 'NINE_TEST_PASS_PROOF_MISSING' }
    $tests='9/9_PASS'
    $dryOut=Join-Path $runDir 'dry-run.txt'; $dryErr=Join-Path $runDir 'dry-run-stderr.txt'
    $p2=Start-Process -FilePath 'py.exe' -ArgumentList @('-3.12', ('"'+$script+'"'), '--dry-run') -PassThru -Wait -NoNewWindow -RedirectStandardOutput $dryOut -RedirectStandardError $dryErr
    if ($p2.ExitCode -ne 0) { throw ('DRY_RUN_EXIT_CODE_' + $p2.ExitCode) }
    $dryText=Get-Content -LiteralPath $dryOut -Raw
    if ($dryText -notmatch 'DRY_RUN_PASS_NO_NETWORK_NO_SECRETS' -or $dryText -notmatch '"real_http_calls": 0' -or $dryText -notmatch '"secrets_requested": false') { throw 'DRY_RUN_NO_NETWORK_PROOF_MISSING' }
    $dry='PASS_NO_NETWORK_NO_SECRETS'
    if ((GitValue -gitArgs @('rev-parse','HEAD')) -ne $original) { throw 'ORIGINAL_HEAD_CHANGED' }
    $result='PASS'; $exitCode=0
} catch {
    $result='FAIL'; $exitCode=1
    Add-Content -LiteralPath $log -Value ('ERROR_CODE=' + $_.Exception.Message) -Encoding UTF8
} finally {
    if ($null -ne $original) {
        $current = (& git -C $Repository rev-parse HEAD 2>$null | Out-String).Trim()
        $originalUnchanged=([string]::Equals($current,$original)).ToString().ToLowerInvariant()
    }
    $summary=@(
       'STAGE05_HASH_AND_WINDOWS_RECEIPT_005',
       ('UTC_FINISHED='+(Get-Date).ToUniversalTime().ToString('o')),
       ('PINNED_HEAD='+$head),('PINNED_TREE='+$tree),('GIT_BLOB_SHA='+$blob),
       ('EXPECTED_SCRIPT_SHA256='+$expectedSha256),('RAW_GIT_SCRIPT_SHA256='+$rawGitHash),
       ('BEFORE_WORKTREE_SCRIPT_SHA256='+$beforeHash),('AFTER_WORKTREE_SCRIPT_SHA256='+$actualHash),
       ('WORKTREE_SCRIPT_RESTORED='+$restored),('CORE_AUTOCRLF='+$gitConfig),
       ('PYTHON_VERSION='+$pythonVersion),('NEW_SMOKE_TESTS='+$tests),
       ('DRY_RUN='+$dry),('LIVE_TELEGRAM_REQUESTS=0'),('SECRETS_USED=NO'),
       ('ORIGINAL_HEAD_UNCHANGED='+$originalUnchanged),('STATUS='+$result),('EXIT_CODE='+$exitCode)
    )
    Add-Content -LiteralPath $log -Value ($summary -join "`n") -Encoding UTF8
    $logHash=HashFile $log
    foreach ($item in $summary) { Write-Output $item }
    Write-Output ('LOG_SHA256='+$logHash)
    Write-Output ('LOCAL_LOG='+$log)
}
exit $exitCode