param([string]$Server = '.\SQLEXPRESS')
$ErrorActionPreference = 'Stop'
$ddlPath = Join-Path $PSScriptRoot '../stage05/sqlserver-contract-v1.sql'
$ddl = [IO.File]::ReadAllText((Resolve-Path $ddlPath)).Replace('dbo.', 'zs_e2e51_check.')
$probe = @"
SET NOCOUNT ON; SET QUOTED_IDENTIFIER ON; SET ANSI_NULLS ON; SET ANSI_PADDING ON; SET ANSI_WARNINGS ON; SET CONCAT_NULL_YIELDS_NULL ON; SET ARITHABORT ON; SET NUMERIC_ROUNDABORT OFF;
SET XACT_ABORT OFF;
BEGIN TRANSACTION;
EXEC(N'CREATE SCHEMA zs_e2e51_check');
$ddl
INSERT zs_e2e51_check.assets VALUES ('BTCUSDT','BINANCE_SPOT','USDT');
INSERT zs_e2e51_check.source_manifests VALUES ('fixture',REPLICATE('a',64),'SYNTHETIC_TEST_ONLY','v1');
INSERT zs_e2e51_check.scan_cycles VALUES ('cycle','fixture','2026-11-09T00:00:00.123456','2026-11-09T00:00:00.123456Z');
INSERT zs_e2e51_check.candidates VALUES ('cand','event','BTCUSDT','cycle','fixture','REJECTED','2026-11-09T00:00:00.123456','2026-11-09T00:00:00.123456Z',REPLICATE('b',64),'zs.stage05.event.v1');
INSERT zs_e2e51_check.telegram_deliveries(delivery_id,candidate_id,bot_id,destination_label,status)
VALUES (REPLICATE('a',64),'cand','ANALYTICS','C','UNKNOWN_DELIVERY');
INSERT zs_e2e51_check.delivery_attempts(delivery_attempt_id,delivery_id,attempt_no,started_at_utc,outcome)
VALUES (REPLICATE('c',64),REPLICATE('a',64),1,'2026-11-09T00:00:00.123456','UNKNOWN_DELIVERY');
BEGIN TRY
  INSERT zs_e2e51_check.telegram_deliveries(delivery_id,candidate_id,bot_id,destination_label,status)
  VALUES (REPLICATE('d',64),'cand','ANALYTICS','C','API_ACCEPTED');
  THROW 50001, 'DUPLICATE_ROUTE_NOT_REJECTED', 1;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() NOT IN (2601,2627) THROW;
END CATCH;
BEGIN TRY
  INSERT zs_e2e51_check.delivery_attempts(delivery_attempt_id,delivery_id,attempt_no,started_at_utc)
  VALUES (REPLICATE('e',64),REPLICATE('f',64),1,'2026-11-09T00:00:00');
  THROW 50002, 'ORPHAN_ATTEMPT_NOT_REJECTED', 1;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 547 THROW;
END CATCH;
IF NOT EXISTS (
 SELECT 1 FROM zs_e2e51_check.candidates c
 JOIN zs_e2e51_check.telegram_deliveries d ON c.candidate_id=d.candidate_id
 JOIN zs_e2e51_check.delivery_attempts a ON a.delivery_id=d.delivery_id
 WHERE d.signal_id IS NULL AND c.qualification_status='REJECTED' AND DATEPART(microsecond,c.decision_at_utc)=123456 AND a.outcome='UNKNOWN_DELIVERY'
) THROW 50003, 'READBACK_MISSING', 1;
ROLLBACK TRANSACTION;
IF SCHEMA_ID(N'zs_e2e51_check') IS NOT NULL THROW 50004, 'ROLLBACK_FAILED', 1;
SELECT 'SQLSERVER_DDL_KEYS_REJECTED_CANDIDATE_UNKNOWN_DELIVERY_ROLLBACK_PASS', SERVERPROPERTY('ProductVersion');
"@
$probe | sqlcmd -S $Server -E -C -b -l 5 -t 10 -d tempdb -h -1 -W
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
