"""Offline adapter for externally authenticated clock transcript samples."""
from datetime import timedelta

from .stage05_contracts import ContractError, SHA, canonical, digest, parse_utc

PROTOCOL = "NTS_RFC8915_RECORDED_V1"


def admit_brackets(samples, *, source_pin, session, markers, host_synchronized,
                   max_width_us, authenticate):
    """The authenticator verifies original transcript bytes against independent trust pins."""
    try:
        if (host_synchronized is not True or len(samples) != 4
                or not SHA.fullmatch(source_pin) or not isinstance(session, str) or not session
                or type(max_width_us) is not int or not 0 < max_width_us <= 1500000):
            return None
        observed, seen = [], set()
        for sample in samples:
            if (sample["protocol"] != PROTOCOL or sample["session"] != session
                    or sample["source_sha256"] != source_pin):
                return None
            request_id, pin = sample["request_id"], sample["transcript_sha256"]
            if not SHA.fullmatch(request_id) or not SHA.fullmatch(pin) or request_id in seen:
                return None
            seen.add(request_id)
            send, receive, radius = (sample[k] for k in ("send_ns", "receive_ns", "radius_us"))
            if (any(type(v) is not int for v in (send, receive, radius))
                    or not 0 <= send < receive or not 0 <= radius < max_width_us
                    or (observed and send <= observed[-1][1])):
                return None
            center = parse_utc(sample["utc_at_receive"])
            # Authentication must bind the supplied sample fields and the original transcript.
            if authenticate(canonical(sample), pin) is not True:
                return None
            error = timedelta(microseconds=radius)
            low_at_receive = center-error
            # Convert a receive-time upper bound to a send-time upper bound only
            # by monotonic ordering, without estimating host UTC drift.
            high_at_receive = center+error
            observed.append((send, receive, low_at_receive, high_at_receive))
        result = {}
        for index, name in enumerate(("availability", "decision")):
            before, after = observed[index*2:index*2+2]
            marker = markers[name]
            if type(marker) is not int or not before[1] < marker < after[0]:
                return None
            low, high = before[2], after[3]
            if not timedelta(0) <= high-low < timedelta(microseconds=max_width_us):
                return None
            result[name] = (low, high)
        if result["availability"][1] > result["decision"][0]:
            return None
        return {"status":"RECORDED_BRACKET_VALIDATED", "source_sha256":source_pin,
                "session":session, "samples_sha256":digest(canonical(samples)),
                "utc_intervals":{key:[v.isoformat().replace("+00:00","Z") for v in values]
                                 for key,values in result.items()}}
    except (ContractError, KeyError, TypeError, AttributeError, OverflowError, ValueError):
        return None
