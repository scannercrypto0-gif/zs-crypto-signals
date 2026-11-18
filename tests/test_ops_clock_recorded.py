from unittest import TestCase

from zs_smart_gate.ops_clock_recorded import PROTOCOL, admit_brackets
from zs_smart_gate.stage05_contracts import canonical

SOURCE = "a"*64
MARKERS = {"availability": 3, "decision": 9}


def samples():
    return [dict(protocol=PROTOCOL, session="one", source_sha256=SOURCE,
                 request_id=f"{i+1:064x}", transcript_sha256=f"{i+100:064x}",
                 send_ns=send, receive_ns=send+1, radius_us=1000,
                 utc_at_receive=f"2026-11-17T08:00:0{seconds}.100000Z")
            for i, (send, seconds) in enumerate(((1,0), (4,1), (7,2), (10,3)))]


class ClockRecordedTests(TestCase):
    def run_adapter(self, rows, **extra):
        pins = {row["transcript_sha256"]:canonical(row) for row in samples()}
        args = dict(source_pin=SOURCE, session="one", markers=MARKERS,
                    host_synchronized=True, max_width_us=1500000,
                    authenticate=lambda raw, pin: pins.get(pin)==raw)
        return admit_brackets(rows, **(args | extra))

    def test_authenticated_brackets_bound_two_distinct_events(self):
        result = self.run_adapter(samples())
        self.assertEqual(result["status"], "RECORDED_BRACKET_VALIDATED")
        self.assertEqual(result["utc_intervals"]["availability"],
                         ["2026-11-17T08:00:00.099000Z","2026-11-17T08:00:01.101000Z"])

    def test_altered_replayed_or_reordered_samples_are_blocked(self):
        for index, changed in ((0, {"radius_us":10}), (1, {"request_id":samples()[0]["request_id"]}),
                               (1, {"send_ns":1}), (0, {"session":"old"})):
            rows = samples()
            rows[index].update(changed)
            self.assertIsNone(self.run_adapter(rows))

    def test_unsynchronized_host_and_bad_markers_fail_closed(self):
        self.assertIsNone(self.run_adapter(samples(), host_synchronized=False))
        self.assertIsNone(self.run_adapter(samples(), markers={"availability":4,"decision":9}))
        self.assertIsNone(self.run_adapter(samples(), max_width_us=1002000))
