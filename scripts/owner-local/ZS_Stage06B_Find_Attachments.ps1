# Stage06B: read-only recovery locator for Telegram Desktop exported attachments.
# Detects referenced media within bounded owner-local folders; no network, SQL or data copies.
[CmdletBinding()]
param(
  [string]$Base = 'D:\ZS-LOCAL-CI',
  [string[]]$AdditionalRoots = @()
)
$ErrorActionPreference = 'Stop'
$maxDirs = 4000
$maxDepth = 4
$maxFileBytes = 16MB
$exportFiles = @(
    @{ Role='ANALYTICS_C'; Path=(Join-Path $Base 'bot data and archive.json') },
    @{ Role='SIGNALS_MAIN'; Path=(Join-Path $Base 'bot signals main.json') }
)
$roots = @(
    (Join-Path $env:USERPROFILE 'Downloads'),
    (Join-Path $env:USERPROFILE 'Desktop'),
    (Join-Path $env:USERPROFILE 'Documents'),
    $Base,
    'D:\TelegramExports',
    'D:\ZS_STAGE06B_PRIVATE\exports',
    'D:\ZS-LOCAL-CI\stage06b-private\exports'
) + @($AdditionalRoots)
$exclude = '^(run-\d{8}|node_modules|\.git|\.venv|venv|__pycache__|stage06b-readiness)$'
$refs = New-Object System.Collections.ArrayList
function SafeRelative([string]$value) {
    if ([string]::IsNullOrWhiteSpace($value) -or
        $value -match '(^[/\\]|^[a-zA-Z]:|[/\\]{2}|[\x00-\x1f])') { return $false }
    foreach ($part in ($value -split '[\\/]')) {
        if ($part -eq '' -or $part -eq '.' -or $part -eq '..') { return $false }
    }
    return $true
}
function TextOf($row) {
    if ($row.text -is [string]) { return $row.text }
    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($part in @($row.text)) {
        if ($part -is [string]) { [void]$parts.Add($part) }
        elseif ($null -ne $part.text -and $part.text -is [string]) { [void]$parts.Add($part.text) }
    }
    return ($parts -join '')
}
try {
    foreach ($source in $exportFiles) {
        if (!(Test-Path -LiteralPath $source.Path -PathType Leaf)) { continue }
        $export = Get-Content -LiteralPath $source.Path -Encoding UTF8 -Raw | ConvertFrom-Json
        if ($export.type -notin @('bot_chat','personal_chat') -or $null -eq $export.messages) {
            throw 'UNSUPPORTED_EXPORT_STRUCTURE'
        }
        foreach ($row in @($export.messages)) {
            if ($null -eq $row) { continue }
            $caption = TextOf $row
            $expectedSHA = $null
            if ($caption -match 'ZS05_ARCHIVE_V1 sha256=([a-f0-9]{64})') { $expectedSHA = $Matches[1] }
            foreach ($field in @('file','photo','thumbnail','video_file','audio_file','voice_file','sticker_file')) {
                $value = [string]$row.$field
                if ([string]::IsNullOrWhiteSpace($value)) { continue }
                if (!(SafeRelative $value)) { throw 'UNSAFE_MEDIA_REFERENCE' }
                $normalized = $value.Replace('/','\')
                $basename = [IO.Path]::GetFileName($normalized)
                # Only archive document references carry a separately signed caption SHA.
                $verify = if ($field -eq 'file') { $expectedSHA } else { $null }
                [void]$refs.Add([pscustomobject]@{
                    Role=$source.Role
                    Relative=$normalized
                    Basename=$basename
                    ExpectedSHA=$verify
                    Candidates=(New-Object System.Collections.ArrayList)
                })
            }
        }
    }
    $queue = New-Object System.Collections.Queue
    $enqueued = @{}
    foreach ($root in $roots) {
        if ([string]::IsNullOrWhiteSpace($root) -or
            !(Test-Path -LiteralPath $root -PathType Container)) { continue }
        $full = [IO.Path]::GetFullPath($root)
        if (!$enqueued.ContainsKey($full.ToLowerInvariant())) {
            $queue.Enqueue([pscustomobject]@{Path=$full;Depth=0})
            $enqueued[$full.ToLowerInvariant()] = $true
        }
    }
    $dirs = 0
    $tooMany = $false
    while ($queue.Count -gt 0) {
        if ($dirs -ge $maxDirs) { $tooMany = $true; break }
        $folder = $queue.Dequeue()
        $dirs++
        foreach ($r in $refs) {
            foreach ($relative in @($r.Relative, $r.Basename)) {
                $candidate = Join-Path $folder.Path $relative
                try {
                    $file = Get-Item -LiteralPath $candidate -ErrorAction Stop
                    if (!$file.PSIsContainer -and $file.Length -le $maxFileBytes -and
                        !($file.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                        if (!@($r.Candidates | Where-Object { $_.Path -eq $file.FullName }).Count) {
                            [void]$r.Candidates.Add([pscustomobject]@{Path=$file.FullName; SHA=$null})
                        }
                    }
                } catch {}
            }
        }
        if ($folder.Depth -ge $maxDepth) { continue }
        try { $children = @(Get-ChildItem -LiteralPath $folder.Path -Directory -ErrorAction Stop | Select-Object -First 250) }
        catch { continue }
        foreach ($child in $children) {
            if ($child.Name -match $exclude -or ($child.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
            $key = $child.FullName.ToLowerInvariant()
            if (!$enqueued.ContainsKey($key)) {
                $enqueued[$key] = $true
                $queue.Enqueue([pscustomobject]@{Path=$child.FullName;Depth=($folder.Depth + 1)})
            }
        }
    }
    $matchedHash=0; $uniqueWithoutHash=0; $ambiguous=0; $missing=0; $wrongHash=0
    foreach ($r in $refs) {
        if ($r.Candidates.Count -eq 0) { $missing++; continue }
        if ($r.ExpectedSHA) {
            $matches=0
            foreach ($cand in $r.Candidates) {
                try {
                    $actual=(Get-FileHash -LiteralPath $cand.Path -Algorithm SHA256).Hash.ToLowerInvariant()
                    if ($actual -eq $r.ExpectedSHA) { $matches++ }
                } catch {}
            }
            if ($matches -ge 1) { $matchedHash++ } else { $wrongHash++ }
        } elseif ($r.Candidates.Count -eq 1) { $uniqueWithoutHash++ }
        else { $ambiguous++ }
    }
    $report=[ordered]@{
        schema='zs.stage06b.local-attachment-locator.v1'
        mode='READ_ONLY_NO_COPIES'
        generated_utc=[DateTime]::UtcNow.ToString('o')
        media_references=$refs.Count
        directories_checked=$dirs
        search_limit_reached=$tooMany
        archive_sha_verified_references=$matchedHash
        unique_name_candidates_unverified=$uniqueWithoutHash
        ambiguous_name_candidates=$ambiguous
        found_wrong_hash=$wrongHash
        not_found=$missing
        sql_attempts=0
        network_attempts=0
        files_copied=0
    }
    $output=Join-Path $Base 'stage06b-readiness'
    New-Item -ItemType Directory -Path $output -Force | Out-Null
    $reportPath=Join-Path $output ('MEDIA-LOCATOR-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'.json')
    [IO.File]::WriteAllText($reportPath, (([pscustomobject]$report) | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))
    Write-Host 'MEDIA_LOCATOR=COMPLETE_READ_ONLY'
    Write-Host ("MEDIA_REFERENCES="+$report.media_references)
    Write-Host ("DIRECTORIES_CHECKED="+$report.directories_checked)
    Write-Host ("SEARCH_LIMIT_REACHED="+$report.search_limit_reached)
    Write-Host ("ARCHIVE_SHA_VERIFIED="+$report.archive_sha_verified_references)
    Write-Host ("UNVERIFIED_UNIQUE_NAME="+$report.unique_name_candidates_unverified)
    Write-Host ("AMBIGUOUS="+$report.ambiguous_name_candidates)
    Write-Host ("WRONG_SHA="+$report.found_wrong_hash)
    Write-Host ("NOT_FOUND="+$report.not_found)
    Write-Host ("SAFE_REPORT="+$reportPath)
    Write-Host 'No private file names, chat IDs, messages or credentials printed.'
} catch {
    Write-Host 'MEDIA_LOCATOR=BLOCKED'
    Write-Host ('STOP_REASON='+$_.Exception.Message)
    exit 2
}
