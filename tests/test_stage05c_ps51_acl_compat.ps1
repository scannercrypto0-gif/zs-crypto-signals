# Focused Windows PowerShell 5.1 compatibility test: creates no project custody or secrets.
# Execute ONLY on Windows PowerShell 5.1 via powershell.exe -NoProfile -ExecutionPolicy Bypass -File.
# This test intentionally preserves its own new isolated fixture for inspection.
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
    throw 'POWERSHELL_51_REQUIRED'
}
$owner = [Security.Principal.WindowsIdentity]::GetCurrent().User
function Assert-Private([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    $acl = Get-Acl -LiteralPath $Path
    $rules = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        ($item.PSIsContainer -and !$acl.AreAccessRulesProtected) -or
        $acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $owner -or
        $rules.Count -ne 1 -or $rules[0].IdentityReference -ne $owner -or
        $rules[0].AccessControlType -ne 'Allow') {
        throw 'OWNER_ONLY_ACL_REQUIRED'
    }
}
# Separate, unique owner-local fixture; nothing under either Stage05C custody root.
$fixtureParent = Join-Path $env:LOCALAPPDATA 'ZS-SmartGate\\stage05-secrets'
Assert-Private $fixtureParent
$fixture = Join-Path $fixtureParent ('ps51-acl-fixture-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $fixture) { throw 'TEST_FIXTURE_COLLISION' }
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true,$false)
$acl.SetOwner($owner)
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($owner,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
[void][System.IO.Directory]::CreateDirectory($fixture,$acl)
Assert-Private $fixture
Write-Output 'PS51_ATOMIC_OWNER_ONLY_CREATE=PASS'
# Check rejection of an existing invalid ACL; do not change its ACL or remove it.
$bad = Join-Path $fixture ('invalid-' + [guid]::NewGuid().ToString('N'))
[void][System.IO.Directory]::CreateDirectory($bad)
$rejected = $false
try { Assert-Private $bad } catch { $rejected = ($_.Exception.Message -eq 'OWNER_ONLY_ACL_REQUIRED') }
if (-not $rejected) { throw 'INVALID_ACL_NOT_REJECTED' }
Write-Output 'EXISTING_INVALID_ACL_REJECTED=PASS'
Write-Output 'LIVE_NOT_STARTED'
Write-Output 'NETWORK_CALLS=0'
Write-Output 'PS51_ACL_COMPAT_TEST_PASS'
