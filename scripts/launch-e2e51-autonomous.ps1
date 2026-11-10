param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$Head)
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
        & py -3.12 -B (Join-Path $PSScriptRoot 'e2e51-autonomous.py') --head $Head
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
