# Stage06B owner-local SQL Server environment inventory -- strictly READ-ONLY.
# No connections, credentials, database creation, migration, or import.
[CmdletBinding()]
param([string]$Base = 'D:\ZS-LOCAL-CI')
$ErrorActionPreference = 'Stop'
$result = [ordered]@{
    schema = 'zs.stage06b.local-sql-server-readiness.v1'
    mode = 'LOCAL_METADATA_ONLY_NO_SQL_CONNECT'
    generated_utc = [DateTime]::UtcNow.ToString('o')
    archive_validation_receipt_found = $false
    identity_readiness_receipt_found = $false
    sql_engine_service_count = 0
    sql_engine_running_count = 0
    sql_engine_service_names = @()
    sqlcmd_installed = $false
    sql_localdb_installed = $false
    odbc_64bit_sql_drivers = @()
    python_312_present = $false
    pyodbc_for_python_312 = $false
    approved_nonproduction_database = 'NOT_YET_SELECTED'
    proposed_separate_test_database_name = 'ZS_STAGE06B_SANDBOX'
    sql_connection_attempted = $false
    sql_database_created = $false
    sql_schema_modified = $false
    sql_data_written = $false
    telegram_api_called = $false
    credentials_accessed = $false
}
try {
    $root = [IO.Path]::GetFullPath($Base)
    if ([IO.Path]::GetPathRoot($root) -ne 'D:\') {
        throw 'BASE_MUST_BE_ON_D'
    }
    $safe = Join-Path $root 'stage06b-readiness'
    if (!(Test-Path -LiteralPath $safe -PathType Container)) {
        throw 'READINESS_DIRECTORY_MISSING'
    }
    $result.archive_validation_receipt_found = (
        @(Get-ChildItem -LiteralPath $safe -Filter 'REAL-ARCHIVE-VALIDATION-*.json' -File -ErrorAction SilentlyContinue).Count -gt 0
    )
    $result.identity_readiness_receipt_found = (
        @(Get-ChildItem -LiteralPath $safe -Filter 'IDENTITY-READINESS-*.json' -File -ErrorAction SilentlyContinue).Count -gt 0
    )
    $services = @(Get-Service -Name 'MSSQLSERVER','MSSQL$*' -ErrorAction SilentlyContinue)
    $services = @($services | Sort-Object -Property Name -Unique)
    $result.sql_engine_service_count = $services.Count
    $result.sql_engine_running_count = @($services | Where-Object { $_.Status -eq 'Running' }).Count
    # Only local Windows service names; do NOT print machine names, connection strings or secrets.
    $result.sql_engine_service_names = @($services | ForEach-Object { $_.Name })
    $result.sqlcmd_installed = ($null -ne (Get-Command sqlcmd.exe -ErrorAction SilentlyContinue))
    $result.sql_localdb_installed = ($null -ne (Get-Command SqlLocalDB.exe -ErrorAction SilentlyContinue))
    try {
        $result.odbc_64bit_sql_drivers = @(
            Get-OdbcDriver -Platform '64-bit' -ErrorAction Stop |
            Where-Object { $_.Name -match 'SQL Server' } |
            Select-Object -ExpandProperty Name -Unique |
            Sort-Object
        )
    } catch {
        $result.odbc_64bit_sql_drivers = @()
    }
    if ($null -ne (Get-Command py.exe -ErrorAction SilentlyContinue)) {
        $version = (& py -3.12 --version 2>$null | Out-String).Trim()
        $result.python_312_present = (
            $LASTEXITCODE -eq 0 -and $version -match '^Python 3\.12\.'
        )
        if ($result.python_312_present) {
            $check = (& py -3.12 -B -c "import importlib.util;print('YES' if importlib.util.find_spec('pyodbc') else 'NO')" 2>$null | Out-String).Trim()
            $result.pyodbc_for_python_312 = ($LASTEXITCODE -eq 0 -and $check -eq 'YES')
        }
    }
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
    $report = Join-Path $safe ('SQL-READINESS-' + $stamp + '.json')
    if (Test-Path -LiteralPath $report) { throw 'REPORT_ALREADY_EXISTS' }
    [IO.File]::WriteAllText(
        $report,
        (([pscustomobject]$result) | ConvertTo-Json -Depth 8),
        (New-Object System.Text.UTF8Encoding($false))
    )
    Write-Host 'SQL_READINESS=COMPLETE_READ_ONLY'
    Write-Host ("REAL_ARCHIVE_RECEIPT_PRESENT=" + $result.archive_validation_receipt_found)
    Write-Host ("IDENTITY_RECEIPT_PRESENT=" + $result.identity_readiness_receipt_found)
    Write-Host ("SQL_ENGINE_SERVICES=" + $result.sql_engine_service_count)
    Write-Host ("SQL_ENGINE_RUNNING=" + $result.sql_engine_running_count)
    Write-Host ("SQL_SERVICE_NAMES=" + ($result.sql_engine_service_names -join ','))
    Write-Host ("SQLCMD_AVAILABLE=" + $result.sqlcmd_installed)
    Write-Host ("LOCALDB_AVAILABLE=" + $result.sql_localdb_installed)
    Write-Host ("ODBC_64BIT_SQL_DRIVERS=" + ($result.odbc_64bit_sql_drivers -join ','))
    Write-Host ("PYTHON_312_AVAILABLE=" + $result.python_312_present)
    Write-Host ("PYODBC_AVAILABLE=" + $result.pyodbc_for_python_312)
    Write-Host ("NONPRODUCTION_SQL_DATABASE_APPROVED=" + $result.approved_nonproduction_database)
    Write-Host 'SQL_CONNECTIONS=0 SQL_WRITES=0'
    Write-Host ("SAFE_REPORT=" + $report)
    Write-Host 'No connection, database creation, migration, data import, bot API or trading.'
    exit 0
} catch {
    # Fixed privacy-safe failure code; do not print sensitive local paths.
    Write-Host 'SQL_READINESS=BLOCKED'
    Write-Host 'STOP_REASON=LOCAL_METADATA_READ_OR_REPORT_FAILED'
    exit 2
}
