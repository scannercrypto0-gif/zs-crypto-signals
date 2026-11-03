# Owner-approved completion of Order015 custody

Owner explicitly selected **48 MiB**, recorded in Issue25 comment6600760450.
This applies to the consolidated 010–014 migration only. Other studies and the
runtime spool retain 10MiB. No production or market collection is authorized.

The original evidence and verification snapshots are unchanged. A raw supplement
adds the exact 51 unique archives / 187 aliases previously capacity-blocked:
26,356,407 original bytes, 35,191,736 serialized journal bytes. The original two
packets plus supplement total **45,649,513 / 50,331,648 bytes**. A final audit
packet may be added only after checking the same aggregate ceiling again.

`aggregate-anchor.json` pins all three Stage04 manifest hashes and the complete
evidence commit. Individual namespaces are append-only snapshots for preserving
old manifests; they are not separate capacity allowances. The composite restore
checks the actual sum and fails over 48MiB or if the packet set/byte count changes.
The only namespace allowed a larger Stage04 payload is the exact raw-supplement
ID; arbitrary names retain the default bound.

The archive contains existing Binance Vision ZIPs, a deliberately corrupted
negative-test ZIP, and two existing Tardis sample CSV.gz files. No new provider
requests or historical acquisitions occurred. Binance attribution/CC BY-NC-SA
4.0 and noncommercial research restrictions apply. Tardis raw remains private
internal Customer User/confidential cloud custody under clauses9.1/9.5/9.6,
not a public dataset, external redistribution or foundation-model training
source. Repository privacy was rechecked before the final commit. Do not make
the evidence branch public or enable commercial use under this migration.

After checking out this PR's pinned code head and the evidence commit in the
aggregate anchor into `github-evidence`, set `PYTHONPATH=src` and run:

```text
python scripts/restore-custody-015-complete.py --snapshot github-evidence --destination restored-complete-from-github
```

The script disables sockets, restores/verifies all three packets, joins the
original byte inventory with the supplement without accepting changed hashes,
and reconstructs the required historical audit trees. It re-audits all 48 frozen
market archives, exact parent/child context, both quote samples, and unchanged
frozen model/result bytes. This is custody/audit replay, not a fresh independent
DEV/OOS scientific experiment. No missing publication proof is manufactured.

Expected custody coverage is 680 allowed original paths / 438 unique objects;
two NTS session packets remain forbidden and two unnecessary certificates are
represented by their sanitized existing report. No secret is needed to accept
the application custody result. PM independent acceptance is still required.
PIT_FAIL_HOLD / FULL_V2_UNAVAILABLE / NO_QUALIFIED_SIGNAL / FORWARD_NOT_ARMED
remain unchanged even if every custody gate passes.
