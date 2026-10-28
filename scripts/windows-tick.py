"""Task Scheduler entry point; Python must start with -B. Never opens a socket."""
import argparse
import os
from pathlib import Path
import sys

# Set task-owned environment before package imports or tempfile discovery.
root = Path('D:/ZS-SMART-GATE')
for key, suffix in {'TEMP':'temp', 'TMP':'temp', 'TMPDIR':'temp',
                    'PIP_CACHE_DIR':'cache/pip', 'PYTHONPYCACHEPREFIX':'cache/pycache',
                    'XDG_CACHE_HOME':'cache', 'UV_CACHE_DIR':'cache/uv'}.items():
    os.environ[key] = str(root/suffix)
os.environ['PYTHONNOUSERSITE'] = '1'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config', required=True)
parser.add_argument('--config-sha', required=True)
parser.add_argument('--state-dir', required=True)
parser.add_argument('--log-dir', required=True)
parser.add_argument('--dry-run', required=True, action='store_true')
parser.add_argument('--once', required=True, action='store_true')
args = parser.parse_args()
def deny_network(event, arguments):
    if event.startswith('socket.'):
        raise RuntimeError('SIMULATION_NETWORK_FORBIDDEN')

sys.addaudithook(deny_network)
try:
    # Verify the pinned package bytes before importing any project code.
    import hashlib
    import json
    config_file = Path(args.config).resolve(strict=True)
    if config_file.drive.upper() != 'D:' or config_file.stat().st_size > 65536:
        raise ValueError('D_CONFIG_REQUIRED')
    frozen = json.loads(config_file.read_text(encoding='utf-8-sig'))
    config_digest = hashlib.sha256(json.dumps(frozen, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    if config_digest != args.config_sha or not frozen.get('files'):
        raise ValueError('FROZEN_CONFIG_CHANGED')
    checkout = Path.cwd().resolve(strict=True)
    for name, checksum in frozen['files'].items():
        item = (checkout/name).resolve(strict=True)
        if not item.is_relative_to(checkout) or hashlib.sha256(item.read_bytes()).hexdigest() != checksum:
            raise ValueError('DEPLOYMENT_CHECKSUM_MISMATCH')
    from zs_smart_gate.windows_operations import d_path, load_config, scheduled_tick
    config_path = d_path(args.config)
    config = load_config(config_path, args.config_sha)
    result = scheduled_tick(config, args.config_sha, d_path(Path.cwd()),
                            d_path(args.state_dir), d_path(args.log_dir))
    raise SystemExit(result['exit_code'])
except (ValueError, OSError) as exc:
    # Do not log attacker-supplied values or write outside validated directories.
    print('WINDOWS_RUNTIME_BLOCKED: ' + type(exc).__name__, file=sys.stderr)
    raise SystemExit(2)
