"""Discover protected Windows catalog locations; never issue an acceptance witness."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zs_smart_gate.ops24_catalog import member_proof
from zs_smart_gate.ops24_normal_clock import system_directory
from zs_smart_gate.stage05_contracts import canonical

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();target=args.output.resolve()
    if Path('D:/ZS-SMART-GATE').resolve() not in target.parents or target.exists():
        raise ValueError('FRESH_D_CATALOG_MAP_REQUIRED')
    rows={}
    for name in ('sc.exe','w32tm.exe','w32time.dll','svchost.exe','autotimesvc.dll'):
        proof=member_proof(system_directory()/name)
        if not proof['verified']:
            raise ValueError('OPERATOR_CATALOG_DISCOVERY_UNVERIFIED')
        rows[name]={k:proof[k] for k in ('file_sha256','catalog','catalog_sha256')}
    target.write_bytes(canonical(dict(schema='zs.ops24.catalog-map.v1',
        scope='DISCOVERY_ONLY_NOT_ACCEPTANCE',files=rows)))
    print('CATALOG_LOCATIONS_DISCOVERED_5_NOT_A_WORKER_WITNESS')

if __name__=='__main__':
    main()
