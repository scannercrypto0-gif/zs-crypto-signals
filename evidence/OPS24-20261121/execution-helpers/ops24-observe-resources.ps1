param([long]$Boundary=1795255200)
$ErrorActionPreference='Stop'
$rows=[Collections.Generic.List[object]]::new()
while([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() -lt $Boundary*1000){Start-Sleep -Milliseconds 500}
$until=$Boundary+125
while([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() -le $until){
 $all=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='powershell.exe' OR Name='w32tm.exe' OR Name='sc.exe'")
 $roots=@($all|Where-Object{$_.Name -eq 'python.exe' -and $_.CommandLine -like '*ops24-bounded.py*' -and $_.CommandLine -like '*OPS24-20261121-full-market*'})
 $ids=[Collections.Generic.HashSet[int]]::new()
 foreach($p in $roots){$null=$ids.Add([int]$p.ProcessId)}
 for($depth=0;$depth -lt 4;$depth++){foreach($p in $all){if($ids.Contains([int]$p.ParentProcessId)){$null=$ids.Add([int]$p.ProcessId)}}}
 $processes=@()
 foreach($id in $ids){$p=Get-Process -Id $id -ErrorAction SilentlyContinue;if($p){$processes+=@{pid=$id;name=$p.ProcessName;cpu_seconds=$p.CPU;working_set_bytes=$p.WorkingSet64;private_bytes=$p.PrivateMemorySize64}}}
 $rows.Add(@{utc=[DateTime]::UtcNow.ToString('o');processes=$processes})
 if((Test-Path 'D:\ZS-SMART-GATE\validation\OPS24-20261121-full-market-driver.exit.txt') -and -not $roots.Count){break}
 Start-Sleep -Seconds 2
}
$record=[ordered]@{scope='EXTERNAL_2_SECOND_PROCESS_TREE_SAMPLES_NOT_GLOBAL_CPU_OR_MEMORY_PROOF';boundary=$Boundary;rows=$rows}
[IO.File]::WriteAllText('D:\ZS-SMART-GATE\validation\OPS24-20261121-full-market-resources.json',($record|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
Write-Output ('RESOURCE_SAMPLES_RECORDED='+$rows.Count)
