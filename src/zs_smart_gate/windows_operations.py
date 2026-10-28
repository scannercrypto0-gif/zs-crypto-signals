"""D-only, pinned, offline Windows deployment helpers. No LIVE dispatcher."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import sys
import tempfile

ENV_DIRS = ('TEMP', 'TMP', 'TMPDIR', 'PIP_CACHE_DIR', 'PYTHONPYCACHEPREFIX',
            'XDG_CACHE_HOME', 'UV_CACHE_DIR')


def d_path(value, *, resolver=None):
    """Validate both spelling and canonical target; UNC and missing targets fail."""
    spelled = PureWindowsPath(str(value))
    if not spelled.is_absolute() or spelled.drive.upper() != 'D:':
        raise ValueError('D_ONLY_PROJECT_STORAGE_REQUIRED')
    resolved = (resolver or (lambda p: Path(p).resolve(strict=True)))(str(value))
    canonical = PureWindowsPath(str(resolved))
    if not canonical.is_absolute() or canonical.drive.upper() != 'D:':
        raise ValueError('D_PATH_ESCAPE')
    return Path(resolved)


def storage_audit(*, repo, state, logs, executable=None, environ=None, resolver=None,
                  prefix=None, temp=None):
    env = os.environ if environ is None else environ
    values = {'repo': repo, 'state': state, 'logs': logs,
              'python': executable or sys.executable, 'prefix': prefix or sys.prefix,
              'tempfile': temp or tempfile.gettempdir()}
    values.update({key: env.get(key, '') for key in ENV_DIRS})
    actual = {key: str(d_path(value, resolver=resolver)) for key, value in values.items()}
    if not sys.dont_write_bytecode and environ is None:
        raise ValueError('START_PYTHON_WITH_-B')
    return {'status': 'D_ONLY_PROJECT_STORAGE_PASS', 'effective_paths': actual,
            'os_exception': 'Windows-managed Registry, TaskScheduler and Event Logs may write C:',
            'launcher_metadata': 'Codex application metadata is outside project redirection control'}


def canonical_sha(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def verify_deployment(config, repo):
    if set(config) != {'version', 'revision', 'files', 'mode', 'scope'}:
        raise ValueError('DEPLOYMENT_SCHEMA')
    if config['version'] != 1 or config['mode'] != 'SIMULATION_ONLY' or config['scope'] != []:
        raise ValueError('LIVE_GATE_BLOCKED')
    revision = config['revision']
    if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
        raise ValueError('PINNED_REVISION_REQUIRED')
    files = config['files']
    if not isinstance(files, dict) or not files or len(files) > 256:
        raise ValueError('DEPLOYMENT_FILES_REQUIRED')
    actual_names = {p.relative_to(repo).as_posix() for p in (repo/'src').rglob('*.py')}
    actual_names.update(p.relative_to(repo).as_posix() for p in (repo/'scripts').glob('*') if p.is_file())
    if set(files) != actual_names:
        raise ValueError('DEPLOYMENT_FILE_SET_CHANGED')
    for name, expected in files.items():
        p = (repo / name).resolve(strict=True)
        if not p.is_relative_to(repo.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError('DEPLOYMENT_CHECKSUM_MISMATCH')
    return canonical_sha(config)


def load_config(path, expected_sha):
    if path.stat().st_size > 65536:
        raise ValueError('CONFIG_TOO_LARGE')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if canonical_sha(data) != expected_sha:
        raise ValueError('FROZEN_CONFIG_CHANGED')
    return data


def write_bounded_result(logs, result):
    # Fixed ring: at most sixteen small JSON diagnostics, not a permanent journal.
    index = int(datetime.now(timezone.utc).timestamp() // 60) % 16
    encoded = json.dumps(result, sort_keys=True, indent=2, allow_nan=False)
    if len(encoded.encode()) > 65536:
        raise ValueError('DIAGNOSTIC_TOO_LARGE')
    for name in (f'cycle-{index:02d}.json', 'status.json'):
        target = logs/name
        temporary = target.with_suffix('.tmp')
        temporary.write_text(encoded, encoding='utf-8')
        os.replace(temporary, target)


def scheduled_tick(config, config_sha, repo, state, logs):
    audit = storage_audit(repo=repo, state=state, logs=logs)
    verified = verify_deployment(config, repo)
    if verified != config_sha:
        raise ValueError('FROZEN_CONFIG_CHANGED')
    # Import after bytecode/temp/path validation, with no transport construction.
    from .windows_runner import Scope, tick
    result = tick(Scope(), state)
    result.update(run_sha=config['revision'], deployment_config_sha=verified,
                  python_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                  storage=audit, live_permission='OFF', approved_scope=[],
                  actual_successful_closed_event='NONE: SIMULATION_ONLY_EMPTY_SCOPE',
                  evidence_status='DURABLE_GITHUB_EVIDENCE_PENDING',
                  production_status='PRODUCTION_SIGNALS_NOT_AUTHORIZED',
                  execution_kind='LOCAL_OFFLINE_TICK_NOT_24_7_PROOF')
    write_bounded_result(logs, result)
    return result
