param([Parameter(Mandatory=$true)][long]$Boundary)
$ErrorActionPreference='Stop'
$source='D:\ZS-SMART-GATE\validation\OPS24-20261121-github-source'
$out='D:\ZS-SMART-GATE\validation\OPS24-20261121-full-market'
$driver='D:\ZS-SMART-GATE\validation\OPS24-20261121-full-market-driver'
$head='fda01bb5317ef2ed12697d3e6993796b2ae52d42'
$tree='2594b47632100b561dff0a0f4309e1779d91dde7'
Set-Location $source
if((git rev-parse HEAD) -cne $head -or (git rev-parse 'HEAD^{tree}') -cne $tree -or (git status --porcelain)){throw 'SOURCE_PIN_MISMATCH'}
if(Test-Path $out){throw 'FRESH_OUTPUT_REQUIRED'}
Write-Output ('BOUNDED_TEST_WAITING boundary='+$Boundary+' head='+$head)
while([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() -lt ($Boundary*1000+500)){Start-Sleep -Milliseconds 500}
if([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() -gt ($Boundary*1000+5000)){throw 'MISSED_TEST_ENTRY'}
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP;$env:PYTHONDONTWRITEBYTECODE='1'
& 'D:\ZS-SMART-GATE\.venv\Scripts\python.exe' -B scripts\ops24-bounded.py --full-market-preflight --boundary $Boundary --output $out 1>($driver+'.stdout.txt') 2>($driver+'.stderr.txt')
$code=$LASTEXITCODE
[IO.File]::WriteAllText(($driver+'.exit.txt'),[string]$code)
Write-Output ('BOUNDED_TEST_FINISHED exit='+$code)
exit $code
