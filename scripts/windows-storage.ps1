function Assert-DPath {
    param([Parameter(Mandatory)][string]$Path)
    if($Path -notmatch '^[dD]:[\\/]' -or $Path.StartsWith('\\')) { throw 'D_ONLY_PROJECT_STORAGE_REQUIRED' }
    $volume=Get-Volume -DriveLetter D -ErrorAction Stop
    if($volume.DriveType -ne 'Fixed' -or $volume.HealthStatus -ne 'Healthy') { throw 'D_VOLUME_UNAVAILABLE' }
    $full=[IO.Path]::GetFullPath($Path)
    $item=Get-Item -LiteralPath $full -Force -ErrorAction Stop
    while($item) {
        if($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'D_REPARSE_PATH_REJECTED' }
        $parent=Split-Path $item.FullName -Parent
        if(-not $parent -or $parent -eq $item.FullName) { break }
        $item=Get-Item -LiteralPath $parent -Force -ErrorAction Stop
    }
    return $full
}
