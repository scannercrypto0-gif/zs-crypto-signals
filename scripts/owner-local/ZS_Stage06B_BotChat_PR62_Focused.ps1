# Stage06B exact-head owner Windows regression: Telegram Desktop bot_chat.
# No Telegram/Binance API, SQL Server connection, trading or production.
[CmdletBinding()]
param([string]$Root = 'D:\ZS-LOCAL-CI')
$ErrorActionPreference = 'Stop'
$repo = 'scannercrypto0-gif/zs-crypto-signals'
$url = 'https://github.com/scannercrypto0-gif/zs-crypto-signals.git'
$branch = 'stage06b-telegram-bot-chat-export-20261115'
$head = '2e2601df29240173590fa19e4ff323b408886124'
$tree = 'b7048a485864c9316baa823206a785019d953c50'
$run = $null
$result = [ordered]@{
    PR = 62; Head = $head; Tree = $tree
    Status = 'NOT_RUN'; Python = $null; PowerShell = $PSVersionTable.PSVersion.ToString()
    StartUTC = [DateTime]::UtcNow.ToString('o'); EndUTC = $null
    TestsObserved = $null; PassedTests = $null; ExitCode = $null
    StdoutSHA256 = $null; StderrSHA256 = $null; WorktreeClean = $null; Message = $null
}
try {
    if (!(Test-Path -LiteralPath 'D:\' -PathType Container)) { throw 'DRIVE_D_MISSING' }
    if ([IO.Path]::GetPathRoot([IO.Path]::GetFullPath($Root)) -ne 'D:\') {
        throw 'OUTPUT_MUST_USE_D'
    }
    foreach ($name in @('gh','git','py')) {
        if (!(Get-Command $name -ErrorAction SilentlyContinue)) { throw ('TOOL_MISSING_' + $name) }
    }
    $version = (& py -3.12 --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^Python 3\.12\.') { throw 'PYTHON_312_MISSING' }
    $result.Python = $version
    & gh auth setup-git | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'GITHUB_AUTH_FAILED' }
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
    $run = Join-Path $Root ('run-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-PR62')
    if (Test-Path -LiteralPath $run) { throw 'RUN_ALREADY_EXISTS' }
    New-Item -ItemType Directory -Path $run | Out-Null
    $env:TEMP = Join-Path $run 'temp'
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Path $env:TEMP | Out-Null
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:GIT_TERMINAL_PROMPT = '0'
    Write-Host "LOCAL_CI_RUN=$run"
    Write-Host "PYTHON=$version"
    $live = (& gh api "repos/$repo/pulls/62" --jq '.head.sha' 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $live -ne $head) { throw 'PR62_HEAD_DRIFT' }
    $checkout = Join-Path $run 'checkout'
    & git clone -q --depth 1 --single-branch --no-checkout --branch $branch $url $checkout
    if ($LASTEXITCODE -ne 0) { throw 'GIT_CLONE_FAILED' }
    & git -C $checkout checkout -q --detach $head
    if ($LASTEXITCODE -ne 0) { throw 'GIT_CHECKOUT_FAILED' }
    $actualHead = (& git -C $checkout rev-parse HEAD | Out-String).Trim()
    $actualTree = (& git -C $checkout rev-parse 'HEAD^{tree}' | Out-String).Trim()
    if ($actualHead -ne $head -or $actualTree -ne $tree) { throw 'PINNED_TREE_FAILED' }
    $env:PYTHONPATH = "$(Join-Path $checkout 'src');$(Join-Path $checkout 'tests')"
    $stdout = Join-Path $run 'unittest.stdout.txt'
    $stderr = Join-Path $run 'unittest.stderr.txt'
    $args = @(
        '-3.12', '-B', '-m', 'unittest', '-v',
        'test_stage06b_desktop_sql.DesktopSQLTests.test_real_desktop_bot_chat_type_analytics_and_signals',
        'test_stage06b_desktop_sql.DesktopSQLTests.test_bot_chat_still_requires_matching_export_identity',
        'test_stage06b_desktop_sql.DesktopSQLTests.test_bot_chat_missing_media_still_fails_closed',
        'test_stage06b_desktop_sql.DesktopSQLTests.test_export_must_be_a_personal_chat'
    )
    Write-Host ('TEST_PR62 : py ' + ($args -join ' '))
    $proc = Start-Process -FilePath (Get-Command py).Source -ArgumentList $args -WorkingDirectory $checkout -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $result.ExitCode = [int]$proc.ExitCode
    $result.StdoutSHA256 = (Get-FileHash -LiteralPath $stdout -Algorithm SHA256).Hash
    $result.StderrSHA256 = (Get-FileHash -LiteralPath $stderr -Algorithm SHA256).Hash
    $log = Get-Content -LiteralPath $stderr -Raw
    $matches = [regex]::Matches($log,'(?m)^Ran\s+(\d+)\s+tests?\s+in')
    if ($matches.Count -gt 0) {
        $result.TestsObserved = [int]$matches[$matches.Count-1].Groups[1].Value
    }
    $result.PassedTests = [regex]::Matches($log,'(?m)^test_.*\.\.\. ok\s*$').Count
    $statusLines = @(& git -C $checkout status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw 'WORKTREE_CHECK_FAILED' }
    $result.WorktreeClean = ($statusLines.Count -eq 0)
    if ($result.ExitCode -eq 0 -and $result.TestsObserved -eq 4 -and
        $result.PassedTests -eq 4 -and $result.WorktreeClean -and
        [regex]::IsMatch($log,'(?m)^OK\s*$')) {
        $result.Status = 'PASS'
    } else { $result.Status = 'FAIL' }
    $result.Message = 'Four Stage06B bot_chat regressions only'
}
catch {
    $result.Status = 'BLOCKED_OR_ERROR'
    $result.Message = [string]$_.Exception.Message
}
$result.EndUTC = [DateTime]::UtcNow.ToString('o')
if ($run -and (Test-Path -LiteralPath $run)) {
    [IO.File]::WriteAllText((Join-Path $run 'SUMMARY.json'), ($result | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "FINAL_REPORT=$(Join-Path $run 'SUMMARY.json')"
}
Write-Host "PR_62_STATUS=$($result.Status) TESTS=$($result.TestsObserved) EXIT=$($result.ExitCode)"
if ($result.Status -ne 'PASS') { Write-Warning "PR62_$($result.Status): $($result.Message)"; exit 1 }
Write-Host 'No live market, Telegram API, SQL Server or trading calls.'
exit 0
