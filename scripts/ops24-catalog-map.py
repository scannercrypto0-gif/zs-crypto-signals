"""Discover protected Windows catalog locations; never issue an acceptance witness."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zs_smart_gate.ops24_catalog import member_proof
from zs_smart_gate.ops24_normal_clock import system_directory
from zs_smart_gate.stage05_contracts import canonical

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--head');parser.add_argument('--tree')
    args=parser.parse_args();target=args.output.resolve()
    if Path('D:/ZS-SMART-GATE').resolve() not in target.parents or target.exists():
        raise ValueError('FRESH_D_CATALOG_MAP_REQUIRED')
    rows={}
    for name in ('sc.exe','w32tm.exe','w32time.dll','svchost.exe','autotimesvc.dll'):
        proof=member_proof(system_directory()/name)
        if not proof['verified']:
            raise ValueError('OPERATOR_CATALOG_DISCOVERY_UNVERIFIED')
        rows[name]={k:proof[k] for k in ('file_sha256','catalog','catalog_sha256')}
    if bool(args.head)!=bool(args.tree):raise ValueError('HEAD_TREE_PAIR_REQUIRED')
    record=dict(schema='zs.ops24.catalog-map.v2' if args.head else 'zs.ops24.catalog-map.v1',
        scope='DISCOVERY_ONLY_NOT_ACCEPTANCE',files=rows)
    if args.head:record.update(release_head=args.head,release_tree=args.tree)
    target.write_bytes(canonical(record))
    print('CATALOG_LOCATIONS_DISCOVERED_5_NOT_A_WORKER_WITNESS')

if __name__=='__main__':
    main()
