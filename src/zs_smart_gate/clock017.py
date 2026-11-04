"""Offline Roughtime draft08/11 verification; never admits UTC pins itself.

Wire profile follows Cloudflare's Apache-2.0 protocol implementation.
This is not an RFC10049 client. Signed integer-second radii cannot certify <1s.
"""
import hashlib
import math
import struct

VERSIONS = (0x8000000b, 0x80000008)


def encode(fields):
    tags = sorted(fields, key=lambda k: int.from_bytes(k, 'little'))
    if not tags or any(len(k) != 4 or len(fields[k]) % 4 for k in tags):
        raise ValueError('FIELD_ALIGNMENT')
    offsets, size = [], 0
    for k in tags:
        offsets.append(size)
        size += len(fields[k])
    return (struct.pack('<I', len(tags)) +
            b''.join(struct.pack('<I', x) for x in offsets[1:]) +
            b''.join(tags) + b''.join(fields[k] for k in tags))


def decode(raw):
    if not 4 <= len(raw) <= 4096 or len(raw) % 4:
        raise ValueError('MESSAGE_SIZE')
    n = struct.unpack('<I', raw[:4])[0]
    if not 1 <= n <= 32 or 8*n > len(raw):
        raise ValueError('TAG_COUNT')
    ends = [0] + list(struct.unpack('<'+'I'*(n-1), raw[4:4*n])) + [len(raw)-8*n]
    tags = [raw[4*n+4*i:4*n+4*i+4] for i in range(n)]
    ids = [int.from_bytes(x, 'little') for x in tags]
    if ids != sorted(set(ids)) or any(x % 4 for x in ends) or ends != sorted(ends):
        raise ValueError('TAG_OR_OFFSET_ORDER')
    return {k: raw[8*n+ends[i]:8*n+ends[i+1]] for i, k in enumerate(tags)}


def framed(body):
    return b'ROUGHTIM' + struct.pack('<I', len(body)) + body


def request(nonce, public_key):
    if len(nonce) != 32 or len(public_key) != 32:
        raise ValueError('KEY_NONCE_SIZE')
    fields = {b'NONC': nonce, b'VER\0': struct.pack('<II', *VERSIONS),
              b'SRV\0': hashlib.sha512(b'\xff'+public_key).digest()[:32], b'ZZZZ': b''}
    fields[b'ZZZZ'] = b'\0'*(1024-12-len(encode(fields)))
    return framed(encode(fields))


def verify(raw, nonce, public_key):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if len(nonce) != 32 or len(public_key) != 32:
        raise ValueError('KEY_NONCE_SIZE')
    if len(raw) < 12 or raw[:8] != b'ROUGHTIM' or len(raw)-12 != struct.unpack('<I', raw[8:12])[0]:
        raise ValueError('FRAME')
    reply = decode(raw[12:])
    def integer(fields, key, width):
        value = fields[key]
        if len(value) != width:
            raise ValueError('INTEGER_WIDTH')
        return int.from_bytes(value, 'little')
    # Cloudflare's deployed draft11 response omits an echoed NONC. Freshness
    # still requires the supplied nonce's authenticated Merkle inclusion below.
    # Explicit echo, when present, must match. This is a deployed profile,
    # not a claim of conformance to every later draft or RFC10049.
    if integer(reply, b'VER\0', 4) not in VERSIONS or reply.get(b'NONC', nonce) != nonce:
        raise ValueError('VERSION_OR_NONCE')
    cert = decode(reply[b'CERT'])
    Ed25519PublicKey.from_public_bytes(public_key).verify(
        cert[b'SIG\0'], b'RoughTime v1 delegation signature--\0'+cert[b'DELE'])
    delegation = decode(cert[b'DELE'])
    Ed25519PublicKey.from_public_bytes(delegation[b'PUBK']).verify(
        reply[b'SIG\0'], b'RoughTime v1 response signature\0'+reply[b'SREP'])
    signed = decode(reply[b'SREP'])
    midpoint = integer(signed, b'MIDP', 8)
    radius = integer(signed, b'RADI', 4)
    low, high = integer(delegation, b'MINT', 8), integer(delegation, b'MAXT', 8)
    if not low <= midpoint <= high:
        raise ValueError('DELEGATION_TIME')
    index, path = integer(reply, b'INDX', 4), reply[b'PATH']
    if len(path) % 32 or len(path) > 1024:
        raise ValueError('MERKLE_PATH')
    node = hashlib.sha512(b'\0'+nonce).digest()[:32]
    for p in range(0, len(path), 32):
        sibling = path[p:p+32]
        node = hashlib.sha512(b'\1'+(sibling+node if index & 1 else node+sibling)).digest()[:32]
        index >>= 1
    if index or node != signed[b'ROOT']:
        raise ValueError('MERKLE_ROOT')
    return dict(signature_verified=True, midpoint=midpoint, radius_seconds=radius,
                version=integer(reply, b'VER\0', 4), absolute_utc_admitted=False,
                nonce_binding='SIGNED_MERKLE_INCLUSION', nonce_echo_present=b'NONC' in reply)


def local_interval(sample, *, sent_wall, received_wall, elapsed):
    """No symmetric-route assumption: server signing occurs within RTT bracket.

    Source radius is a signed authority assertion, not an independently admitted
    metrology certificate. No inferred oscillator specification or default ppm.
    """
    if any(type(x) not in (int, float) or not math.isfinite(x)
           for x in (sent_wall, received_wall, elapsed)) or elapsed < 0:
        raise ValueError('CLOCK_FIELDS')
    residual = abs(received_wall-sent_wall-elapsed)
    lo = sample['midpoint']-sample['radius_seconds']
    hi = sample['midpoint']+sample['radius_seconds']+elapsed
    bound = max(abs(received_wall-lo), abs(received_wall-hi))+residual
    return dict(utc_received_interval=[lo, hi], local_error_bound_seconds=bound,
                wall_monotonic_residual_seconds=residual, max_drift_ppm=None,
                status='HOLD', reason='INDEPENDENT_SOURCE_AND_DRIFT_ADMISSION_REQUIRED',
                below_one_second=bound < 1, forward_armed=False)
