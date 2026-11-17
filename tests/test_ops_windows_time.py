import unittest

from zs_smart_gate.ops_windows_time import COMMANDS, assess


def observations():
    data = {name:{"exit":0,"stdout":"","wall_step_disagreement_s":0} for name in COMMANDS}
    data["service"]["stdout"] = "STATE : 4 RUNNING"
    data["status"]["stdout"] = ("Leap Indicator: 0(no warning)\nStratum: 4\n"
                                "Source: time.cloudflare.com,0x8\n"
                                "Root Delay: 0.090s\nRoot Dispersion: 0.020s")
    data["source"]["stdout"] = "time.cloudflare.com,0x8"
    data["stripchart"]["stdout"] = "\n".join(
        f"12:00:0{i}, d:+00.020s o:+00.001s" for i in range(4))
    return data


class WindowsTimeTests(unittest.TestCase):
    def test_valid_diagnostics_do_not_approve_unreviewed_tolerance(self):
        result = assess(observations(),sync_age_s=30)
        self.assertEqual(result["blockers"],["OPERATIONAL_TOLERANCES_NOT_APPROVED"])
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(len(result["samples"]),4)
        self.assertAlmostEqual(result["conditional_uncertainty_s"],.075)

    def test_source_failure_stale_and_step_are_explicit(self):
        rows = observations()
        rows["source"]["exit"] = 5
        rows["source"]["stdout"] = "Access is denied"
        rows["configuration"]["exit"] = None
        rows["stripchart"]["wall_step_disagreement_s"] = .3
        result = assess(rows,sync_age_s=800)
        for reason in ("SOURCE_COMMAND_FAILED","CONFIGURATION_COMMAND_FAILED",
                       "STRIPCHART_TIME_STEP","SYNC_FRESHNESS_UNVERIFIED_OR_STALE"):
            self.assertIn(reason,result["blockers"])

    def test_unknown_source_quorum_and_unsafe_offset(self):
        rows = observations()
        rows["source"]["stdout"] = "Local CMOS Clock"
        rows["stripchart"]["stdout"] = "12:00:00, d:+00.200s o:+01.000s"
        result = assess(rows,sync_age_s=None)
        for reason in ("SOURCE_NOT_ALLOWLISTED","OFFSET_QUORUM_OR_DUPLICATE","OFFSET_LIMIT"):
            self.assertIn(reason,result["blockers"])
