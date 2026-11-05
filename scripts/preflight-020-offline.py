"""Real pinned websocket parser exercised with byte buffers; sockets disabled."""
import argparse
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch
import websocket
from websocket._abnf import frame_buffer
from zs_smart_gate.pilot020 import Budget,canonical
from zs_smart_gate.pilot020_io import WebSocketOnce


class Sock:
    def __init__(self,raw):self.raw=io.BytesIO(raw)
    def recv(self,n,*args):
        data=self.raw.read(n)
        if not data:raise ValueError('TRUNCATED_TEST_FRAME')
        return data


class Fake:
    def __init__(self,raw,status=101):
        self.sock=Sock(raw);self.handshake_response=type('Response',(),dict(status=status))()
        self.frame_buffer=frame_buffer(lambda n:self.sock.recv(n),False);self.pongs=[]
    def recv_frame(self):return self.frame_buffer.recv_frame()
    def pong(self,raw):self.pongs.append(raw)
    def shutdown(self):pass


def parser_checks():
    if websocket.__version__!='1.9.0':raise ValueError('PINNED_WS_VERSION_REQUIRED')
    passed=[]
    def client(raw,status=101):
        f=Fake(raw,status);w=WebSocketOnce(Budget())
        with patch('websocket.create_connection',return_value=f):w.connect()
        return w,f
    w,f=client(b'\x89\x01x\x81\x03abc')
    assert w.receive()[0] is None and f.pongs==[b'x']
    assert w.receive()[0]==b'abc';passed.append('PING_PAYLOAD_ECHO_AND_TEXT_RAW')
    w,f=client(b'\x01\x02ab\x80\x01c')
    assert w.receive()[0] is None and w.receive()[0]==b'abc'
    assert w.budget.frames==2 and w.budget.messages==1;passed.append('BOUNDED_FRAGMENT_REASSEMBLY')
    for name,raw in [('TRUNCATED',b'\x81\x03a'),('OVERSIZED_DECLARED_FRAME',b'\x81\x7e\x20\x01'),
                     ('MASKED_SERVER_FRAME',b'\x81\x81'),('BINARY_SCOPE',b'\x82\x01x')]:
        w,f=client(raw)
        try:w.receive()
        except Exception:passed.append(name)
        else:raise AssertionError(name)
    try:client(b'',302)
    except ValueError:passed.append('REDIRECT_REJECTED_WITHOUT_SECOND_CONNECTION')
    else:raise AssertionError('REDIRECT')
    return passed


def main():
    p=argparse.ArgumentParser();p.add_argument('--github019');p.add_argument('--output',required=True);a=p.parse_args()
    def denied(*args,**kwargs):raise RuntimeError('NETWORK_DISABLED_020_A')
    socket.socket=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    preserved=json.loads(Path('research/stage03-020/preserved-git-blobs.json').read_bytes())
    if a.github019:
        if subprocess.check_output(['git','-C',a.github019,'rev-parse','HEAD'],text=True).strip()!='2f4c6266fb88893dbb1f2e1805f28afdacca1bbb':
            raise ValueError('ORIGINAL019_NOT_PINNED')
        for path,sha in preserved.items():
            for directory in ('.',a.github019):
                actual=subprocess.check_output(['git','-C',directory,'rev-parse','HEAD:'+path],text=True).strip()
                if actual!=sha:raise ValueError('FROZEN_FILE_CHANGED:'+path)
    result=dict(status='020_A_OFFLINE_ENGINEERING_CHECKS_PASS',native_ws_parser_checks=parser_checks(),
        preserved_blob_count=len(preserved),history_verified_by_git=bool(a.github019),market_requests=0,
        phase_B='020_FIELD_PREFLIGHT_BLOCKED_PENDING_INDEPENDENT_REVIEW',synthetic_only=True)
    Path(a.output).write_bytes(canonical(result));print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
