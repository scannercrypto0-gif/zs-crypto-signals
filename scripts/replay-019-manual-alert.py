"""GitHub-only019 synthetic replay; source and original history are pinned.

Never connects to market/time services. Disables sockets during computation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
from zs_smart_gate.evidence_journal import canonical_bytes
from zs_smart_gate.manual_alert019 import evaluate
from zs_smart_gate.manual_sensitivity019 import fixture,pack_fixture,unpack_fixture,comparison

PARENT='f8f9507ff45a914edabfdea19c90155d2c7f01d5'


def main():
    p=argparse.ArgumentParser();p.add_argument('--github018',required=True);p.add_argument('--output',required=True)
    args=p.parse_args()
    def denied(*a,**k):raise RuntimeError('NETWORK_DISABLED_DURING_019_REPLAY')
    socket.socket=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    root=Path('research/stage03-019')
    if subprocess.check_output(['git','-C',args.github018,'rev-parse','HEAD'],text=True).strip()!=PARENT:
        raise ValueError('ORIGINAL018_CHECKOUT_NOT_PINNED')
    history=json.loads((root/'preserved-git-blobs.json').read_bytes())
    for name,sha in history.items():
        for directory in ('.',args.github018):
            if subprocess.check_output(['git','-C',directory,'rev-parse','HEAD:'+name],text=True).strip()!=sha:
                raise ValueError('PRE019_FROZEN_FILE_CHANGED:'+name)
    hashes=json.loads((root/'manifest.json').read_bytes())
    for name,sha in hashes.items():
        if Path(name).name!=name or hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('019_INPUT_MANIFEST_CHANGED')
    source=json.loads((root/'synthetic-source.json').read_bytes())
    if canonical_bytes(source)!=canonical_bytes(pack_fixture(fixture())):
        raise ValueError('SYNTHETIC_SOURCE_NOT_REPRODUCED')
    decision=evaluate(**unpack_fixture(source));sensitivity=comparison()
    for name,value in [('baseline-decision.json',decision),('sensitivity.json',sensitivity)]:
        if canonical_bytes(value)!=(root/name).read_bytes():raise ValueError('019_RESULT_NOT_EXACT:'+name)
    if decision['ABSOLUTE_UTC_PIT']!='HOLD' or decision['publishable'] or decision['OOS_QUALIFIED']:
        raise ValueError('FORBIDDEN_PROMOTION')
    result=dict(source='PINNED_GITHUB_ONLY',synthetic_only=True,preserved_files=len(history),
        original_parent=PARENT,scenarios=len(sensitivity['cases']),
        decision_sha256=hashlib.sha256(canonical_bytes(decision)).hexdigest(),
        sensitivity_sha256=hashlib.sha256(canonical_bytes(sensitivity)).hexdigest(),
        relative_status=decision['status'],ABSOLUTE_UTC_PIT='HOLD',publishable=False,
        forward='NOT_ARMED',new_OOS=0,new_provider_requests=0,sockets='DISABLED')
    Path(args.output).write_bytes(canonical_bytes(result))
    print('ZS019_REPRODUCED='+json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
