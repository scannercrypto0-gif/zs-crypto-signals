# Owner Windows local ONLY. This script DOES NOT call Telegram/GitHub or enable sends.
# Values are encrypted using current-user DPAPI; no plaintext .env files.
param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('signals-token','signals-chat-a','signals-chat-b',
               'interactive-token','interactive-allowed-users',
               'interactive-allowed-chats','analytics-token','analytics-chat')]
  [string]$Name
)
$ErrorActionPreference='Stop'
if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
  throw 'WINDOWS_DPAPI_REQUIRED'
}
$root=Join-Path $env:LOCALAPPDATA 'ZS-SmartGate\stage05-secrets'
New-Item -ItemType Directory -Path $root -Force | Out-Null
$user=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$dirAcl=New-Object System.Security.AccessControl.DirectorySecurity
$dirAcl.SetAccessRuleProtection($true,$false)
$rule=New-Object System.Security.AccessControl.FileSystemAccessRule(
  $user,'FullControl','ContainerInherit,ObjectInherit','None','Allow'
)
$dirAcl.AddAccessRule($rule)
Set-Acl -LiteralPath $root -AclObject $dirAcl
$path=Join-Path $root ($Name+'.dpapi')
if (Test-Path -LiteralPath $path) {
  throw 'EXISTING_SECRET_REFUSE_OVERWRITE_USE_EXPLICIT_ROTATION'
}
$secret=Read-Host "Local $Name value (input hidden)" -AsSecureString
try {
  if ($secret.Length -eq 0) { throw 'EMPTY_SECRET_REJECTED' }
  $sealed=ConvertFrom-SecureString -SecureString $secret
  Set-Content -LiteralPath $path -Value $sealed -Encoding UTF8 -NoNewline
  $fileAcl=New-Object System.Security.AccessControl.FileSecurity
  $fileAcl.SetAccessRuleProtection($true,$false)
  $fRule=New-Object System.Security.AccessControl.FileSystemAccessRule(
    $user,'FullControl','Allow'
  )
  $fileAcl.AddAccessRule($fRule)
  Set-Acl -LiteralPath $path -AclObject $fileAcl
} finally {
  $secret.Dispose()
  Remove-Variable sealed -ErrorAction SilentlyContinue
}
Write-Output 'STAGE05_DPAPI_SECRET_STORED_FOR_CURRENT_WINDOWS_USER'
Write-Output 'LIVE_SWITCHES_UNCHANGED_FALSE'
Write-Output 'TELEGRAM_HTTP_REQUESTS=0'
