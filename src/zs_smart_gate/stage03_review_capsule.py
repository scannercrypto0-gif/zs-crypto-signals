"""Read-only verification against an externally supplied manifest digest."""
import hashlib
import json
from pathlib import Path, PurePosixPath


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_capsule(root, manifest_path, expected_sha256):
    root = Path(root).resolve(strict=True)
    manifest_path = Path(manifest_path)
    if file_hash(manifest_path) != expected_sha256:
        raise ValueError('EXTERNAL_MANIFEST_ANCHOR_MISMATCH')
    manifest = json.loads(manifest_path.read_bytes())
    checked = []
    seen = set()
    for item in manifest['files']:
        rel = PurePosixPath(item['path'])
        if rel.is_absolute() or '..' in rel.parts or ':' in item['path'] or '\\' in item['path'] or item['path'] in seen:
            raise ValueError('CAPSULE_PATH_REJECTED')
        seen.add(item['path'])
        path = (root/str(rel)).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError('CAPSULE_ESCAPE')
        if path.stat().st_size != item['bytes'] or file_hash(path) != item['sha256']:
            raise ValueError('CAPSULE_BYTES_CHANGED:'+item['path'])
        checked.append(item['path'])
    return dict(status='BYTE_VERIFIED_NOT_INDEPENDENT_SCIENTIFIC_REVIEW', checked=len(checked),
                external_anchor=expected_sha256, scientific_approval=False)
