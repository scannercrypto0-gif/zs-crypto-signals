"""014 explicit one-shot authenticated clock probe, no retries/system mutations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import struct
import time
from zs_smart_gate.stage03_nts_authority import parse_ke,ke_complete,ke_record,dns_identity,protected_packet,verify_packet
from zs_smart_gate.stage03_source_clock import stamp


def run(root):
    from OpenSSL import SSL,crypto
    from cryptography import x509
    import certifi
    root.mkdir(exist_ok=False)
    result = dict(status='STARTED',TCP_connections=0,UDP_datagrams=0,system_changes=False,
                  publication_proved=False,forward_armed=False,absolute_UTC_certified=False)
    tcp = connection = None
    try:
        context = SSL.Context(SSL.TLS_CLIENT_METHOD)
        context.set_min_proto_version(SSL.TLS1_3_VERSION)
        context.load_verify_locations(certifi.where())
        context.set_verify(SSL.VERIFY_PEER,lambda conn,cert,errno,depth,ok: bool(ok))
        context.set_alpn_protos([b'ntske/1'])
        result['TCP_connections'] = 1
        tcp = socket.create_connection(('time.cloudflare.com',4460),timeout=5)
        tcp.setblocking(False)
        connection = SSL.Connection(context,tcp)
        connection.set_connect_state()
        connection.set_tlsext_host_name(b'time.cloudflare.com')
        deadline = time.monotonic()+10
        def io(operation):
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('NTS_TLS_DEADLINE')
                try:
                    return operation()
                except SSL.WantReadError:
                    select.select([tcp],[],[],max(0,deadline-time.monotonic()))
                except SSL.WantWriteError:
                    select.select([],[tcp],[],max(0,deadline-time.monotonic()))
        io(connection.do_handshake)
        if connection.get_alpn_proto_negotiated() != b'ntske/1' or connection.get_protocol_version_name() != 'TLSv1.3':
            raise ValueError('NTS_TLS_PROFILE')
        cert = connection.get_peer_certificate().to_cryptography()
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
        if not dns_identity('time.cloudflare.com',names):
            raise ValueError('TLS_HOSTNAME_MISMATCH')
        result.update(TLS='TLSv1.3',ALPN='ntske/1',certificate_chain_verified=True,hostname_verified=True)
        for i,c in enumerate(connection.get_peer_cert_chain()):
            (root/('certificate-'+str(i)+'.pem')).write_bytes(crypto.dump_certificate(crypto.FILETYPE_PEM,c))
        result['leaf_certificate_sha256'] = hashlib.sha256(crypto.dump_certificate(crypto.FILETYPE_ASN1,connection.get_peer_certificate())).hexdigest()
        request = ke_record(1,b'\0\0')+ke_record(4,b'\0\x0f')+ke_record(0)
        sent = 0
        while sent < len(request):
            sent += io(lambda: connection.send(request[sent:]))
        response = b''
        while not ke_complete(response):
            piece = io(lambda: connection.recv(4096))
            if not piece:
                raise ValueError('NTS_KE_EOF')
            response += piece
            if len(response) > 16384:
                raise ValueError('NTS_KE_CAP')
        negotiated = parse_ke(response,'time.cloudflare.com')
        # Keys/cookies stay in memory; do not persist credentials or TLS exporters.
        c2s = connection.export_keying_material(b'EXPORTER-network-time-security',32,b'\0\0\0\x0f\0')
        s2c = connection.export_keying_material(b'EXPORTER-network-time-security',32,b'\0\0\0\x0f\1')
        result.update(ke_records_sha256=hashlib.sha256(response).hexdigest(),cookie_count=len(negotiated['cookies']),
                      AEAD='AES_SIV_CMAC_256',key_material_persisted=False)
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.settimeout(3)
            sock.connect(('time.cloudflare.com',123))
            t1,m1 = time.time(),time.monotonic()
            tx,unique = stamp(t1),os.urandom(32)
            packet = protected_packet(b'\x23'+b'\0'*39+tx,unique,negotiated['cookies'][0],c2s,os.urandom(16))
            if len(packet) > 4096:
                raise ValueError('NTS_REQUEST_CAP')
            result['UDP_datagrams'] = 1
            sock.send(packet)
            raw = sock.recv(4097)
            t4,m4 = time.time(),time.monotonic()
        result['sample'] = verify_packet(raw,unique,s2c,tx,t1,t4,m4-m1)
        # Packet transcripts have opaque protocol cookies, never publish them.
        (root/'ntp-request.private').write_bytes(packet)
        (root/'ntp-response.private').write_bytes(raw)
        result.update(status='NTS_AUTHENTICATED_CLOCK_PARTIAL',request_bytes=len(packet),response_bytes=len(raw),
                      request_sha256=hashlib.sha256(packet).hexdigest(),response_sha256=hashlib.sha256(raw).hexdigest(),
                      limitation='Identity and AEAD verified in executor process. Exporter secrets deliberately not saved; independent reviewer repeats fresh protocol rather than offline re-verifying this tag. Authority absolute error/drift not attested.')
    except Exception as exc:
        result.update(status='STOPPED_NO_RETRY',error_type=type(exc).__name__,error=str(exc)[:160])
    finally:
        if connection is not None:
            try: connection.close()
            except Exception: pass
        if tcp is not None:
            tcp.close()
        (root/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-published-probe',action='store_true')
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    if not args.run_published_probe:
        raise SystemExit('NOT_ARMED_ZERO_NETWORK')
    root = Path(args.output).resolve()
    if root.drive.upper() != 'D:':
        raise SystemExit('PRIVATE_D_REQUIRED')
    print(json.dumps(run(root)))
