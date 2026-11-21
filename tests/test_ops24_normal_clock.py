"""Normal-token clock equivalence controls. Fixture provenance is synthetic."""
import copy
import unittest
from unittest.mock import patch

from zs_smart_gate.ops24_budget import Hold
from zs_smart_gate.ops24_normal_clock import (
    NormalClock,PROFILE,assess_normal,verify_provenance,system_directory,
)
from test_p0_clock_73 import valid_receipts


def profile():
    system=str(system_directory())
    base="SYSTEM\\CurrentControlSet\\Services\\W32Time"
    auto="SYSTEM\\CurrentControlSet\\Services\\autotimesvc"
    def row(path,values):
        return dict(path=path,owner="S-1-5-18",values=values,rules=[
            dict(sid="S-1-5-18",rights=983103,type="Allow",propagation=0),
            dict(sid="S-1-5-32-545",rights=131097,type="Allow",propagation=0)])
    result=dict(system32=system,service_sid_text=(
        "S-1-5-80-1-2-3-4-5\nS-1-5-80-6-7-8-9-10"),
        signatures=[dict(file=name,status="Valid",signer="CN=Microsoft Windows, O=Microsoft Corporation",
            sha256="a"*64,owner="S-1-5-18",rules=[]) for name in
            ("sc.exe","w32tm.exe","w32time.dll","svchost.exe","autotimesvc.dll")],
        registry=[
            row(base,dict(ImagePath=system+"\\svchost.exe -k LocalService")),
            row(base+"\\Parameters",dict(Type="NTP",NtpServer="time.cloudflare.com,0x8",
                                         ServiceDll=system+"\\w32time.dll")),
            row(base+"\\TimeProviders\\NtpClient",dict(Enabled=1)),
            row(auto,dict(ImagePath=system+"\\svchost.exe -k autoTimeSvc")),
            row(auto+"\\Parameters",dict(ServiceDll=system+"\\autotimesvc.dll")),
        ])
    return result


def observations():
    result=valid_receipts()
    for name in ("source","configuration"):
        result[name]["exit"]=2147942405
        result[name]["stdout"]="Access is denied"
    return result


class NormalClockTests(unittest.TestCase):
    def test_verified_equivalent_retains_original_denials_and_numerical_policy(self):
        result=assess_normal(observations(),profile(),10)
        self.assertEqual(result["status"],"OPERATIONAL_TIME_ACCEPTED")
        self.assertEqual(result["rpc_exit_codes"]["source"],2147942405)
        self.assertEqual(result["rpc_exit_codes"]["configuration"],2147942405)
        self.assertEqual(result["original_rpc_blockers"],
                         ["SOURCE_COMMAND_FAILED","CONFIGURATION_COMMAND_FAILED"])
        self.assertEqual(result["observation_profile"],PROFILE)
        self.assertEqual(result["independent_time"],"INDEPENDENT_CRYPTOGRAPHIC_TIME_NOT_PROVEN")

    def test_mutable_registry_or_untrusted_owner_never_substitutes_rpc(self):
        for mode in ("WRITABLE","OWNER","SOURCE","DISABLED"):
            value=profile()
            if mode=="WRITABLE":
                value["registry"][1]["rules"].append(
                    dict(sid="S-1-5-32-545",rights=2,type="Allow",propagation=0))
            elif mode=="OWNER":
                value["registry"][1]["owner"]="S-1-5-21-123"
            elif mode=="SOURCE":
                value["registry"][1]["values"]["NtpServer"]="other.example,0x8"
            else:
                value["registry"][2]["values"]["Enabled"]=0
            with self.subTest(mode=mode),self.assertRaises(Hold):
                assess_normal(observations(),value,10)

    def test_binary_signature_acl_path_and_identity_checks(self):
        for mode in ("SIGNATURE","WRITABLE","DLL","DIRECTORY","SERVICE_SID"):
            value=profile()
            if mode=="SIGNATURE":
                value["signatures"][0]["status"]="NotSigned"
            elif mode=="WRITABLE":
                value["signatures"][0]["rules"]=[dict(sid="S-1-5-32-545",rights=2,type="Allow",propagation=0)]
            elif mode=="DLL":
                value["registry"][1]["values"]["ServiceDll"]="D:\\untrusted.dll"
            elif mode=="DIRECTORY":
                value["system32"]="D:\\fake-system32"
            else:
                value["service_sid_text"]=""
            with self.subTest(mode=mode),self.assertRaises(Hold):
                verify_provenance(value)

    def test_stale_future_quorum_step_and_active_source_mismatch_remain_blocked(self):
        for mode in ("STALE","FUTURE","QUORUM","STEP","SOURCE"):
            rows=observations()
            age=10
            if mode=="STALE":
                age=601
            elif mode=="FUTURE":
                age=-1
            elif mode=="QUORUM":
                rows["stripchart"]["stdout"]=""
            elif mode=="STEP":
                rows["status"]["wall_step_disagreement_s"]=.1
            else:
                rows["status"]["stdout"]=rows["status"]["stdout"].replace(
                    "Source: time.cloudflare.com","Source: Local CMOS Clock")
            with self.subTest(mode=mode):
                self.assertEqual(assess_normal(rows,profile(),age)["status"],"BLOCKED")

    def test_refresh_uses_real_commands_by_default_but_fixture_cache_is_bounded(self):
        rows=observations()
        calls=[]
        def observed(argv):
            calls.append(argv)
            if argv[0].endswith("sc.exe"):
                return rows["service"]
            for name in ("status","source","configuration"):
                if "/"+name in argv:
                    return rows[name]
            return rows["stripchart"]
        clock=NormalClock(observe=observed,provenance=profile,age=lambda _:10)
        with patch("zs_smart_gate.ops24_normal_clock.is_admin",return_value=False):
            self.assertTrue(clock.accepted())
            self.assertTrue(clock.accepted())
        self.assertEqual(len(calls),5)
        self.assertTrue(all(str(system_directory()) in row[0] for row in calls))

    def test_gpo_override_cannot_be_ignored(self):
        value=profile()
        value["registry"].append(dict(path="SOFTWARE\\Policies\\Microsoft\\W32Time\\Parameters",
            owner="S-1-5-18",rules=[],values=dict(Type="NT5DS",NtpServer=None,Enabled=None)))
        with self.assertRaisesRegex(Hold,"GPO_CLOCK_SOURCE_OVERRIDE"):
            assess_normal(observations(),value,10)


    def test_step_between_cached_samples_is_not_hidden_by_refresh(self):
        clock=NormalClock(provenance=lambda:self.fail("step must stop before requery"))
        clock.latest={"assessment":{"sync_age_s":10}}
        clock.at_mono=10
        clock.at_wall=100
        with patch("zs_smart_gate.ops24_normal_clock.is_admin",return_value=False), \
             patch("zs_smart_gate.ops24_normal_clock.time.monotonic",return_value=11), \
             patch("zs_smart_gate.ops24_normal_clock.time.time",return_value=102):
            with self.assertRaisesRegex(Hold,"NORMAL_CLOCK_TIME_STEP"):
                clock.refresh()
