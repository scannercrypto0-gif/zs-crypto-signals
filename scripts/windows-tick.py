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
except Exception as exc:
    # pythonw has no stderr. Log startup failures without trusting project imports.
    # Fixed D destination, no traceback/arguments/credentials in incident data.
    import json
    from datetime import datetime, timezone
    try:
        destination = (root/'logs').resolve(strict=True)
        if destination.drive.upper() != 'D:':
            raise ValueError('D_ONLY')
        allowed={'FROZEN_CONFIG_CHANGED','DEPLOYMENT_CHECKSUM_MISMATCH','D_CONFIG_REQUIRED',
                 'SIMULATION_NETWORK_FORBIDDEN','D_PATH_ESCAPE','CORRUPT_RECEIPT'}
        category=str(exc) if str(exc) in allowed else type(exc).__name__
        health_file=destination/'health.json'
        previous={}
        if health_file.exists() and health_file.stat().st_size <= 16384:
            try: previous=json.loads(health_file.read_text(encoding='utf-8'))
            except (ValueError,OSError): pass
        now=datetime.now(timezone.utc)
        incident={'updated_utc':now.isoformat(),'last_failure_utc':now.isoformat(),
                  'last_success_utc':previous.get('last_success_utc'),'exit_code':2,
                  'current_error_category':category,'last_error_category':category,
                  'run_sha':locals().get('frozen',{}).get('revision'),
                  'deployment_config_sha':args.config_sha[:64], 'startup_verified':False,
                  'live_permission':'OFF','codex_required':False,'model_api_calls':0}
        text=json.dumps(incident,indent=2)
        temporary=health_file.with_suffix('.tmp')
        temporary.write_text(text,encoding='utf-8'); os.replace(temporary,health_file)
        (destination/f'incident-{int(now.timestamp())%8}.json').write_text(text,encoding='utf-8')
    except Exception:
        pass  # LastTaskResult=2 is still observable if the D volume is unavailable.
    raise SystemExit(2)
