[CmdletBinding()]
param(
    [ValidateSet('Plan','Install','Status','Stop','Uninstall')][string]$Action = 'Plan',
    [string]$PythonPath,
    [string]$WorkingDirectory,
    [string]$TaskName = 'ZS-WindowsRunner-DryRun-Pilot',
    [switch]$OptIn
)
$ErrorActionPreference = 'Stop'
$taskPath = '\ZS-Offline-Pilot\'
if ($TaskName -notmatch '^ZS-WindowsRunner-[A-Za-z0-9-]+$') { throw 'Pilot task name required' }
if ($Action -in @('Status','Stop','Uninstall')) {
    $task = Get-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Action -eq 'Status') {
        [pscustomobject]@{ UTC=[DateTime]::UtcNow.ToString('o'); Timezone=(Get-TimeZone).Id; Account=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name; Task=$task }
        if ($task) { Get-ScheduledTaskInfo -InputObject $task }
    } elseif ($task) {
        if ($task.Description -ne 'ZS offline-only Windows pilot; no LIVE transport') { throw 'Refusing unrelated task' }
        Disable-ScheduledTask -InputObject $task | Out-Null
        Stop-ScheduledTask -InputObject $task
        if ($Action -eq 'Uninstall') { Unregister-ScheduledTask -InputObject $task -Confirm:$false }
    }
    return
}
if (-not $PythonPath -or -not $WorkingDirectory) { throw 'Absolute venv PythonPath and WorkingDirectory required' }
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
$WorkingDirectory = (Resolve-Path -LiteralPath $WorkingDirectory).Path
if (-not (Test-Path -LiteralPath (Join-Path (Split-Path (Split-Path $PythonPath)) 'pyvenv.cfg'))) { throw 'Use a venv Python executable' }
if ($PythonPath.Contains('"') -or $WorkingDirectory.Contains('"')) { throw 'Invalid path' }
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskAction = New-ScheduledTaskAction -Execute $PythonPath -Argument '-m zs_smart_gate.windows_runner --dry-run --once' -WorkingDirectory $WorkingDirectory
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Minutes 10)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 30) -Disable
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$definition = New-ScheduledTask -Action $taskAction -Trigger $trigger -Settings $settings -Principal $principal -Description 'ZS offline-only Windows pilot; no LIVE transport'
if ($Action -eq 'Plan') { $definition; return }
if (-not $OptIn) { throw 'Install requires -OptIn; task stays disabled. No activation command is provided.' }
$existing = Get-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.Description -ne $definition.Description) { throw 'Refusing unrelated task' }
    $xml = [xml](Export-ScheduledTask -InputObject $existing)
    if ($xml.Task.Actions.Exec.Command -ne $PythonPath -or $xml.Task.Actions.Exec.WorkingDirectory -ne $WorkingDirectory -or $xml.Task.Actions.Exec.Arguments -ne $taskAction.Arguments) { throw 'Existing configuration differs; uninstall explicitly first' }
    Disable-ScheduledTask -InputObject $existing | Out-Null
    return
}
Register-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -InputObject $definition | Out-Null
