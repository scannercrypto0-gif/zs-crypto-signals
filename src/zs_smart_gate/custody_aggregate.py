"""Owner-approved 015 composite custody, not scientific source qualification."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .custody_restore import restore
from .evidence_journal import canonical_bytes, MIGRATION_015_CAP_BYTES

ALLOWED_STUDIES = frozenset(('custody-010-014-015','custody-015-verification',
                            'custody-010-014-015-raw'))

def aggregate_bytes(root, studies):
    if set(studies)!=ALLOWED_STUDIES or len(studies)!=len(ALLOWED_STUDIES):
        raise ValueError('UNEXPECTED_CONSOLIDATED_STUDY_SET')
    size=0
    for study in studies:
        folder=Path(root)/'studies'/study
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError('STUDY_FOLDER_REQUIRED')
        for p in folder.rglob('*'):
            if p.is_symlink():
                raise ValueError('SYMLINK_NOT_ALLOWED')
            if p.is_file():size+=p.stat().st_size
        if size>MIGRATION_015_CAP_BYTES:
            raise ValueError('CONSOLIDATED_48MIB_LIMIT')
    return size

def restore_aggregate(snapshot, destination, anchor):
    packets=anchor['packets']
    size=aggregate_bytes(snapshot,[x['study_id']for x in packets])
    if size!=anchor['combined_bytes']:
        raise ValueError('COMPOSITE_BYTE_COUNT_CHANGED')
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('FRESH_DESTINATION_REQUIRED')
    result={}
    for packet in packets:
        result[packet['study_id']]=restore(snapshot,destination/packet['study_id'],
             study_id=packet['study_id'],branch='evidence-migration-015',
             manifest_sha256=packet['manifest_sha256'])
    original=destination/'custody-010-014-015'
    supplement=destination/'custody-010-014-015-raw'
    old=json.loads((original/'inventory.json').read_bytes())
    raw=json.loads((supplement/'inventory.json').read_bytes())
    extra={x['path']:x for x in raw['files']}
    if len(extra)!=len(raw['files']):raise ValueError('DUPLICATE_SUPPLEMENT_PATH')
    required={x['path']for x in old['files']if x['transfer_status']=='BLOCKED_CAPACITY'}
    if set(extra)!=required:raise ValueError('SUPPLEMENT_SCOPE_MISMATCH')
    objects={}
    for item in old['files']:
        source=original
        if item['path']in extra:
            newer=extra[item['path']]
            if (newer['sha256'],newer['bytes'],newer['transfer_status'])!=(item['sha256'],item['bytes'],'INCLUDED'):
                raise ValueError('SUPPLEMENT_CHANGED_ORIGINAL_BYTES')
            item.update(newer);source=supplement
        if item['transfer_status']=='INCLUDED':
            body=(source/'objects'/item['sha256']).read_bytes()
            if len(body)!=item['bytes']or hashlib.sha256(body).hexdigest()!=item['sha256']:
                raise ValueError('COMPOSITE_OBJECT_CHANGED')
            objects[item['sha256']]=source/'objects'/item['sha256']
        elif item['transfer_status']not in ('WITHHELD_SECURITY','SANITIZED_REPORT_ONLY'):
            raise ValueError('ALLOWED_REQUIRED_MATERIAL_MISSING')
    combined=destination/'combined'
    (combined/'objects').mkdir(parents=True)
    for sha,source in objects.items():
        (combined/'objects'/sha).write_bytes(source.read_bytes())
    old.update(custody='ALL_ALLOWED_ORIGINAL_BYTES_RESTORED',full_reproducible=False,
               scientific_state='PIT_FAIL_HOLD',source_packet_manifests=packets)
    (combined/'inventory.json').write_bytes(canonical_bytes(old))
    return dict(status='GITHUB_ONLY_CUSTODY_PASS_PENDING_PM_ACCEPTANCE',
        allowed_original_paths=sum(x['transfer_status']=='INCLUDED'for x in old['files']),
        unique_original_objects=len(objects),combined_bytes=size,cap_bytes=MIGRATION_015_CAP_BYTES,
        security_withheld_paths=sum(x['transfer_status']=='WITHHELD_SECURITY'for x in old['files']),
        sanitized_report_only_paths=sum(x['transfer_status']=='SANITIZED_REPORT_ONLY'for x in old['files']),
        full_scientific_reproducible=False,scientific_state='PIT_FAIL_HOLD',parts=result)
