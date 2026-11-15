param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$Head, [switch]$Live, [switch]$AccountAReadyNoOtherConsumer)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$actual = git -C $repo rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $actual -cne $Head) { throw 'CHECKOUT_SHA_MISMATCH' }
$dirty = git -C $repo status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0 -or $dirty) { throw 'CHECKOUT_NOT_CLEAN' }
$secretsRoot = Join-Path $env:LOCALAPPDATA 'ZS-SmartGate\stage05-secrets'
$mapping = @{
    'signals-token' = 'ZS_SIGNALS_BOT_TOKEN'
    'signals-chat-a' = 'ZS_SIGNALS_CHAT_ID_A'
    'signals-chat-b' = 'ZS_SIGNALS_CHAT_ID_B'
    'interactive-token' = 'ZS_INTERACTIVE_BOT_TOKEN'
    'interactive-allowed-users' = 'ZS_INTERACTIVE_ALLOWED_USER_IDS'
    'interactive-allowed-chats' = 'ZS_INTERACTIVE_ALLOWED_CHAT_IDS'
    'analytics-token' = 'ZS_ANALYTICS_BOT_TOKEN'
    'analytics-chat' = 'ZS_ANALYTICS_CHAT_ID'
}
$missing = @($mapping.Keys | Where-Object {
    -not (Test-Path -LiteralPath (Join-Path $secretsRoot ($_ + '.dpapi')) -PathType Leaf)
})
$owner = [Security.Principal.WindowsIdentity]::GetCurrent().User
function Assert-Private([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    $acl = Get-Acl -LiteralPath $Path
    $rules = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        ($item.PSIsContainer -and !$acl.AreAccessRulesProtected) -or $acl.GetOwner([Security.Principal.SecurityIdentifier]) -ne $owner -or
        $rules.Count -ne 1 -or $rules[0].IdentityReference -ne $owner -or $rules[0].AccessControlType -ne 'Allow') {
        throw 'OWNER_ONLY_ACL_REQUIRED'
    }
}
if ($missing.Count) { throw 'BLOCKED_MISSING_LOCAL_CONFIGURATION' }
Assert-Private $secretsRoot
foreach ($name in $mapping.Keys) { Assert-Private (Join-Path $secretsRoot ($name + '.dpapi')) }
$root = 'D:\ZS-SMART-GATE\stage51-final-003-a-retry1'
if (!(Test-Path -LiteralPath $root)) {
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner($owner)
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($owner,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    [void][IO.FileSystemAclExtensions]::Create([IO.DirectoryInfo]::new($root),$acl)
}
Assert-Private $root
$loaded = @()
$originalPythonPath = $env:PYTHONPATH
$code = 2
try {
    if ($missing.Count -eq 0) {
        foreach ($name in $mapping.Keys) {
            $key = $mapping[$name]
            if ([Environment]::GetEnvironmentVariable($key, 'Process')) {
                throw 'AMBIGUOUS_SECRET_CONFIGURATION'
            }
            $encrypted = [IO.File]::ReadAllText((Join-Path $secretsRoot ($name + '.dpapi')))
            $secure = ConvertTo-SecureString -String $encrypted
            $ptr = [IntPtr]::Zero
            try {
                $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
                [Environment]::SetEnvironmentVariable($key,
                    [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr), 'Process')
                $loaded += $key
            } finally {
                if ($ptr -ne [IntPtr]::Zero) {
                    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
                }
                $secure.Dispose()
            }
        }
    } elseif ($missing.Count -ne $mapping.Count) {
        throw 'INCOMPLETE_DPAPI_CONFIGURATION'
    }
    $env:PYTHONPATH = Join-Path $repo 'src'
    Push-Location -LiteralPath $repo
    try {
        $runArgs = @('--head',$Head)
        if ($Live) { $runArgs += '--live' }
        if ($AccountAReadyNoOtherConsumer) { $runArgs += '--account-a-ready-no-other-consumer' }
        & py -3.12 -B (Join-Path $PSScriptRoot 'stage51-final-once.py') @runArgs
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
} catch {
    Write-Output 'BLOCKED_MISSING_LOCAL_CONFIGURATION_OR_LAUNCH_ERROR'
} finally {
    foreach ($key in $loaded) {
        [Environment]::SetEnvironmentVariable($key, $null, 'Process')
    }
    $env:PYTHONPATH = $originalPythonPath
}
exit $code
