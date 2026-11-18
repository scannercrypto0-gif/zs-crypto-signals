"""Private subprocess for the bounded Windows foreground entry point."""
import json
import os
from pathlib import Path
import subprocess
import sys

from .ops_windows_time import capture
from .ops_windows_watchdog import START


def sync_age(status):
    line = next((s for s in status.splitlines() if s.startswith("Last Successful Sync Time:")), "")
    if not line:
        return None
    env = dict(os.environ, ZS_SYNC_DISPLAY=line.split(":", 1)[1].strip())
    script = """
    $ErrorActionPreference='Stop'
    $culture=[Globalization.CultureInfo]::CurrentCulture
    $patterns=@($culture.DateTimeFormat.GetAllDateTimePatterns([char]'G'))
    $local=[DateTime]::ParseExact($env:ZS_SYNC_DISPLAY,[string[]]$patterns,$culture,
        [Globalization.DateTimeStyles]::AllowWhiteSpaces)
    $zone=[TimeZoneInfo]::Local
    if($zone.IsAmbiguousTime($local) -or $zone.IsInvalidTime($local)){exit 2}
    $utc=[TimeZoneInfo]::ConvertTimeToUtc($local,$zone)
    ([DateTime]::UtcNow-$utc).TotalSeconds.ToString([Globalization.CultureInfo]::InvariantCulture)
    """
    try:
        result = subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",script],
                                env=env, capture_output=True, text=True, timeout=8)
        return float(result.stdout.strip()) if result.returncode == 0 else None
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return None


if __name__ == "__main__":
    if sys.stdin.buffer.readline() != START:
        raise SystemExit(2)
    result = capture(Path(sys.argv[1]), sync_age=sync_age)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["spot"]["status"] == "SOURCE_READBACK_PASS_CLOCK_PENDING" else 2)
