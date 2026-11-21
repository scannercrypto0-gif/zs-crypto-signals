# OPS77 cross-user S4U correction

Source head `8981f5bef96bb9f1be885ba25f52982b169e9ca9`, tree `1802d00502f6893edaf256b904002b4e082fb2b2`.
Windows targeted controller suite: 6/6 PASS, zero failures/errors/skips, zero Python network attempts.
Independent GitHub source clone reproduction: 6/6 PASS on the same head.
Original f98ce7a baseline suites: 70/70, preserved separately; not claimed rerun on 8981f5b.
Original administrator-run f98ce7a task registration failed 0x80070005 before registering any task. No live calls.
Root cause: cross-user S4U registration requires that user's credential even for administrators. Reference: https://learn.microsoft.com/en-us/windows/win32/taskschd/security-contexts-for-running-tasks
Correction supplies a transient PSCredential through the API, never command-line/file/report. Only the unused project standard account may be rotated; existing tasks or a user profile abort rotation. No production credentials are involved.
The prior ACL repair receipt is preserved; contents were unchanged. No SACL manipulation or security policy weakening.

Actual corrected scheduled probe: PENDING administrator execution. No claimed reboot, logoff, 24-hour acceptance or scientific timing GO. Production bootstrap cross-user credential provisioning remains pending, independently of this diagnostic repair. No merge; PR76 remains Draft. No Binance/Telegram/SQL calls in this repair.
