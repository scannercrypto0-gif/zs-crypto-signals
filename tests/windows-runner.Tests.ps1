param([Parameter(Mandatory)][string]$PythonPath)
$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot
$runner=Join-Path $repo 'scripts/windows-runner.ps1'
. (Join-Path $repo 'scripts/windows-storage.ps1')
# Persist test files only on D. No actual OS registration in this offline suite.
$testRoot=Join-Path $env:TEMP ('zs-operations-'+[guid]::NewGuid().ToString('N'))
if([IO.Path]::GetPathRoot($testRoot) -ne 'D:\') { throw 'D-only test temporary directory required' }
New-Item -ItemType Directory -Path $testRoot | Out-Null
try {
    $config=Join-Path $testRoot 'deployment.json'
    '{}' | Set-Content -LiteralPath $config
    @{status='OS_CLOCK_VERIFIED';measuredUtc=[DateTimeOffset]::UtcNow.ToString('o');source='MOCK_ONLY';sampleCount=3;maxAbsOffsetSeconds=0.1;syncAgeSeconds=2} | ConvertTo-Json | Set-Content (Join-Path $testRoot 'clock-proof.json')
    $params=@{PythonPath=$PythonPath;WorkingDirectory=$repo;StateDirectory=$testRoot;LogDirectory=$testRoot;ConfigPath=$config;ConfigSha=('a'*64)}
    foreach($bad in @('C:\Windows','relative','\\server\share','D:relative')) {
        $blocked=$false
        try { Assert-DPath $bad | Out-Null } catch { $blocked=$true }
        if(-not $blocked) { throw 'Outside-D path accepted' }
    }
    $definition=& $runner -Action Plan @params
    if($definition.Settings.Enabled -or $definition.Settings.MultipleInstances -ne 2) { throw 'Disabled/IgnoreNew' }
    if($definition.Settings.StartWhenAvailable -or $definition.Settings.WakeToRun) { throw 'Catch-up/wake disabled' }
    if($definition.Principal.RunLevel -ne 0 -or $definition.Principal.LogonType -ne 3) { throw 'Limited interactive required' }
    if($definition.Triggers.Repetition.Duration -ne 'P1D') { throw '24-hour finite lease required' }
    if($definition.Actions.Arguments -notlike '*--dry-run --once' -or $definition.Actions.Arguments -notlike '*--state-dir*') { throw 'Explicit safe arguments' }
    $global:ZSRunnerTestState=@{stored=$null;registrations=0}
    function Get-ScheduledTask { param($TaskPath,$TaskName) $global:ZSRunnerTestState.stored }
    function Register-ScheduledTask { param($TaskPath,$TaskName,$InputObject) $global:ZSRunnerTestState.stored=$InputObject; $global:ZSRunnerTestState.registrations++ }
    function Disable-ScheduledTask { param($InputObject) $InputObject.Settings.Enabled=$false }
    function Enable-ScheduledTask { param($InputObject) $InputObject.Settings.Enabled=$true }
    function Stop-ScheduledTask { param($InputObject) }
    function Unregister-ScheduledTask { param($InputObject,[switch]$Confirm) $global:ZSRunnerTestState.stored=$null }
    function Get-Service { param($Name) [pscustomobject]@{Status='Running'} }
    function Get-WinEvent { param($ListLog) [pscustomobject]@{IsEnabled=$true} }
    function Export-ScheduledTask {
        param($InputObject)
        $command=[Security.SecurityElement]::Escape($InputObject.Actions.Execute)
        $working=[Security.SecurityElement]::Escape($InputObject.Actions.WorkingDirectory)
        $arguments=[Security.SecurityElement]::Escape($InputObject.Actions.Arguments)
        "<Task><Actions><Exec><Command>$command</Command><WorkingDirectory>$working</WorkingDirectory><Arguments>$arguments</Arguments></Exec></Actions></Task>"
    }
    $blocked=$false
    try { & $runner -Action Install @params } catch { $blocked=$true }
    if(-not $blocked) { throw 'Missing opt-in accepted' }
    & $runner -Action Install -OptIn @params
    & $runner -Action Install -OptIn @params
    if($global:ZSRunnerTestState.registrations -ne 1) { throw 'Install not idempotent' }
    & $runner -Action Enable -OptIn @params
    & $runner -Action Enable -OptIn @params
    if(-not $global:ZSRunnerTestState.stored.Settings.Enabled) { throw 'Enable failed' }
    & $runner -Action Disable
    & $runner -Action Disable
    if($global:ZSRunnerTestState.stored.Settings.Enabled) { throw 'Disable failed' }
    & $runner -Action Uninstall
    & $runner -Action Uninstall
    if($global:ZSRunnerTestState.stored) { throw 'Uninstall failed' }
    function Get-Volume { param($DriveLetter) throw 'D_VOLUME_UNAVAILABLE' }
    $blocked=$false
    try { Assert-DPath $testRoot | Out-Null } catch { $blocked=$true }
    if(-not $blocked) { throw 'Missing D accepted' }
    Remove-Item Function:\Get-Volume
    function Get-Item { param($LiteralPath,[switch]$Force) [pscustomobject]@{FullName=$LiteralPath;Attributes=[IO.FileAttributes]::ReparsePoint} }
    $blocked=$false
    try { Assert-DPath $testRoot | Out-Null } catch { $blocked=$true }
    if(-not $blocked) { throw 'Junction accepted' }
    Remove-Item Function:\Get-Item
    'PASS native definition + mocked lifecycle; no OS registration; D-only test files'
} finally {
    $resolved=[IO.Path]::GetFullPath($testRoot)
    if($resolved.StartsWith([IO.Path]::GetFullPath($env:TEMP)+'\') -and [IO.Path]::GetPathRoot($resolved) -eq 'D:\') {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    Remove-Variable ZSRunnerTestState -Scope Global -ErrorAction SilentlyContinue
}
