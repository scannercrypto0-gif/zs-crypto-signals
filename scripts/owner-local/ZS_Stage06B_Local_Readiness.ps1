# Stage06B owner Windows local readiness preflight. READ-ONLY.
# Uses ONLY local export files and local process/service metadata.
# No Telegram/Binance API, SQL connection, write, polling or trading.
# No raw text, bot IDs, chat IDs, file names or credentials in report.
[CmdletBinding()]
param(
    [string]$ReportRoot = 'D:\ZS-LOCAL-CI\stage06b-readiness',
    [string[]]$AdditionalExportRoots = @()
)

$ErrorActionPreference = 'Stop'
$maxBytes = 64MB
$now = [DateTime]::UtcNow.ToString('o')
$sourceMain = 'bd7d6a88430d12b91fcc2004290ddb0c38833e6e'

function Test-FilePresent([string]$file) {
    try { return (Test-Path -LiteralPath $file -PathType Leaf -ErrorAction Stop) }
    catch { return $false }
}

$findings = [ordered]@{
    schema = 'zs.stage06b.owner-local-readiness.v1'
    mode = 'READ_ONLY_PREFLIGHT'
    generated_utc = $now
    source_main_sha = $sourceMain
    export_candidate_count = 0
    export_shape_accepted_count = 0
    export_shape_rejected_count = 0
    export_too_large_count = 0
    messages_count = 0
    archive_caption_count = 0
    media_reference_count = 0
    missing_media_count = 0
    unsafe_media_path_count = 0
    export_read_errors = 0
    sql_engine_service_present = $false
    sql_engine_service_running = $false
    sql_localdb_command_present = $false
    sqlcmd_command_present = $false
    sql_odbc_driver_present = $false
    python_312_present = $false
    pyodbc_installed = $false
    private_sql_connection_configured = $false
    sql_connection_attempts = 0
    sql_write_attempts = 0
    telegram_api_attempts = 0
    market_api_attempts = 0
    owner_mapping_present = $false
    readiness = 'UNDETERMINED'
    next_action = 'UNDETERMINED'
}

$scanned = @{}
$roots = @(
    (Join-Path $env:USERPROFILE 'Downloads'),
    (Join-Path $env:USERPROFILE 'Desktop'),
    (Join-Path $env:USERPROFILE 'Documents'),
    'D:\ZS-LOCAL-CI\stage06b-private\exports',
    'D:\ZS_STAGE06B_PRIVATE\exports',
    'D:\TelegramExports'
) + @($AdditionalExportRoots)

function Add-ExportCandidate([string]$folder) {
    if ([string]::IsNullOrWhiteSpace($folder)) { return }
    try {
        $target = Join-Path $folder 'result.json'
        if (Test-FilePresent $target) {
            $full = [IO.Path]::GetFullPath($target)
            $script:scanned[$full.ToLowerInvariant()] = $full
        }
    } catch { }
}

# Bounded discovery: only named standard export folders within two levels
# of Downloads/Desktop/Documents and explicitly designated D: directories.
foreach ($root in $roots) {
    if ([string]::IsNullOrWhiteSpace($root) -or
        !(Test-Path -LiteralPath $root -PathType Container -ErrorAction SilentlyContinue)) {
        continue
    }
    Add-ExportCandidate $root
    $first = @(Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
               Select-Object -First 250)
    foreach ($folder in $first) {
        Add-ExportCandidate $folder.FullName
        if ($folder.Name -match '(?i)(chat.?export|telegram|export|stage06b)') {
            $second = @(Get-ChildItem -LiteralPath $folder.FullName -Directory -ErrorAction SilentlyContinue |
                        Select-Object -First 150)
            foreach ($child in $second) {
                Add-ExportCandidate $child.FullName
            }
        }
    }
}

$findings.export_candidate_count = $scanned.Count
foreach ($resultFile in @($scanned.Values)) {
    try {
        $file = Get-Item -LiteralPath $resultFile -ErrorAction Stop
        if ($file.Length -le 0 -or $file.Length -gt $maxBytes) {
            $findings.export_too_large_count++
            continue
        }
        $raw = [IO.File]::ReadAllText($resultFile, [Text.Encoding]::UTF8)
        $export = ConvertFrom-Json -InputObject $raw -ErrorAction Stop
        if ($null -eq $export -or $export.type -ne 'personal_chat' -or
            $null -eq $export.id -or $null -eq $export.messages -or
            [string]::IsNullOrWhiteSpace([string]$export.name)) {
            $findings.export_shape_rejected_count++
            continue
        }
        $findings.export_shape_accepted_count++
        foreach ($message in @($export.messages)) {
            $findings.messages_count++
            if ($null -eq $message) { continue }
            $fragments = @()
            if ($message.text -is [string]) { $fragments = @($message.text) }
            elseif ($message.text -is [array]) {
                foreach ($bit in $message.text) {
                    if ($bit -is [string]) { $fragments += $bit }
                    elseif ($null -ne $bit.text -and $bit.text -is [string]) { $fragments += $bit.text }
                }
            }
            if (($fragments -join '') -match 'ZS05_ARCHIVE_V1 sha256=') {
                $findings.archive_caption_count++
            }
            foreach ($field in @('file','photo','thumbnail','video_file',
                                  'audio_file','voice_file','sticker_file')) {
                $relative = [string]$message.$field
                if ([string]::IsNullOrWhiteSpace($relative)) { continue }
                $findings.media_reference_count++
                if ($relative -match '(^[/\\]|^[A-Za-z]:|(^|[/\\])\.\.([/\\]|$))') {
                    $findings.unsafe_media_path_count++
                    continue
                }
                $normalized = $relative.Replace('/','\')
                $candidate = Join-Path $file.DirectoryName $normalized
                if (!(Test-FilePresent $candidate)) { $findings.missing_media_count++ }
            }
        }
    }
    catch {
        $findings.export_read_errors++
    }
}

try {
    $services = @(Get-Service -Name 'MSSQLSERVER','MSSQL$*' -ErrorAction SilentlyContinue)
    $findings.sql_engine_service_present = ($services.Count -gt 0)
    $findings.sql_engine_service_running = (@($services | Where-Object { $_.Status -eq 'Running' }).Count -gt 0)
} catch {}
$findings.sql_localdb_command_present = ($null -ne (Get-Command 'SqlLocalDB.exe' -ErrorAction SilentlyContinue))
$findings.sqlcmd_command_present = ($null -ne (Get-Command 'sqlcmd.exe' -ErrorAction SilentlyContinue))
try {
    $drivers = @(Get-OdbcDriver -Platform '64-bit' -ErrorAction Stop |
                 Where-Object { $_.Name -match 'SQL Server' })
    $findings.sql_odbc_driver_present = ($drivers.Count -gt 0)
} catch {}
if ($null -ne (Get-Command 'py.exe' -ErrorAction SilentlyContinue)) {
    try {
        $version = (& py -3.12 --version 2>$null | Out-String).Trim()
        $findings.python_312_present = ($LASTEXITCODE -eq 0 -and $version -match '^Python 3\.12\.')
        if ($findings.python_312_present) {
            $present = (& py -3.12 -c "import importlib.util;print('PRESENT' if importlib.util.find_spec('pyodbc') else 'ABSENT')" 2>$null | Out-String).Trim()
            $findings.pyodbc_installed = ($LASTEXITCODE -eq 0 -and $present -eq 'PRESENT')
        }
    } catch {}
}
$findings.private_sql_connection_configured = (
    ![string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('ZS_STAGE06B_SQL_ODBC')))
$findings.owner_mapping_present = (Test-FilePresent 'D:\ZS-LOCAL-CI\stage06b-private\owner-mapping.json')

if ($findings.export_shape_accepted_count -eq 0) {
    $findings.readiness = 'NEED_TELEGRAM_DESKTOP_EXPORT'
    $findings.next_action = 'EXPORT_PRIVATE_BOT_CHATS_TO_JSON_WITH_MEDIA'
}
elseif ($findings.missing_media_count -gt 0 -or $findings.unsafe_media_path_count -gt 0 -or
        $findings.export_read_errors -gt 0 -or $findings.export_shape_rejected_count -gt 0) {
    $findings.readiness = 'EXPORT_VALIDATION_INCOMPLETE'
    $findings.next_action = 'REPAIR_EXPORT_ATTACHMENTS_OR_SHAPE'
}
elseif (-not $findings.owner_mapping_present) {
    $findings.readiness = 'NEED_LOCAL_OWNER_BOT_CHAT_MAPPING'
    $findings.next_action = 'PREPARE_PRIVATE_MANIFEST_WITH_DECLARED_IDENTITIES'
}
elseif (-not ($findings.sql_engine_service_running -or $findings.sql_localdb_command_present)) {
    $findings.readiness = 'NEED_AUTHORIZED_LOCAL_SQL_SERVER'
    $findings.next_action = 'CHECK_LOCAL_SQL_TEST_DATABASE'
}
else {
    $findings.readiness = 'READ_ONLY_PREFLIGHT_PASSED_PARTIAL'
    $findings.next_action = 'VERIFY_PRIVATE_MANIFEST_THEN_AUTHORIZE_SQL_ROUNDTRIP'
}

try {
    if (!(Test-Path 'D:\')) { throw 'DRIVE_D_UNAVAILABLE' }
    if ([IO.Path]::GetPathRoot([IO.Path]::GetFullPath($ReportRoot)) -ne 'D:\') {
        throw 'REPORT_MUST_BE_ON_D'
    }
    New-Item -ItemType Directory -Path $ReportRoot -Force | Out-Null
    $timestamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
    $report = Join-Path $ReportRoot ('READINESS-' + $timestamp + '.json')
    if (Test-Path -LiteralPath $report) { throw 'REPORT_EXISTS' }
    $json = ConvertTo-Json -InputObject ([pscustomobject]$findings) -Depth 8
    [IO.File]::WriteAllText($report, $json, (New-Object Text.UTF8Encoding($false)))
    Write-Host 'STAGE06B_PREFLIGHT=COMPLETE_READ_ONLY'
    Write-Host ("EXPORTS_FOUND=" + $findings.export_shape_accepted_count)
    Write-Host ("MESSAGES_OBSERVED=" + $findings.messages_count)
    Write-Host ("ARCHIVE_CAPTIONS_OBSERVED=" + $findings.archive_caption_count)
    Write-Host ("MISSING_MEDIA_REFERENCES=" + $findings.missing_media_count)
    Write-Host ("SQL_ENGINE_RUNNING=" + $findings.sql_engine_service_running)
    Write-Host ("SQL_LOCALDB_AVAILABLE=" + $findings.sql_localdb_command_present)
    Write-Host ("ODBC_DRIVER_AVAILABLE=" + $findings.sql_odbc_driver_present)
    Write-Host ("PYODBC_AVAILABLE=" + $findings.pyodbc_installed)
    Write-Host ("OWNER_MAPPING_PRESENT=" + $findings.owner_mapping_present)
    Write-Host ("NEXT_ACTION=" + $findings.next_action)
    Write-Host ("SAFE_REPORT=" + $report)
    Write-Host 'No SQL connections/writes; no market/Telegram API calls.'
    exit 0
}
catch {
    # Sanitized local error code; do not leak user filenames or source content.
    Write-Host 'STAGE06B_PREFLIGHT=BLOCKED_REPORT_WRITE'
    exit 2
}
