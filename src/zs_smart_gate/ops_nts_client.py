"""Operator-invoked NTS sampling and optional separately authorized Spot capture."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import os
import socket
import time

from .ops_nts_protocol import dns_identity, ke_complete, ke_record, parse_ke, protected_packet, stamp, verify_packet
from .ops_spot_preflight import public_get, run_preflight
from .stage05_contracts import ContractError, canonical, digest, utc_now

KE_HOST = "sth1.nts.netnod.se"
STAMP_HOST = "sth1-ts.nts.netnod.se"
KE_PORT, STAMP_PORT = 4460, 4123
MAX_SECONDS = 120


def dependencies(ca_file, ca_pin):
    from importlib.metadata import version
    from OpenSSL import SSL, crypto
    from cryptography import x509
    for name, expected in (("pyOpenSSL","25.3.0"), ("cryptography","46.0.5"),
                           ("cffi","2.0.0"), ("pycparser","3.0"), ("typing-extensions","4.15.0")):
        if version(name) != expected:
            raise ContractError("NTS_DEPENDENCY_PIN_MISMATCH")
    if digest(Path(ca_file).read_bytes()) != ca_pin:
        raise ContractError("NTS_CA_BUNDLE_PIN_MISMATCH")
    return SSL, crypto, x509


def establish(ca_file, ca_pin, approved_ip, timeout):
    SSL, crypto, x509 = dependencies(ca_file, ca_pin)
    addresses = {entry[4][0] for entry in socket.getaddrinfo(STAMP_HOST, STAMP_PORT, socket.AF_INET, socket.SOCK_DGRAM)}
    if approved_ip not in addresses:
        raise ContractError("NTS_TIMESTAMP_DNS_PIN_MISMATCH")
    first = socket.getaddrinfo(KE_HOST, KE_PORT, socket.AF_INET, socket.SOCK_STREAM)[0][4]
    context = SSL.Context(SSL.TLS_CLIENT_METHOD)
    context.set_min_proto_version(SSL.TLS1_3_VERSION)
    context.set_max_proto_version(SSL.TLS1_3_VERSION)
    context.set_verify(SSL.VERIFY_PEER, lambda connection, cert, errno, depth, ok: bool(ok))
    context.load_verify_locations(str(ca_file))
    context.set_alpn_protos([b"ntske/1"])
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as tcp:
        tcp.settimeout(timeout())
        tcp.connect(first)
        connection = SSL.Connection(context, tcp)
        connection.set_connect_state()
        connection.set_tlsext_host_name(KE_HOST.encode("ascii"))

        def step(operation):
            import select
            while True:
                seconds = timeout()
                try:
                    return operation()
                except SSL.WantReadError:
                    select.select([tcp], [], [], seconds)
                except SSL.WantWriteError:
                    select.select([], [tcp], [], seconds)

        tcp.setblocking(False)
        step(connection.do_handshake)
        certificate = connection.get_peer_certificate()
        san = certificate.to_cryptography().extensions.get_extension_for_class(x509.SubjectAlternativeName)
        if (connection.get_protocol_version_name() != "TLSv1.3"
                or connection.get_alpn_proto_negotiated() != b"ntske/1"
                or not dns_identity(KE_HOST, san.value.get_values_for_type(x509.DNSName))):
            raise ContractError("NTS_TLS_PEER_REJECTED")
        message = ke_record(1, bytes(2)) + ke_record(4, bytes((0,15))) + ke_record(0)
        sent = 0
        while sent < len(message):
            count = step(lambda: connection.send(message[sent:]))
            if not count:
                raise ContractError("NTS_KE_SEND_EOF")
            sent += count
        raw = bytearray()
        while not ke_complete(raw):
            chunk = step(lambda: connection.recv(4096))
            raw.extend(chunk)
            if not chunk or len(raw) > 16384:
                raise ContractError("NTS_KE_EOF_OR_SIZE")
        keys = parse_ke(bytes(raw), approved_ip, STAMP_PORT)
        label = b"EXPORTER-network-time-security"
        c2s, s2c = [connection.export_keying_material(label, 32, bytes((0,0,0,15,side)))
                    for side in (0,1)]
        peer = digest(crypto.dump_certificate(crypto.FILETYPE_ASN1, certificate))
    return c2s, s2c, list(dict.fromkeys(keys["cookies"]))[:4], peer


def take_sample(root, index, address, cookie, c2s, s2c, timeout):
    unique = os.urandom(32)
    with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as udp:
        udp.settimeout(timeout())
        udp.connect((address, STAMP_PORT))
        t1, m1 = time.time(), time.monotonic_ns()
        tx = stamp(t1)
        packet = protected_packet(bytes((0x23,))+bytes(39)+tx, unique, cookie, c2s, os.urandom(16))
        udp.send(packet)
        response = udp.recv(4097)
        t4, m4 = time.time(), time.monotonic_ns()
    (root/f"request-{index}.private").write_bytes(packet)
    (root/f"response-{index}.private").write_bytes(response)
    measurement = verify_packet(response, unique, s2c, tx, t1, t4, (m4-m1)/1e9)
    return {**measurement, "send_mono_ns":m1, "receive_mono_ns":m4, "request_sha256":digest(packet),
            "response_sha256":digest(response)}


def conditional_brackets(samples, markers):
    if len(samples) != 4 or len(markers) != 2:
        return None
    result = []
    for index, marker in enumerate(markers):
        before, after = samples[index*2:index*2+2]
        if not before["receive_mono_ns"] < marker < after["send_mono_ns"]:
            return None
        def edge(row, sign):
            return row["sample_local_received"] + row["offset_seconds"] + sign*row["conditional_radius_seconds"]
        low, high = edge(before,-1), edge(after,1)
        if not 0 <= high-low < 1.5:
            return None
        result.append({"lower_utc":datetime.fromtimestamp(low, timezone.utc).isoformat(),
                       "upper_utc":datetime.fromtimestamp(high, timezone.utc).isoformat(),
                       "width_seconds":high-low, "marker_mono_ns":marker})
    if result[0]["upper_utc"] > result[1]["lower_utc"]:
        return None
    return result


def run(root, *, ca_file, ca_pin, approved_ip, time_end, spot_end=None):
    """Secrets stay in memory; private NTS packets never belong in GitHub."""
    start = time.monotonic()
    summary = {"schema":"zs.ops.nts-preflight.v1", "status":"STARTED", "samples":[],
               "clock_absolute":"NOT_VERIFIED", "spot":None, "trading_authorized":False,
               "ke_attempts":0,"udp_attempts":0}
    def timeout():
        duration = min(5, MAX_SECONDS-(time.monotonic()-start),
                       (time_end-datetime.now(timezone.utc)).total_seconds())
        if duration <= 0:
            raise ContractError("NTS_DEADLINE")
        return duration
    def flush():
        temp = root/"summary.unfinished"
        temp.write_bytes(canonical(summary))
        temp.replace(root/"summary.json")

    def record(entry):
        with (root/"spot.jsonl").open("ab") as out:
            out.write(canonical(entry)+b"\n")
            out.flush()
            os.fsync(out.fileno())

    def sample():
        index = len(summary["samples"])
        summary["udp_attempts"] += 1
        flush()
        row = take_sample(root, index, approved_ip, cookies[index], c2s, s2c, timeout)
        summary["samples"].append(row)
        flush()

    try:
        summary["ke_attempts"] = 1
        flush()
        c2s, s2c, cookies, peer = establish(ca_file, ca_pin, approved_ip, timeout)
        summary["peer_certificate_sha256"] = peer
        summary["trust_bundle_sha256"] = ca_pin
        summary["timestamp_ip"] = approved_ip
        markers = []
        if spot_end is not None:
            attempt = 0
            def get(path, params, limit):
                nonlocal attempt
                attempt += 1
                if attempt == 5:
                    sample()
                remaining = (spot_end-datetime.now(timezone.utc)).total_seconds()
                if remaining <= 0:
                    raise ContractError("SPOT_WINDOW_CLOSED")
                answer = public_get(path, params, min(limit, remaining, timeout()))
                if isinstance(answer[2], bytes) and len(answer[2]) <= 262144:
                    (root/f"spot-response-{attempt}.private").write_bytes(answer[2])
                if attempt == 5:
                    markers.append(time.monotonic_ns())
                    sample()
                return answer
            summary["spot"] = run_preflight(get=get, monotonic=time.monotonic,
                                            utc_now=lambda:utc_now(lambda:datetime.now(timezone.utc)), record=record)
            if summary["spot"]["status"] != "SOURCE_READBACK_PASS_CLOCK_PENDING":
                raise ContractError("SPOT_PREFLIGHT_BLOCKED")
        else:
            sample()
            markers.append(time.monotonic_ns())
            sample()
        time.sleep(.25)
        sample()
        markers.append(time.monotonic_ns())
        sample()
        summary["conditional_brackets"] = conditional_brackets(summary["samples"], markers)
        summary["status"] = ("AUTHENTICATED_CONDITIONAL_ONLY" if summary["conditional_brackets"]
                             else "AUTHENTICATED_BRACKET_NOT_ADMISSIBLE")
    except Exception as exc:
        summary["status"] = "STOPPED_NO_RETRY"
        summary["reason"] = str(exc) if isinstance(exc, ContractError) else type(exc).__name__
    finally:
        flush()
    return summary
