# OPS77 actual batch-logon failure and scoped repair

Original 8981f5b Windows task: registered=true, probe_observed=false, cleanup=true.
Actual Windows Operational events 101/104: result 2147943785 / 0x80070569, ERROR_LOGON_TYPE_NOT_GRANTED. Redacted extraction retains event SHA-256, code, UTC and event ID; account/host/SID fields are omitted. Original task report retained unchanged.

Source fix PR76 head 8c8c84b54465b9a7478bac77b090ad6faeabaa95, tree de03fa242464386fdcafb15af7ef6d5c4c962d99. Add only SeBatchLogonRight to the marked nonadmin project account via LSA additive APIs. Do not remove deny policies, modify UAC or replace global user-right assignments. Direct explicit deny aborts; group/GPO deny can still block and must be reported. Grant is persistent OS configuration under standing owner authority, not an administrator worker token.

Windows affected tests 7/7 PASS; independent GitHub source clone reproduces 7/7, no skips/errors/failures or Python network attempts. Native LSA helper compiles and refuses nonadmin mutation. These offline tests do NOT prove the actual LSA grant or actual scheduled worker execution. Administrator execution of corrected pinned probe remains PENDING. Real logoff/reboot/24h and independent scientific time remain NOT_PROVED. Market/Telegram/SQL calls=0 in this repair. PR76 Draft; no merges.

Microsoft reference: https://learn.microsoft.com/windows/security/threat-protection/security-policy-settings/log-on-as-a-batch-job
