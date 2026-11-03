"""Bounded offline restoration of an explicitly pinned GitHub custody packet.

Historical artifacts are opaque research evidence, never production inputs. No
network, credentials, local drive defaults, or writes occur on import.
"""
from __future__ import annotations
import base64
from dataclasses import asdict
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
from .stage04_evidence_packet import restore_from_remote
from .evidence_journal import study_capacity

MAX_EXPANDED_BYTES = 80_000_000
MAX_ARCHIVE_BYTES = 10 * 1024 * 1024

class Snapshot:
    def __init__(self, root):
        self.root = Path(root).resolve()
    def get_file(self, path, branch):
        p = safe_target(self.root, path)
        if not p.is_file():
            return None
        body = p.read_bytes()
        return body, hashlib.sha256(body).hexdigest()

def safe_target(root: Path, name: str) -> Path:
    if not isinstance(name, str) or '\\' in name or ':' in name:
        raise ValueError('UNSAFE_ARTIFACT_PATH')
    relative = PurePosixPath(name)
    if relative.is_absolute() or not relative.parts or any(x in ('..', '.') for x in relative.parts):
        raise ValueError('UNSAFE_ARTIFACT_PATH')
    target = root.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('ARTIFACT_PATH_ESCAPES_ROOT')
    return target

def restore(snapshot, destination, *, study_id, branch, manifest_sha256):
    """Verify accepted Stage04 journal before decoding or extracting anything."""
    remote = Snapshot(snapshot)
    check = restore_from_remote(study_id=study_id, branch=branch, transport=remote,
                                expected_manifest_sha256=manifest_sha256)
    if not check.ok:
        raise ValueError(check.status)
    prefix = 'studies/' + study_id + '/receipts/'
    m = json.loads(remote.get_file(prefix+'manifest.json', branch)[0])['payload']
    chunks = []
    control = None
    for entry in m['entries']:
        record = json.loads(remote.get_file(prefix+entry['event_id']+'.json', branch)[0])['payload']
        payload = record['payload']
        if payload.get('kind') == 'custody-control-v1':
            if control is not None:
                raise ValueError('DUPLICATE_CONTROL')
            control = payload
        elif payload.get('kind') == 'custody-chunk-v1':
            chunks.append(payload)
        else:
            raise ValueError('UNEXPECTED_CUSTODY_RECORD')
    if control is None or len(chunks) != control['chunk_count']:
        raise ValueError('INCOMPLETE_CHUNK_SET')
    chunks.sort(key=lambda x:x['ordinal'])
    archive = bytearray()
    for i, chunk in enumerate(chunks):
        if chunk['ordinal'] != i:
            raise ValueError('CHUNK_SEQUENCE_MISMATCH')
        part = base64.b64decode(chunk['data_base64'], validate=True)
        if hashlib.sha256(part).hexdigest() != chunk['sha256']:
            raise ValueError('CHUNK_HASH_MISMATCH')
        archive.extend(part)
        if len(archive) > study_capacity(study_id):
            raise ValueError('ARCHIVE_SIZE_LIMIT')
    if (len(archive) != control['archive_bytes'] or
            hashlib.sha256(archive).hexdigest() != control['archive_sha256']):
        raise ValueError('ARCHIVE_HASH_MISMATCH')
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('FRESH_DESTINATION_REQUIRED')
    # Bounded streaming decompression: reject bombs before materializing members.
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as stream:
        expanded = stream.read(MAX_EXPANDED_BYTES + 1)
    if len(expanded) > MAX_EXPANDED_BYTES:
        raise ValueError('EXPANSION_LIMIT')
    with tarfile.open(fileobj=io.BytesIO(expanded), mode='r:') as tar:
        members = tar.getmembers()
        names = [x.name for x in members]
        if len(names) != len(set(names)) or len(members) > 2000:
            raise ValueError('DUPLICATE_OR_EXCESS_MEMBERS')
        extracted = {}
        for member in members:
            safe_target(destination, member.name)
            if not member.isfile() or member.size > MAX_EXPANDED_BYTES:
                raise ValueError('UNSAFE_TAR_MEMBER')
            extracted[member.name] = tar.extractfile(member).read()
    inventory = json.loads(extracted['inventory.json'])
    expected = {'inventory.json'}
    for item in inventory['files']:
        if item['transfer_status'] != 'INCLUDED':
            continue
        name = 'objects/'+item['sha256']
        expected.add(name)
        raw = extracted.get(name)
        if raw is None or len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('ORIGINAL_FILE_HASH_MISMATCH')
    if expected != set(extracted):
        raise ValueError('UNINDEXED_ARCHIVE_CONTENT')
    # Validate entire inventory before first write. Restore once; never overwrite.
    destination.mkdir(parents=True)
    for name, raw in extracted.items():
        target = safe_target(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return {'status':'RESTORE_VERIFIED_APPLICATION_ONLY',
            'stage04':asdict(check), 'files_in_inventory':len(inventory['files']),
            'unique_objects_restored':len(extracted)-1,
            'original_bytes_restored':sum(len(x) for k,x in extracted.items() if k!='inventory.json'),
            'archive_sha256':control['archive_sha256'],
            'full_reproducible':False, 'scientific_state':'PIT_FAIL_HOLD',
            'blocked_files':sum(x['transfer_status']!='INCLUDED' for x in inventory['files'])}

def materialize(restored, historical_prefix, destination):
    """Rebuild a historical relative tree from content-addressed verified bytes."""
    root, destination = Path(restored).resolve(), Path(destination).resolve()
    inventory = json.loads((root/'inventory.json').read_bytes())
    selected = [x for x in inventory['files'] if x['path'].startswith(historical_prefix)]
    if not selected or any(x['transfer_status']!='INCLUDED' for x in selected):
        raise ValueError('SOURCE_MISSING_OR_WITHHELD')
    if destination.exists():
        raise ValueError('FRESH_DESTINATION_REQUIRED')
    for item in selected:
        safe_target(destination, item['path'][len(historical_prefix):])
        raw = (root/'objects'/item['sha256']).read_bytes()
        if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:
            raise ValueError('RESTORED_OBJECT_CHANGED')
    for item in selected:
        target = safe_target(destination, item['path'][len(historical_prefix):])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root/'objects'/item['sha256']).read_bytes())
    return len(selected)
