# ZS Crypto Signals — Stage06 PR61 owner Windows offline focused test
# Source: GitHub tooling branch; target: exact PR61 HEAD/TREE.
# Uses gh, git, Python 3.12; output on D:. No SQL, bot, Binance, trading.
[CmdletBinding()]
param([string]$Root = 'D:\ZS-LOCAL-CI')

$ErrorActionPreference = 'Stop'
$repo = 'scannercrypto0-gif/zs-crypto-signals'
$repoUrl = 'https://github.com/scannercrypto0-gif/zs-crypto-signals.git'
$sourceBranch = 'stage06-source-bound-archive-6892206107-20261115'
$expectedHead = 'c8422f1235fbaf655d4cfeff04b4912b23724891'
$expectedTree = 'c7588bfc5a72b9bb90b332347c7f1c5dcd996c4c'
$runDir = $null
$entry = [ordered]@{
    PR = 61; Status = 'NOT_RUN'; Head = $expectedHead; Tree = $expectedTree
    Python = $null; PowerShell = $PSVersionTable.PSVersion.ToString()
    StartUTC = [DateTime]::UtcNow.ToString('o')
    EndUTC = $null; TestsObserved = $null; ExitCode = $null
    StdoutSHA256 = $null; StderrSHA256 = $null; WorktreeClean = $null; Message = $null
}
try {
    if (!(Test-Path 'D:\')) { throw 'DRIVE_D_NOT_AVAILABLE' }
    $fullRoot = [IO.Path]::GetFullPath($Root)
    if ([IO.Path]::GetPathRoot($fullRoot) -ne 'D:\') { throw 'OUTPUT_MUST_BE_ON_D' }
    foreach ($program in @('git','gh','py')) {
        if (!(Get-Command $program -ErrorAction SilentlyContinue)) {
            throw ("REQUIRED_COMMAND_MISSING_" + $program)
        }
    }
    $entry.Python = (& py -3.12 --version 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'PYTHON_312_REQUIRED' }
    & gh auth setup-git | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'GITHUB_AUTH_SETUP_FAILED' }
    New-Item -ItemType Directory -Force -Path $fullRoot | Out-Null
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
    $runDir = Join-Path $fullRoot ("run-" + $stamp + "-PR61")
    if (Test-Path -LiteralPath $runDir) { throw 'RUN_FOLDER_ALREADY_EXISTS' }
    New-Item -ItemType Directory -Path $runDir | Out-Null
    $env:TEMP = Join-Path $runDir '_temp'
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Path $env:TEMP | Out-Null
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:GIT_TERMINAL_PROMPT = '0'
    Write-Host "LOCAL_CI_RUN=$runDir"
    Write-Host "PYTHON=$($entry.Python)"
    Write-Host "=== PR61 verifying remote HEAD ==="
    $live = (& gh api "repos/$repo/pulls/61" --jq '.head.sha' 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $live -ne $expectedHead) { throw 'PR61_REMOTE_HEAD_DRIFT_OR_API_FAILURE' }
    $checkout = Join-Path $runDir 'checkout'
    & git clone -q --depth 1 --single-branch --no-checkout --branch $sourceBranch $repoUrl $checkout
    if ($LASTEXITCODE -ne 0) { throw 'GITHUB_CLONE_FAILED' }
    & git -C $checkout checkout -q --detach $expectedHead
    if ($LASTEXITCODE -ne 0) { throw 'PINNED_CHECKOUT_FAILED' }
    $actualHead = (& git -C $checkout rev-parse HEAD | Out-String).Trim()
    $actualTree = (& git -C $checkout rev-parse 'HEAD^{tree}' | Out-String).Trim()
    if ($actualHead -ne $expectedHead -or $actualTree -ne $expectedTree) {
        throw 'PINNED_HEAD_OR_TREE_MISMATCH'
    }
    $env:PYTHONPATH = "$(Join-Path $checkout 'src');$(Join-Path $checkout 'tests')"
    $stdout = Join-Path $runDir 'unittest.stdout.txt'
    $stderr = Join-Path $runDir 'unittest.stderr.txt'
    $arguments = @('-3.12','-B','-m','unittest','-v','test_stage06a_source_bound','test_stage06b_desktop_sql')
    Write-Host "TEST_PR61 : py $($arguments -join ' ')"
    $proc = Start-Process -FilePath (Get-Command py).Source -ArgumentList $arguments -WorkingDirectory $checkout -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $entry.ExitCode = [int]$proc.ExitCode
    $entry.StdoutSHA256 = (Get-FileHash -LiteralPath $stdout -Algorithm SHA256).Hash
    $entry.StderrSHA256 = (Get-FileHash -LiteralPath $stderr -Algorithm SHA256).Hash
    $rawLog = Get-Content -LiteralPath $stderr -Raw
    $found = [regex]::Matches($rawLog, '(?m)^Ran\s+(\d+)\s+tests?\s+in')
    if ($found.Count -gt 0) {
        $entry.TestsObserved = [int]$found[$found.Count-1].Groups[1].Value
    }
    $passed = [regex]::Matches($rawLog, '(?m)^test_.*\.\.\. ok\s*$').Count
    $clean = @(& git -C $checkout status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw 'GIT_STATUS_FAILED' }
    $entry.WorktreeClean = ($clean.Count -eq 0)
    $entry.Status = if ($proc.ExitCode -eq 0 -and $entry.TestsObserved -eq 31 -and
                        $passed -eq 31 -and $entry.WorktreeClean -and
                        [regex]::IsMatch($rawLog, '(?m)^OK\s*$')) { 'PASS' } else { 'FAIL' }
    $entry.Message = 'Only 14 new Stage06A and 17 new Stage06B offline tests; no old tests.'
}
catch {
    $entry.Status = 'BLOCKED_OR_ERROR'
    $entry.Message = [string]$_.Exception.Message
}
$entry.EndUTC = [DateTime]::UtcNow.ToString('o')
if ($runDir -and (Test-Path -LiteralPath $runDir)) {
    [pscustomobject]$entry | ConvertTo-Json -Depth 5 |
        Set-Content -LiteralPath (Join-Path $runDir 'SUMMARY.json') -Encoding UTF8
    Write-Host "FINAL_REPORT=$(Join-Path $runDir 'SUMMARY.json')"
}
Write-Host "PR_61_STATUS=$($entry.Status) TESTS=$($entry.TestsObserved) EXIT=$($entry.ExitCode)"
if ($entry.Status -ne 'PASS') {
    Write-Warning "PR61_$($entry.Status): $($entry.Message)"
    exit 1
}
Write-Host 'No live market, Telegram, SQL Server or trading calls.'
exit 0
