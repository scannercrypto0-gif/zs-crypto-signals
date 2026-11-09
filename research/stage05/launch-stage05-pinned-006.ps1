# ZS-STAGE05-LIVE-SMOKE-PINNED-LAUNCH-006
# PM REVIEW FIRST. Offline preparation is default; -EnableLive is an explicit post-PM opt-in.
# Owner Windows PowerShell 5.1 only. NO live Telegram in default mode.
[CmdletBinding()]
param(
    [string]$Repository = 'D:\ZS Crypto Signals Latest Version',
    [string]$Root = 'D:\ZS_STAGE05_LOCAL_TEMP',
    [switch]$EnableLive
)
$ErrorActionPreference = 'Stop'
$head = 'a15f3399233f211d6b73378d9b0b7f0d78c6a41d'
$tree = '8566977aeacd38ef59ba120f4f36318b1d382f16'
$blob = 'fc1605cba716edd591eb7352e86acd584fc27c20'
$scriptHash = '255c8a8213171448ef6631113cc28702d99e30f46b3c383c2a5c75c38f98b9a7'
$branch = 'stage05-real-telegram-transport-disabled-20261109'
$relative = 'research/stage05/zs05_three_bot_smoke_windows.py'
$scriptRelative = 'research\stage05\zs05_three_bot_smoke_windows.py'
$approvedRemote = 'https://github.com/scannercrypto0-gif/zs-crypto-signals.git'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')
$session = Join-Path $Root ('zs05-pinned-launch-006-' + $stamp)
$clone = Join-Path $session 'isolated-clone'
$script = Join-Path $clone $scriptRelative
$raw = Join-Path $session 'raw-git-script.py'
$receipt = Join-Path $session 'preflight-receipt.txt'
$original = $null
$originalBranch = $null
$originalConfigHash = $null
$originalAfter = 'UNKNOWN'
$originalBranchUnchanged = 'UNKNOWN'
$originalConfigUnchanged = 'UNKNOWN'
$mode = 'PREPARE_ONLY_NO_TELEGRAM'
$preflight = 'FAIL'
$code = 1
$actualBlobHash = 'NOT_CHECKED'
$checkoutHash = 'NOT_CHECKED'
$restored = 'NO'
$python = 'NOT_CHECKED'
$dry = 'NOT_RUN'
$cloneHead = 'NOT_CHECKED'
$cloneTree = 'NOT_CHECKED'
$cloneBranch = 'NOT_CHECKED'
$cloneRemoteBranch = 'NOT_CHECKED'
$source = 'NOT_CHECKED'
$liveStarted = $false
function GitRead([string[]]$GitArgs) {
    $output = & git @GitArgs 2>$null
    if ($LASTEXITCODE -ne 0) { throw ('GIT_CHECK_FAILED: ' + ($GitArgs -join ' ')) }
    return (($output | Out-String).Trim())
}
function HashFile([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Native([string[]]$CommandArgs) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & git @CommandArgs 2>&1 | Out-Null
        $nativeCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    if ($nativeCode -ne 0) { throw ('GIT_NATIVE_FAILED: ' + ($CommandArgs -join ' ')) }
}
try {
    if (-not [string]::Equals([System.IO.Path]::GetPathRoot($Root), 'D:\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'D_DRIVE_ROOT_REQUIRED' }
    if (-not [string]::Equals([System.IO.Path]::GetPathRoot($Repository), 'D:\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'D_DRIVE_REPO_REQUIRED' }
    if (-not (Test-Path -LiteralPath $Repository -PathType Container)) { throw 'ORIGINAL_REPO_NOT_FOUND' }
    $original = GitRead -GitArgs @('-C', $Repository, 'rev-parse', 'HEAD')
    $originalBranch = GitRead -GitArgs @('-C', $Repository, 'rev-parse', '--abbrev-ref', 'HEAD')
    $originalConfigPath = Join-Path $Repository '.git\config'
    if (-not (Test-Path -LiteralPath $originalConfigPath -PathType Leaf)) { throw 'STANDARD_ORIGINAL_CONFIG_REQUIRED' }
    $originalConfigHash = HashFile $originalConfigPath
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) { New-Item -ItemType Directory -Path $Root -Force | Out-Null }
    New-Item -ItemType Directory -Path $session -ErrorAction Stop | Out-Null
    # --no-hardlinks creates an independent .git object database and independent refs.
    # No remote network is needed: the pinned commit was fetched in the successful prior Windows receipt.
    Native -CommandArgs @('clone', '--no-hardlinks', '--no-checkout', '--origin', 'origin', '--', $Repository, $clone)
    $cloneGit = Join-Path $clone '.git'
    if (-not (Test-Path -LiteralPath $cloneGit -PathType Container)) { throw 'SEPARATE_GIT_DIR_REQUIRED' }
    $source = GitRead -GitArgs @('-C', $clone, 'remote', 'get-url', 'origin')
    # Local clone origin points to original path; replace only the ISOLATED clone remote URL with canonical GitHub URL.
    Native -CommandArgs @('-C', $clone, 'remote', 'set-url', 'origin', $approvedRemote)
    if ((GitRead -GitArgs @('-C', $clone, 'remote', 'get-url', 'origin')) -ne $approvedRemote) { throw 'ISOLATED_REMOTE_URL_NOT_CANONICAL' }
    if ((GitRead -GitArgs @('-C', $clone, 'rev-parse', ($head + '^{commit}'))) -ne $head) { throw 'APPROVED_COMMIT_NOT_PRESENT_LOCALLY' }
    $cloneTree = GitRead -GitArgs @('-C', $clone, 'rev-parse', ($head + '^{tree}'))
    if ($cloneTree -ne $tree) { throw 'APPROVED_TREE_SHA_MISMATCH' }
    if ((GitRead -GitArgs @('-C', $clone, 'rev-parse', ($head + ':' + $relative))) -ne $blob) { throw 'APPROVED_GIT_BLOB_MISMATCH' }
    # Branch and origin/* ref are scoped to the isolated .git only, not the original repository.
    Native -CommandArgs @('-C', $clone, 'branch', $branch, $head)
    Native -CommandArgs @('-C', $clone, 'update-ref', ('refs/remotes/origin/' + $branch), $head)
    Native -CommandArgs @('-C', $clone, 'checkout', '--force', $branch)
    $cloneHead = GitRead -GitArgs @('-C', $clone, 'rev-parse', 'HEAD')
    $cloneBranch = GitRead -GitArgs @('-C', $clone, 'rev-parse', ('refs/heads/' + $branch))
    $cloneRemoteBranch = GitRead -GitArgs @('-C', $clone, 'rev-parse', ('refs/remotes/origin/' + $branch))
    if ($cloneHead -ne $head -or $cloneBranch -ne $head -or $cloneRemoteBranch -ne $head) { throw 'ISOLATED_PINNED_BRANCH_REFS_MISMATCH' }
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw 'APPROVED_SCRIPT_MISSING' }
    $checkoutHash = HashFile $script
    # Use cmd.exe native binary redirect: PowerShell 5.1 redirects native stdout as text and may transcode bytes.
    $command = 'git -C "' + $clone + '" show ' + $head + ':' + $relative + ' > "' + $raw + '"'
    & cmd.exe /d /s /c $command
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $raw -PathType Leaf)) { throw 'PINNED_RAW_GIT_SHOW_FAILED' }
    $actualBlobHash = HashFile $raw
    if ($actualBlobHash -ne $scriptHash -or ([System.IO.FileInfo]::new($raw)).Length -ne 22925) { throw 'PINNED_RAW_SCRIPT_SHA_OR_SIZE_MISMATCH' }
    if ((GitRead -GitArgs @('-C', $clone, 'hash-object', '--no-filters', $raw)) -ne $blob) { throw 'PINNED_RAW_SCRIPT_BLOB_MISMATCH' }
    if ($checkoutHash -ne $scriptHash) {
        [System.IO.File]::WriteAllBytes($script, [System.IO.File]::ReadAllBytes($raw))
        $restored = 'YES_INSIDE_ISOLATED_CLONE_ONLY'
    }
    if ((HashFile $script) -ne $scriptHash -or ([System.IO.FileInfo]::new($script)).Length -ne 22925) { throw 'EXECUTABLE_SCRIPT_BYTES_MISMATCH' }
    if ((GitRead -GitArgs @('-C', $clone, 'hash-object', '--no-filters', $script)) -ne $blob) { throw 'EXECUTABLE_BLOB_MISMATCH' }
    $python = (& py -3.12 --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $python -notmatch '^Python 3\.12\.') { throw 'PYTHON_312_REQUIRED' }
    # Fresh no-network dry-run only; no 9/9 tests, no secrets.
    $dryStdout = Join-Path $session 'dry-run.txt'
    $dryStderr = Join-Path $session 'dry-run-stderr.txt'
    $p = Start-Process -FilePath 'py.exe' -ArgumentList @('-3.12', ('"' + $script + '"'), '--dry-run') -PassThru -Wait -NoNewWindow -RedirectStandardOutput $dryStdout -RedirectStandardError $dryStderr
    if ($p.ExitCode -ne 0) { throw ('DRY_RUN_EXIT_' + $p.ExitCode) }
    $dryText = Get-Content -LiteralPath $dryStdout -Raw
    if ($dryText -notmatch 'DRY_RUN_PASS_NO_NETWORK_NO_SECRETS' -or $dryText -notmatch '"real_http_calls":\s*0' -or $dryText -notmatch '"secrets_requested":\s*false' -or $dryText -notmatch '"maximum_api_calls":\s*17') { throw 'DRY_RUN_PROOF_MISSING' }
    $dry = 'PASS_NO_NETWORK_NO_SECRETS'
    # Check the actual Python verify_pins() path before any secrets: it requires the origin/* remote-tracking ref.
    if ($cloneRemoteBranch -ne $head) { throw 'SCRIPT_REQUIRED_REMOTE_TRACKING_REF_MISMATCH' }
    if ((GitRead -GitArgs @('-C', $Repository, 'rev-parse', 'HEAD')) -ne $original) { throw 'ORIGINAL_HEAD_CHANGED' }
    if ((GitRead -GitArgs @('-C', $Repository, 'rev-parse', '--abbrev-ref', 'HEAD')) -ne $originalBranch) { throw 'ORIGINAL_BRANCH_CHANGED' }
    if ((HashFile $originalConfigPath) -ne $originalConfigHash) { throw 'ORIGINAL_CONFIG_CHANGED' }
    $preflight = 'PASS'
    $code = 0
} catch {
    $code = 1
    $failure = $_.Exception.Message
    Write-Output ('PREPARATION_ERROR=' + $failure)
} finally {
    if ($null -ne $original) {
        try {
            $originalAfter = ([string]::Equals((GitRead -GitArgs @('-C', $Repository, 'rev-parse', 'HEAD')), $original)).ToString().ToLowerInvariant()
            $originalBranchUnchanged = ([string]::Equals((GitRead -GitArgs @('-C', $Repository, 'rev-parse', '--abbrev-ref', 'HEAD')), $originalBranch)).ToString().ToLowerInvariant()
            $originalConfigUnchanged = ([string]::Equals((HashFile $originalConfigPath), $originalConfigHash)).ToString().ToLowerInvariant()
        } catch { $originalAfter = 'UNKNOWN'; $originalBranchUnchanged = 'UNKNOWN'; $originalConfigUnchanged = 'UNKNOWN' }
    }
    $lines = @(
        'STAGE05_PINNED_LAUNCHER_006',
        ('UTC_FINISHED=' + (Get-Date).ToUniversalTime().ToString('o')),
        ('APPROVED_HEAD=' + $head), ('APPROVED_TREE=' + $tree), ('APPROVED_GIT_BLOB=' + $blob),
        ('APPROVED_SCRIPT_SHA256=' + $scriptHash), ('RAW_GIT_SHOW_SHA256=' + $actualBlobHash),
        ('ISOLATED_CHECKOUT_SHA256_BEFORE_RESTORE=' + $checkoutHash), ('ISOLATED_RESTORED=' + $restored),
        ('ISOLATED_HEAD=' + $cloneHead), ('ISOLATED_LOCAL_BRANCH=' + $cloneBranch),
        ('ISOLATED_ORIGIN_TRACKING_REF=' + $cloneRemoteBranch), ('PYTHON_VERSION=' + $python),
        ('DRY_RUN=' + $dry), ('ORIGINAL_HEAD_UNCHANGED=' + $originalAfter),
        ('ORIGINAL_BRANCH_UNCHANGED=' + $originalBranchUnchanged), ('ORIGINAL_CONFIG_UNCHANGED=' + $originalConfigUnchanged),
        ('PREFLIGHT_STATUS=' + $preflight), ('REAL_API_CALLS_FROM_LAUNCHER_PREPARATION=0'),
        ('LIVE_LAUNCH_REQUESTED=' + $EnableLive.ToString().ToLowerInvariant()),
        ('EXIT_CODE=' + $code)
    )
    foreach ($line in $lines) { Write-Output $line }
    if (Test-Path -LiteralPath $session -PathType Container) {
        [System.IO.File]::WriteAllText($receipt, ($lines -join "`r`n") + "`r`n", (New-Object System.Text.UTF8Encoding($false)))
        Write-Output ('PREFLIGHT_RECEIPT_SHA256=' + (HashFile $receipt))
        Write-Output ('PREFLIGHT_RECEIPT_PATH=' + $receipt)
    }
}
if ($code -ne 0) { exit $code }
if (-not $EnableLive) {
    Write-Output 'PREPARE_ONLY_COMPLETE_PM_REVIEW_REQUIRED_NO_LIVE_REQUESTS'
    exit 0
}
# This gate is deliberately separate from the preflight. Abort without a perfect SHA string.
Write-Output 'OWNER MANUAL GATE: PM must explicitly accept this exact launcher SHA before live use.'
Write-Output 'One single TEST ONLY session, <=17 Telegram API requests; no retries if interrupted.'
$pmGate = Read-Host 'Type exact PM ACCEPTED LAUNCHER 006 to continue or press Enter to stop'
if ($pmGate -cne 'PM ACCEPTED LAUNCHER 006') { Write-Output 'SAFE_STOP_BEFORE_SECRETS_OR_NETWORK'; exit 0 }
$headGate = Read-Host 'Type EXACT approved 40-char smoke commit SHA to permit live prompt'
if ($headGate -cne $head) { Write-Output 'SAFE_STOP_SHA_CONFIRMATION_MISMATCH'; exit 0 }
# No extra token handling: approved Python script prompts owner-only via getpass after its own verify_pins.
# No secrets and no chat identifiers in the launcher, logs, or command-line.
Write-Output 'Python prompts three hidden tokens and account A, B, C=A IDs. Do not paste them into GitHub/chat.'
Write-Output 'After outbound 05A/05B: send btcusdt privately from A and B to 05C; return and press Enter once.'
Write-Output 'Expected seven outputs: 05A to A/B (2), 05B C=A summary (1) and JSON documents (2), 05C replies A/B (2).'
$launchArgs = @('-3.12', $script, '--execute', '--repo', $clone, '--head-sha', $head, '--tree-sha', $tree, '--script-sha256', $scriptHash)
& py @launchArgs
$smokeExit = $LASTEXITCODE
Write-Output ('OWNER_SMOKE_PROCESS_EXIT_CODE=' + $smokeExit)
Write-Output 'NO_AUTOMATIC_RETRY_OR_REPEAT_EXECUTION'
exit $smokeExit
