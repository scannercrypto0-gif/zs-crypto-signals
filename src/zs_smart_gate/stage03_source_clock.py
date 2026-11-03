"""013 public-source/clock probes: parsing only, never certify publication or UTC."""
from decimal import Decimal
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
    if leap == 3 or version not in (3, 4) or mode != 4 or not 1 <= raw[1] <= 15:
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


def validate_public_payload(endpoint, payload, symbol=None):
    if endpoint == 'time':
        if not isinstance(payload, dict) or type(payload.get('serverTime')) is not int or payload['serverTime'] <= 0:
            raise ValueError('SERVER_TIME_SCHEMA')
        return dict(status='EXCHANGE_CLOCK_ONLY', independent_publication=False)
    if endpoint == 'bookTicker':
        if payload.get('symbol') != symbol:
            raise ValueError('BOOK_ASSET')
        bid, ask = Decimal(payload['bidPrice']), Decimal(payload['askPrice'])
        if not bid.is_finite() or not ask.is_finite() or not 0 < bid <= ask:
            raise ValueError('BOOK_SCHEMA')
        return dict(status='BID_ASK_OBSERVED_NOT_PIT', spread_bps=str(10000*(ask-bid)/((ask+bid)/2)),
                    independent_publication=False)
    if endpoint == '24hr':
        if payload.get('symbol') != symbol:
            raise ValueError('TICKER_ASSET')
        volume = Decimal(payload['quoteVolume'])
        if not volume.is_finite() or volume < 0 or type(payload.get('closeTime')) is not int or type(payload.get('openTime')) is not int or payload['openTime'] > payload['closeTime']:
            raise ValueError('TICKER_SCHEMA')
        return dict(status='ROLLING_VOLUME_OBSERVED_NOT_HISTORICAL_ELIGIBILITY', independent_publication=False)
    if endpoint == 'klines':
        if not isinstance(payload, list) or len(payload) != 3:
            raise ValueError('KLINE_COUNT')
        for r in payload:
            if len(r) != 12 or type(r[0]) is not int or r[6] != r[0]+300000-1:
                raise ValueError('KLINE_BOUNDARY')
            o, h, l, c = map(Decimal, r[1:5])
            if not all(v.is_finite() for v in (o, h, l, c)) or not 0 < l <= min(o, c) <= max(o, c) <= h:
                raise ValueError('KLINE_PRICE')
        return dict(status='BOUNDARIES_ONLY_OPEN_BAR_NOT_ADMITTED', independent_publication=False)
    raise ValueError('ENDPOINT_NOT_ALLOWED')
