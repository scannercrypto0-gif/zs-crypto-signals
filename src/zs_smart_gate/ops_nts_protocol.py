"""RFC 8915 framing adapted from the repository Order014 verifier."""
import math
import struct
NTP_EPOCH = 2208988800


def stamp(value):
    seconds = value+NTP_EPOCH
    integer = int(seconds)
    return struct.pack('!II', integer, int((seconds-integer)*2**32))


def unstamp(raw):
    a, b = struct.unpack('!II', raw)
    return a-NTP_EPOCH+b/2**32


def parse_ntp(raw, request_transmit, t1, t4, elapsed_monotonic):
    if len(raw) < 48 or len(raw) > 512:
        raise ValueError('NTP_SIZE')
    leap, version, mode = raw[0] >> 6, (raw[0] >> 3) & 7, raw[0] & 7
    if leap == 3 or version != 4 or mode != 4 or not 1 <= raw[1] <= 15:
        raise ValueError('NTP_UNSYNCED_OR_MODE')
    if raw[24:32] != request_transmit:
        raise ValueError('NTP_ORIGIN_MISMATCH')
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (t1, t4, elapsed_monotonic)):
        raise ValueError('NTP_NONFINITE_TIME')
    if elapsed_monotonic < 0 or t4 < t1 or abs((t4-t1)-elapsed_monotonic) > .02:
        raise ValueError('LOCAL_CLOCK_STEP')
    t2, t3 = unstamp(raw[32:40]), unstamp(raw[40:48])
    root_delay = struct.unpack('!i', raw[4:8])[0]/65536
    dispersion = struct.unpack('!I', raw[8:12])[0]/65536
    delay = (t4-t1)-(t3-t2)
    if root_delay < 0 or t3 < t2 or delay < -.001 or abs(t2-t1) > 86400:
        raise ValueError('NTP_INCONSISTENT_CLOCKS')
    offset = ((t2-t1)+(t3-t4))/2
    radius = dispersion+root_delay/2+max(0, delay)/2+.001
    return dict(offset_seconds=offset, network_delay_seconds=delay,
                server_root_delay=root_delay, server_root_dispersion=dispersion,
                conditional_radius_seconds=radius,
                conditional_local_error_bound_seconds=abs(offset)+radius,
                conditional_below_one_second=abs(offset)+radius < 1,
                stratum=raw[1], sample_local_received=t4,
                authentication='NONE_NOT_NTS', status='PARTIAL_CONDITIONAL_UNAUTHENTICATED',
                absolute_UTC_certified=False,
                caveat='Assumes truthful server/root metadata, valid local timestamps and nonnegative network delays; not independent reviewer attestation.')


def ke_record(kind, body=b'', critical=True):
    return struct.pack('!HH', kind | (0x8000 if critical else 0), len(body))+body


def ke_complete(raw):
    pos = 0
    while pos+4 <= len(raw):
        kind, size = struct.unpack('!HH', raw[pos:pos+4])
        if pos+4+size > len(raw):
            return False
        pos += 4+size
        if kind & 0x7fff == 0:
            return True
    return False


def parse_ke(raw, allowed_host, allowed_port):
    if len(raw) > 16384:
        raise ValueError('NTS_KE_CAP')
    pos, protocol, algorithm, cookies, host, port, ended = 0, None, None, [], None, 123, False
    seen = set()
    while pos < len(raw):
        if pos+4 > len(raw):
            raise ValueError('NTS_KE_TRUNCATED')
        field, size = struct.unpack('!HH', raw[pos:pos+4])
        kind, critical = field & 0x7fff, bool(field & 0x8000)
        pos += 4
        body = raw[pos:pos+size]
        if len(body) != size:
            raise ValueError('NTS_KE_TRUNCATED')
        pos += size
        if ended:
            raise ValueError('NTS_KE_AFTER_END')
        if kind in (0,1,4,6,7):
            if kind in seen:
                raise ValueError('NTS_KE_DUPLICATE')
            seen.add(kind)
        if kind == 0:
            if size or not critical:
                raise ValueError('NTS_KE_END')
            ended = True
        elif kind == 1:
            if body != b'\0\0' or not critical:
                raise ValueError('NTS_PROTOCOL')
            protocol = 0
        elif kind == 4:
            if body != b'\0\x0f':
                raise ValueError('NTS_AEAD')
            algorithm = 15
        elif kind == 5:
            if not 16 <= len(body) <= 1024 or len(body) % 4:
                raise ValueError('NTS_COOKIE_SIZE')
            cookies.append(body)
        elif kind == 6:
            host = body.decode('ascii')
            if host != allowed_host:
                raise ValueError('NTS_UNAPPROVED_DESTINATION')
        elif kind == 7:
            if len(body) != 2 or int.from_bytes(body, 'big') != allowed_port:
                raise ValueError('NTS_UNAPPROVED_PORT')
            port = allowed_port
        elif kind in (2,3) or critical:
            raise ValueError('NTS_KE_ERROR_OR_UNKNOWN_CRITICAL')
    if not ended or protocol != 0 or algorithm != 15 or host != allowed_host or port != allowed_port or len(set(cookies)) < 4:
        raise ValueError('NTS_KE_INCOMPLETE')
    return dict(host=host, port=port, cookies=cookies, aead=algorithm)


def dns_identity(host, names):
    host = host.lower().rstrip('.')
    for name in names:
        name = name.lower().rstrip('.')
        if name == host or (name.startswith('*.') and host.count('.') == name.count('.') and host.endswith(name[1:])):
            return True
    return False


def extension(kind, body):
    if (len(body)+4) % 4:
        raise ValueError('NTS_EXTENSION_ALIGNMENT')
    return struct.pack('!HH', kind, len(body)+4)+body


def protected_packet(header, unique, cookie, key, nonce):
    from cryptography.hazmat.primitives.ciphers.aead import AESSIV
    if len(header) != 48 or len(unique) != 32 or len(key) != 32 or len(nonce) != 16:
        raise ValueError('NTS_INPUT_LENGTH')
    prefix = header+extension(0x104, unique)+extension(0x204, cookie)+extension(0x304, b'\0'*len(cookie))
    ciphertext = AESSIV(key).encrypt(b'', [prefix, nonce])
    return prefix+extension(0x404, struct.pack('!HH',len(nonce),len(ciphertext))+nonce+ciphertext)


def verify_packet(raw, unique, key, request_tx, t1, t4, monotonic_elapsed):
    from cryptography.hazmat.primitives.ciphers.aead import AESSIV
    if not 48 <= len(raw) <= 4096 or len(key) != 32 or len(unique) != 32:
        raise ValueError('NTS_PACKET_SIZE')
    pos, uid, authenticated = 48, None, False
    while pos < len(raw):
        start = pos
        if pos+4 > len(raw):
            raise ValueError('NTS_EXTENSION_TRUNCATED')
        kind, length = struct.unpack('!HH',raw[pos:pos+4])
        if length < 4 or length % 4 or pos+length > len(raw):
            raise ValueError('NTS_EXTENSION_LENGTH')
        body = raw[pos+4:pos+length]
        pos += length
        if authenticated:
            raise ValueError('NTS_UNAUTHENTICATED_TRAILER')
        if kind == 0x104:
            if uid is not None or body != unique:
                raise ValueError('NTS_UNIQUE_ID_MISMATCH')
            uid = body
        if kind == 0x404:
            if len(body) < 4:
                raise ValueError('NTS_AUTH_TRUNCATED')
            n, c = struct.unpack('!HH',body[:4])
            padded_nonce = (n+3)//4*4
            if n != 16 or c < 16 or 4+padded_nonce+(c+3)//4*4 != len(body):
                raise ValueError('NTS_AUTH_LENGTH')
            nonce, encrypted = body[4:4+n], body[4+padded_nonce:4+padded_nonce+c]
            AESSIV(key).decrypt(encrypted, [raw[:start],nonce])
            authenticated = True
    if not authenticated or uid != unique:
        raise ValueError('NTS_AUTH_OR_UID_MISSING')
    result = parse_ntp(raw[:48],request_tx,t1,t4,monotonic_elapsed)
    result.update(authentication='TLS13_NTSKE_AND_AES_SIV_CMAC_256',
                  status='CLOCK_AUTHENTICATED_CONDITIONAL_BOUND_ONLY',
                  absolute_UTC_certified=False, publication_proved=False)
    return result
