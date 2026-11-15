# Stage06B: owner-local attachment disambiguation, READ ONLY.
# All source paths and file digests stay in a PRIVATE report on D:, not GitHub.
# Console outputs counters only; no copies/SQL/Telegram/market activity.
[CmdletBinding()]
param(
  [string]$Base = 'D:\ZS-LOCAL-CI',
  [string[]]$AdditionalRoots = @()
)
$ErrorActionPreference = 'Stop'
$maxDirs = 4000
$maxDepth = 4
$maxBytes = 16MB
$refs = New-Object System.Collections.ArrayList
$files = @(
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
function IsSafeMedia([string]$s) {
    if ([string]::IsNullOrWhiteSpace($s) -or $s -match '(^[/\\]|^[A-Za-z]:|[/\\]{2}|[\x00-\x1f])') {
        return $false
    }
    foreach ($p in ($s -split '[/\\]')) {
        if ($p -eq '' -or $p -eq '.' -or $p -eq '..') { return $false }
    }
    return $true
}
function CaptionText($row) {
    if ($row.text -is [string]) { return $row.text }
    $parts = @()
    foreach ($fragment in @($row.text)) {
        if ($fragment -is [string]) { $parts += $fragment }
        elseif ($null -ne $fragment.text -and $fragment.text -is [string]) { $parts += $fragment.text }
    }
    return ($parts -join '')
}
try {
    foreach ($source in $files) {
        if (!(Test-Path -LiteralPath $source.Path -PathType Leaf)) { throw 'SOURCE_EXPORT_NOT_FOUND' }
        $raw = Get-Content -LiteralPath $source.Path -Raw -Encoding UTF8
        $export = ConvertFrom-Json -InputObject $raw -ErrorAction Stop
        if ($export.type -notin @('bot_chat','personal_chat') -or $null -eq $export.messages) {
            throw 'SOURCE_EXPORT_STRUCTURE_INVALID'
        }
        foreach ($msg in @($export.messages)) {
            if ($null -eq $msg) { continue }
            $expected = $null
            $caption = CaptionText $msg
            if ($caption -match 'ZS05_ARCHIVE_V1 sha256=([a-f0-9]{64})') {
                $expected = $Matches[1].ToLowerInvariant()
            }
            foreach ($field in @('file','photo','thumbnail','video_file','audio_file','voice_file','sticker_file')) {
                $name = [string]$msg.$field
                if ([string]::IsNullOrWhiteSpace($name)) { continue }
                if (!(IsSafeMedia $name)) { throw 'UNSAFE_ATTACHMENT_REFERENCE' }
                $relative = $name.Replace('/','\')
                [void]$refs.Add([pscustomobject]@{
                    ordinal = ($refs.Count+1)
                    role = $source.Role
                    field = $field
                    relative_path = $relative
                    basename = [IO.Path]::GetFileName($relative)
                    expected_sha256 = $(if ($field -eq 'file') { $expected } else { $null })
                    candidates = (New-Object System.Collections.ArrayList)
                })
            }
        }
    }
    $visited = @{}
    $queue = New-Object System.Collections.Queue
    foreach ($root in $roots) {
        if ([string]::IsNullOrWhiteSpace($root) -or !(Test-Path -LiteralPath $root -PathType Container)) { continue }
        $full = [IO.Path]::GetFullPath($root)
        $key = $full.ToLowerInvariant()
        if (!$visited.ContainsKey($key)) {
            $visited[$key] = $true
            $queue.Enqueue([pscustomobject]@{path=$full; depth=0})
        }
    }
    $directories=0; $limitHit=$false
    while ($queue.Count -gt 0) {
        if ($directories -ge $maxDirs) { $limitHit=$true; break }
        $folder = $queue.Dequeue()
        $directories++
        foreach ($r in $refs) {
            foreach ($piece in @($r.relative_path,$r.basename)) {
                $candidate = Join-Path $folder.path $piece
                try {
                    $fi = Get-Item -LiteralPath $candidate -ErrorAction Stop
                    if ($fi.PSIsContainer -or $fi.Length -gt $maxBytes -or
                        ($fi.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
                    $full = $fi.FullName
                    if (@($r.candidates | Where-Object { $_.path -ieq $full }).Count) { continue }
                    $sha = (Get-FileHash -LiteralPath $full -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
                    [void]$r.candidates.Add([pscustomobject]@{
                        path=$full
                        size_bytes=[int64]$fi.Length
                        sha256=$sha
                    })
                } catch {}
            }
        }
        if ($folder.depth -ge $maxDepth) { continue }
        try {
            $children = @(Get-ChildItem -LiteralPath $folder.path -Directory -ErrorAction Stop | Select-Object -First 250)
        } catch { continue }
        foreach ($child in $children) {
            if ($child.Name -match '^(run-\d{8}|node_modules|\.git|\.venv|venv|__pycache__|stage06b-readiness)$' -or
                ($child.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
            $key = $child.FullName.ToLowerInvariant()
            if (!$visited.ContainsKey($key)) {
                $visited[$key] = $true
                $queue.Enqueue([pscustomobject]@{path=$child.FullName;depth=($folder.depth+1)})
            }
        }
    }
    # Ground probable Telegram export roots in already hash-matched archive files.
    $verifiedRoots = New-Object System.Collections.ArrayList
    $verified=0; $same=0; $different=0; $alone=0; $missing=0; $wrong=0
    foreach ($r in $refs) {
        if (!$r.expected_sha256) { continue }
        $matching = @($r.candidates | Where-Object { $_.sha256 -eq $r.expected_sha256 })
        if (!$matching.Count) { $wrong++; continue }
        $verified++
        foreach ($m in $matching) {
            if ($m.path.EndsWith($r.relative_path,[StringComparison]::OrdinalIgnoreCase)) {
                $rootPath = $m.path.Substring(0,$m.path.Length-$r.relative_path.Length).TrimEnd('\')
                if ($rootPath -and !@($verifiedRoots | Where-Object { $_ -ieq $rootPath }).Count) {
                    [void]$verifiedRoots.Add($rootPath)
                }
            }
        }
    }
    $private=@()
    foreach ($r in $refs) {
        $group = @($r.candidates | Select-Object -ExpandProperty sha256 -Unique)
        $rootMatches=0
        foreach ($candidate in $r.candidates) {
            foreach ($rootPath in $verifiedRoots) {
                $expectedFull = Join-Path $rootPath $r.relative_path
                if ($candidate.path -ieq $expectedFull) { $rootMatches++; break }
            }
        }
        $state = 'UNRESOLVED'
        if ($r.expected_sha256) {
            if (@($r.candidates | Where-Object { $_.sha256 -eq $r.expected_sha256 }).Count) {
                $state='ARCHIVE_SHA_VERIFIED'
            } else { $state='ARCHIVE_SHA_NOT_VERIFIED' }
        } elseif ($r.candidates.Count -eq 0) {
            $missing++; $state='NOT_FOUND'
        } elseif ($group.Count -eq 1 -and $r.candidates.Count -gt 1) {
            $same++; $state='MULTIPLE_PATHS_SAME_CONTENT_UNATTESTED'
        } elseif ($group.Count -gt 1) {
            $different++; $state='DIFFERENT_CONTENT_NEEDS_SOURCE_SELECTION'
        } elseif ($r.candidates.Count -eq 1) {
            $alone++; $state='ONE_NAME_MATCH_NO_EXTERNAL_SHA'
        }
        $private+=([pscustomobject]@{
            ordinal=$r.ordinal; role=$r.role; field=$r.field
            relative_path=$r.relative_path; expected_sha256=$r.expected_sha256
            disposition=$state
            candidate_count=$r.candidates.Count
            unique_content_sha256_count=$group.Count
            matched_verified_export_root_candidates=$rootMatches
            candidates=@($r.candidates)
        })
    }
    $status=[ordered]@{
        schema='zs.stage06b.attachment-disambiguation.v1'
        mode='READ_ONLY_NO_SQL_NO_NETWORK'
        generated_utc=[DateTime]::UtcNow.ToString('o')
        references=$refs.Count
        directories_checked=$directories
        directory_limit_hit=$limitHit
        archive_caption_sha_matched=$verified
        multiple_paths_identical_content_unattested=$same
        differing_content_ambiguous=$different
        name_only_unique_candidate=$alone
        no_candidate=$missing
        expected_sha_not_verified=$wrong
        possible_verified_export_roots=$verifiedRoots.Count
        source_files_changed=0; files_copied=0; sql_attempts=0; telegram_api_attempts=0
    }
    $output = Join-Path $Base 'stage06b-readiness'
    New-Item -ItemType Directory -Path $output -Force | Out-Null
    $stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
    $safePath=Join-Path $output ('DISAMBIGUATION-'+$stamp+'.json')
    $privateFolder=Join-Path $Base 'stage06b-private'
    New-Item -ItemType Directory -Path $privateFolder -Force | Out-Null
    $privatePath=Join-Path $privateFolder ('LOCAL-MEDIA-CANDIDATES-'+$stamp+'.json')
    [IO.File]::WriteAllText($safePath, (([pscustomobject]$status) | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
    [IO.File]::WriteAllText($privatePath, ($private | ConvertTo-Json -Depth 7), (New-Object System.Text.UTF8Encoding($false)))
    Write-Host 'MEDIA_DISAMBIGUATION=COMPLETE_READ_ONLY'
    Write-Host ("REFS="+$status.references)
    Write-Host ("CAPTION_SHA_MATCHED="+$status.archive_caption_sha_matched)
    Write-Host ("DUPLICATE_PATHS_IDENTICAL_BYTES_UNATTESTED="+$status.multiple_paths_identical_content_unattested)
    Write-Host ("DIFFERENT_CONTENT_AMBIGUOUS="+$status.differing_content_ambiguous)
    Write-Host ("ONE_NAME_MATCH_UNATTESTED="+$status.name_only_unique_candidate)
    Write-Host ("NOT_FOUND="+$status.no_candidate)
    Write-Host ("EXPECTED_SHA_UNVERIFIED="+$status.expected_sha_not_verified)
    Write-Host ("VERIFIED_EXPORT_ROOTS="+$status.possible_verified_export_roots)
    Write-Host ("SEARCH_LIMIT_REACHED="+$status.directory_limit_hit)
    Write-Host ("SAFE_REPORT="+$safePath)
    Write-Host 'PRIVATE_DETAIL_REPORT=LOCAL_ONLY_DO_NOT_UPLOAD'
    Write-Host 'No source file copies, network, Telegram calls or SQL connections.'
    exit 0
} catch {
    Write-Host 'MEDIA_DISAMBIGUATION=BLOCKED'
    Write-Host ('STOP_REASON='+$_.Exception.Message)
    exit 2
}
