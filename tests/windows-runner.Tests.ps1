param([Parameter(Mandatory)][string]$PythonPath)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot
$runner = Join-Path $repo 'scripts/windows-runner.ps1'
$definition = & $runner -Action Plan -PythonPath $PythonPath -WorkingDirectory $repo
if ($definition.Settings.Enabled -or $definition.Settings.MultipleInstances -ne 2) { throw 'Disabled/IgnoreNew invariant' }
if ($definition.Principal.RunLevel -ne 0 -or $definition.Principal.LogonType -ne 3) { throw 'Limited interactive invariant' }
if ($definition.Settings.StartWhenAvailable -or $definition.Settings.WakeToRun) { throw 'No wake/catch-up invariant' }
if ($definition.Actions.Arguments -ne '-m zs_smart_gate.windows_runner --dry-run --once') { throw 'Offline command invariant' }
if ($definition.Triggers.Repetition.Interval -ne 'PT1M' -or $definition.Triggers.Repetition.Duration -ne 'PT10M') { throw 'Bounded trigger invariant' }
# Mock only persistence cmdlets. Real TaskScheduler CIM definitions above are used.
# This test never registers, enables, starts or deletes an OS task.
$global:ZSRunnerTestState = @{stored=$null; registrations=0}
function Get-ScheduledTask { param($TaskPath,$TaskName) $global:ZSRunnerTestState.stored }
function Register-ScheduledTask { param($TaskPath,$TaskName,$InputObject) $global:ZSRunnerTestState.stored=$InputObject; $global:ZSRunnerTestState.registrations++ }
function Disable-ScheduledTask { param($InputObject) $InputObject.Settings.Enabled=$false }
function Stop-ScheduledTask { param($InputObject) }
function Unregister-ScheduledTask { param($InputObject,[switch]$Confirm) $global:ZSRunnerTestState.stored=$null }
function Export-ScheduledTask {
    param($InputObject)
    $command=[System.Security.SecurityElement]::Escape($InputObject.Actions.Execute)
    $working=[System.Security.SecurityElement]::Escape($InputObject.Actions.WorkingDirectory)
    "<Task><Actions><Exec><Command>$command</Command><WorkingDirectory>$working</WorkingDirectory><Arguments>-m zs_smart_gate.windows_runner --dry-run --once</Arguments></Exec></Actions></Task>"
}
$rejected=$false
try { & $runner -Action Install -PythonPath $PythonPath -WorkingDirectory $repo } catch { $rejected=$true }
if (-not $rejected -or $global:ZSRunnerTestState.registrations) { throw 'Install opt-in invariant' }
& $runner -Action Install -OptIn -PythonPath $PythonPath -WorkingDirectory $repo
& $runner -Action Install -OptIn -PythonPath $PythonPath -WorkingDirectory $repo
if ($global:ZSRunnerTestState.registrations -ne 1 -or $global:ZSRunnerTestState.stored.Settings.Enabled) { throw 'Install idempotence invariant' }
& $runner -Action Stop
& $runner -Action Uninstall
& $runner -Action Uninstall
if ($global:ZSRunnerTestState.stored) { throw 'Uninstall idempotence invariant' }
'PASS: native disabled TaskScheduler definition; mocked install/stop/uninstall idempotence; zero OS registrations'
