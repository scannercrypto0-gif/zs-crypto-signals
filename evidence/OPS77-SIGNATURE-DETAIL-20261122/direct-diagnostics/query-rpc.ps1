$ErrorActionPreference='Stop'
$r='D:\ZS-SMART-GATE\validation\OPS77-signature-direct-diagnostic-20261122'
$env:PSModulePath=Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\Modules'
$env:TEMP='D:\ZS-SMART-GATE\temp';$env:TMP=$env:TEMP;$env:PSModuleAnalysisCachePath=Join-Path $r 'rpc-module-cache'
$rows=@();foreach($kind in @('status','source','configuration')){
 $text=(& (Join-Path ([Environment]::SystemDirectory) 'w32tm.exe') /query (('/'+$kind)) /verbose 2>&1|Out-String)
 $rows+=@{kind=$kind;exit=$LASTEXITCODE;stdout=$text}
}
[IO.File]::WriteAllText((Join-Path $r 'direct-rpc.json'),($rows|ConvertTo-Json -Depth 5))
