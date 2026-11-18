<#
ORDER007 Windows-owner acceptance. Full local test suite + actual raw byte hashes.
Does not install, start live connections, enable tasks or modify project source.
#>
[CmdletBinding()]
param(
  [string]$Root='D:\ZS-SMART-GATE',
  [string]$ExtraDependenciesPath=''
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if ($Root -ine 'D:\ZS-SMART-GATE') { throw 'ORDER007_D_ONLY_FIXED_ROOT' }
$repo=Join-Path $Root 'repo'
$python=Join-Path $Root '.venv\Scripts\python.exe'
$manager=Join-Path $repo 'scripts\order007-windows.ps1'
if (-not (Test-Path $python) -or -not (Test-Path $manager)) {
  throw 'RUN_ORDER007_INSTALL_FIRST'
}
if ($ExtraDependenciesPath) {
  if ($ExtraDependenciesPath -notmatch '^[dD]:\\') { throw 'DEPENDENCIES_MUST_BE_ON_D' }
  if (-not (Test-Path -LiteralPath $ExtraDependenciesPath -PathType Container)) {
    throw 'DEPENDENCY_DIRECTORY_MISSING'
  }
}
& $manager -Action Verify -Root $Root
if ($LASTEXITCODE -ne 0) { throw 'INSTALL_VERIFY_FAILED' }
$head=((& git -C $repo rev-parse HEAD) | Out-String).Trim()
$tree=((& git -C $repo rev-parse 'HEAD^{tree}') | Out-String).Trim()
if ($head -notmatch '^[a-f0-9]{40}$' -or $tree -notmatch '^[a-f0-9]{40}$') {
  throw 'GIT_SOURCE_IDENTITY_INVALID'
}
$dir=Join-Path $Root ('validation\PR71-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $dir -ErrorAction Stop | Out-Null
$env:TEMP=Join-Path $Root 'temp'
$env:TMP=$env:TEMP
$env:PIP_CACHE_DIR=Join-Path $Root 'cache'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Join-Path $repo 'src')
if ($ExtraDependenciesPath) { $env:PYTHONPATH += ';'+$ExtraDependenciesPath }
$stdout=Join-Path $dir 'unittest.stdout.raw.txt'
$stderr=Join-Path $dir 'unittest.stderr.raw.txt'
$started=[DateTime]::UtcNow.ToString('o')
$proc=Start-Process -FilePath $python -ArgumentList @('-B','-m','unittest','discover','-s','tests','-v') -WorkingDirectory $repo -PassThru -Wait -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$exitCode=[int]$proc.ExitCode
$finished=[DateTime]::UtcNow.ToString('o')
$log=Get-Content -LiteralPath $stderr -Raw -ErrorAction Stop
$matches=[regex]::Matches($log, 'Ran\s+(\d+)\s+tests?\s+in\s+')
$testCount=if($matches.Count){ [int]$matches[$matches.Count-1].Groups[1].Value } else { $null }
$skipped=if($log -match 'skipped=(\d+)'){[int]$Matches[1]}else{0}
$proven=($exitCode -eq 0 -and $log -match '(?m)^OK(?:\s|$)' -and $null -ne $testCount -and $skipped -eq 0)
$afterHead=((& git -C $repo rev-parse HEAD) | Out-String).Trim()
$afterTree=((& git -C $repo rev-parse 'HEAD^{tree}') | Out-String).Trim()
$dirty=((& git -C $repo status --porcelain) | Out-String).Trim()
& git -C $repo fsck --no-reflogs --connectivity-only *> (Join-Path $dir 'git-fsck.txt')
$fsckExit=$LASTEXITCODE
$restored=$false
if ($proven -and $head -eq $afterHead -and $tree -eq $afterTree -and -not $dirty -and $fsckExit -eq 0) {
  & $manager -Action Restore -Root $Root *> (Join-Path $dir 'restore.txt')
  $restored=($? -and $LASTEXITCODE -eq 0)
}
$receipt=[ordered]@{
  schema='zs.order007.windows-acceptance.v1'
  tested_head=$head; tested_tree=$tree
  started_utc=$started; finished_utc=$finished
  python=((& $python -c 'import platform; print(platform.python_version())') | Out-String).Trim()
  tests=$testCount; skipped=$skipped; exit=$exitCode
  test_pass=$proven
  clean_head=($head -eq $afterHead)
  clean_tree=($tree -eq $afterTree)
  clean_worktree=(!$dirty)
  fsck_exit=$fsckExit
  restore_verified=$restored
  stdout_sha256=(Get-FileHash -LiteralPath $stdout -Algorithm SHA256).Hash.ToLowerInvariant()
  stderr_sha256=(Get-FileHash -LiteralPath $stderr -Algorithm SHA256).Hash.ToLowerInvariant()
  local_path=$dir
  windows_local_only=$true
  live_run_executed=$false
  soak_24h_executed=$false
  qualified_market_signal=$false
}
$receiptPath=Join-Path $dir 'receipt.json'
[IO.File]::WriteAllText($receiptPath, ($receipt|ConvertTo-Json -Depth 8)+[Environment]::NewLine, [Text.UTF8Encoding]::new($false))
$receipt | ConvertTo-Json -Depth 8
if(-not ($proven -and $restored)) {
  throw "WINDOWS_ACCEPTANCE_NOT_PROVEN: see $receiptPath"
}
