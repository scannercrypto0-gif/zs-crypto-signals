# OPS77-GATE2F-EVIDENCE-CUSTODY-REVIEW-001
# Windows PowerShell 5.1; nonproduction read-only observer.
# Never starts/stops/disables tasks, changes STOP, reboots, or touches market services.
[CmdletBinding()]
param(
    [ValidateSet('PRECHECK','VERIFY')]
    [string]$Mode = 'PRECHECK',
    [string]$TaskName = 'ZS-SmartGate-OPS24-7ae3882535',
    [string]$OutputDirectory = 'D:\ZS-SMART-GATE\validation\OPS77-GATE2F-READONLY-20261123'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-TextSha256 {
    param([string]$Text)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        return ([BitConverter]::ToString($algorithm.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally { $algorithm.Dispose() }
}
function Get-FileSha256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Write-JsonFile {
    param([string]$Path, $Object)
    $json = ConvertTo-Json -InputObject $Object -Depth 12
    [System.IO.File]::WriteAllText($Path, ($json + [Environment]::NewLine), (New-Object System.Text.UTF8Encoding($false)))
}

if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -lt 1) {
    throw 'REQUIRES_WINDOWS_POWERSHELL_5_1'
}
if ($Mode -eq 'VERIFY') {
    $manifestPath = Join-Path $OutputDirectory 'manifest.json'
    $dataPath = Join-Path $OutputDirectory 'gate2f-safe-observations.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf) -or -not (Test-Path -LiteralPath $dataPath -PathType Leaf)) {
        throw 'VERIFY_HOLD_MISSING_FILE'
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $actual = Get-FileSha256 -Path $dataPath
    if ($actual -cne [string]$manifest.data_sha256) { throw 'VERIFY_HOLD_SHA256_MISMATCH' }
    Write-Output ('VERIFY_LOCAL_SHA256_PASS data_sha256=' + $actual)
    exit 0
}

# Avoid overwriting earlier original or derived evidence, including a previous run.
if (Test-Path -LiteralPath $OutputDirectory) { throw 'PRECHECK_HOLD_OUTPUT_DIRECTORY_ALREADY_EXISTS' }
if ([string]::IsNullOrWhiteSpace($TaskName)) { throw 'PRECHECK_HOLD_TASK_NOT_SPECIFIED' }

$bootUtc = [datetime]::Parse('2026-11-23T05:33:17.500Z', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal)
$startLocal = $bootUtc.AddMinutes(-2).ToLocalTime()
$endLocal = $bootUtc.AddMinutes(10).ToLocalTime()
$channel = 'Microsoft-Windows-TaskScheduler/Operational'
$errors = New-Object System.Collections.Generic.List[string]
$skipped = New-Object System.Collections.Generic.List[object]
$matches = New-Object System.Collections.Generic.List[object]
$seenEvents = 0
$taskState = 'UNREAD'
$lastTaskResult = $null
$bootTriggerConfigured = $false

try {
    $task = @(Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop)
    if ($task.Count -ne 1) { throw 'EXPECTED_ONE_TASK' }
    $taskState = [string]$task[0].State
    $bootTriggerConfigured = (@($task[0].Triggers | Where-Object { [string]$_.CimClass.CimClassName -match 'BootTrigger' }).Count -gt 0)
    $taskInfo = Get-ScheduledTaskInfo -InputObject $task[0] -ErrorAction Stop
    $lastTaskResult = [int]$taskInfo.LastTaskResult
}
catch {
    $errors.Add('TASK_QUERY_FAILED_' + $_.Exception.GetType().Name)
}

try {
    $events = @(Get-WinEvent -FilterHashtable @{LogName=$channel;StartTime=$startLocal;EndTime=$endLocal} -ErrorAction Stop | Sort-Object TimeCreated)
    $seenEvents = $events.Count
    if ($seenEvents -gt 5000) {
        $errors.Add('EVENT_WINDOW_OVER_5000_HOLD')
        $events = @()
    }
    foreach ($record in $events) {
        try {
            [xml]$x = $record.ToXml()
            $id = [int]$record.Id
            $timestamp = $record.TimeCreated.ToUniversalTime().ToString('o')
            $instanceToken = ''
            $isTarget = $false
            $dataAvailable = $false
            if ($null -ne $x.Event.EventData) {
                foreach ($d in @($x.Event.EventData.Data)) {
                    if ($null -eq $d) { continue }
                    $key = [string]$d.Name
                    $value = [string]$d.InnerText
                    if (-not [string]::IsNullOrWhiteSpace($value)) { $dataAvailable = $true }
                    if ($value.IndexOf($TaskName,[System.StringComparison]::OrdinalIgnoreCase) -ge 0) { $isTarget = $true }
                    if ($key -match '^(InstanceId|TaskInstanceId|TaskInstance|InstanceGuid)$') { $instanceToken = $value }
                }
            }
            if ([string]::IsNullOrWhiteSpace($instanceToken) -and $null -ne $x.Event.System.Correlation) {
                $instanceToken = [string]$x.Event.System.Correlation.ActivityID
            }
            if ($isTarget) {
                $matches.Add([ordered]@{
                    id = $id
                    utc = $timestamp
                    record_id = [long]$record.RecordId
                    instance_token_sha256 = $(if ($instanceToken) { Get-TextSha256 $instanceToken } else { $null })
                    has_event_data = $dataAvailable
                })
            }
        }
        catch {
            $skipped.Add([ordered]@{
                id = [int]$record.Id
                utc = $record.TimeCreated.ToUniversalTime().ToString('o')
                record_id = [long]$record.RecordId
                parse_error_type = $_.Exception.GetType().Name
            })
        }
    }
}
catch {
    $errors.Add('EVENT_LOG_READ_FAILED_' + $_.Exception.GetType().Name)
}

$expectedIds = @(118,129,100,200)
$allObserved = $true
foreach ($id in $expectedIds) {
    if (@($matches | Where-Object { $_.id -eq $id }).Count -eq 0) { $allObserved = $false }
}
if ($taskState -ne 'Disabled') { $errors.Add('TASK_NOT_VERIFIED_DISABLED') }
if (-not $bootTriggerConfigured) { $errors.Add('BOOT_TRIGGER_NOT_VERIFIED') }
if (-not $allObserved) { $errors.Add('EXPECTED_EVENT_IDS_NOT_ALL_MATCHED_IN_THIS_WINDOW') }
if ($skipped.Count -gt 0) { $errors.Add('XML_EVENTS_UNPARSED_IN_THIS_WINDOW') }
# This tool does not claim to replay the original Gate2F 176-event query,
# reconstruct the 4 old parse skips, prove STOP location, or certify R02.
$observation = [ordered]@{
    schema = 'ops77.gate2f.readonly-safe-observation.v1'
    assessed_at_utc = [datetime]::UtcNow.ToString('o')
    decision = 'INDEPENDENT_HOLD_ORIGINAL_GATE2F_SOURCE_NOT_READ'
    boot_utc_reference = $bootUtc.ToString('o')
    window_start_utc = $startLocal.ToUniversalTime().ToString('o')
    window_end_utc = $endLocal.ToUniversalTime().ToString('o')
    event_channel = $channel
    event_query_count = $seenEvents
    task_name_sha256 = Get-TextSha256 $TaskName
    task_state = $taskState
    last_task_result = $lastTaskResult
    boot_trigger_configured = $bootTriggerConfigured
    task_event_matches = @($matches.ToArray())
    xml_parse_skips_this_new_query = @($skipped.ToArray())
    holds = @($errors.ToArray())
    limitations = @('Not the original 176-event Gate2F query','Cannot explain the original four parse skips without those source records','Task-event parsing cannot establish universal absence of manual events 110 or logon events 119','No original SQLite rows reviewed','Canonical STOP marker path not pinned; STOP not independently checked','No market/Telegram/SQL checks or activation performed')
    forbidden_actions_executed = $false
}
[void][System.IO.Directory]::CreateDirectory($OutputDirectory)
$dataPath = Join-Path $OutputDirectory 'gate2f-safe-observations.json'
$manifestPath = Join-Path $OutputDirectory 'manifest.json'
Write-JsonFile -Path $dataPath -Object $observation
$sha = Get-FileSha256 -Path $dataPath
$manifest = [ordered]@{
    schema = 'ops77.gate2f.safe-manifest.v1'
    data_name = 'gate2f-safe-observations.json'
    data_length_bytes = (Get-Item -LiteralPath $dataPath).Length
    data_sha256 = $sha
    script_sha256 = Get-FileSha256 -Path $PSCommandPath
    original_gate2f_evidence_custody = 'NOT_COMPLETED'
    readback_from_github = 'NOT_RUN'
    independent_restore_from_github = 'NOT_RUN'
    output_is_sanitized_derived_metadata_only = $true
}
Write-JsonFile -Path $manifestPath -Object $manifest
Write-Output ('PRECHECK_SAFE_REPORT_WRITTEN=' + $dataPath)
Write-Output ('PRECHECK_DATA_SHA256=' + $sha)
Write-Output ('PRECHECK_XML_SKIP_COUNT_NEW_WINDOW=' + $skipped.Count)
Write-Output 'PRECHECK_INDEPENDENT_CUSTODY_HOLD_REMAINS'
