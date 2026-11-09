-- ZS Stage05 SQL Server normalized contract v1 (DDL only).
-- NO database connection/creation/migration is run by Stage05.
-- SQL Server UTC DATETIME2(6); raw precision is retained separately.
-- No Telegram bot tokens or private owner configuration in rows.
CREATE TABLE dbo.assets (
  asset_id nvarchar(32) NOT NULL PRIMARY KEY,
  venue nvarchar(16) NOT NULL,
  quote_asset nvarchar(16) NOT NULL
);
CREATE TABLE dbo.source_manifests (
  source_manifest_id nvarchar(128) NOT NULL PRIMARY KEY,
  manifest_sha256 char(64) NOT NULL,
  source_scope nvarchar(40) NOT NULL,
  record_version nvarchar(64) NOT NULL,
  CONSTRAINT UQ_source_manifest_sha UNIQUE (manifest_sha256)
);
CREATE TABLE dbo.scan_cycles (
  scan_cycle_id nvarchar(128) NOT NULL PRIMARY KEY,
  source_manifest_id nvarchar(128) NULL REFERENCES dbo.source_manifests(source_manifest_id),
  observed_at_utc datetime2(6) NOT NULL,
  observed_at_raw_utc nvarchar(40) NOT NULL
);
CREATE TABLE dbo.candidates (
  candidate_id nvarchar(128) NOT NULL PRIMARY KEY,
  detection_event_key nvarchar(128) NOT NULL,
  asset_id nvarchar(32) NOT NULL REFERENCES dbo.assets(asset_id),
  scan_cycle_id nvarchar(128) NULL REFERENCES dbo.scan_cycles(scan_cycle_id),
  source_manifest_id nvarchar(128) NULL REFERENCES dbo.source_manifests(source_manifest_id),
  qualification_status nvarchar(20) NOT NULL CHECK (qualification_status IN (N'QUALIFIED', N'REJECTED')),
  decision_at_utc datetime2(6) NOT NULL,
  decision_at_raw_utc nvarchar(40) NOT NULL,
  immutable_snapshot_sha256 char(64) NOT NULL,
  event_schema nvarchar(64) NOT NULL,
  CONSTRAINT UQ_candidate_detection_event UNIQUE (detection_event_key)
);
CREATE TABLE dbo.signals (
  signal_id nvarchar(128) NOT NULL PRIMARY KEY,
  candidate_id nvarchar(128) NOT NULL UNIQUE REFERENCES dbo.candidates(candidate_id),
  qualification_evidence_sha256 char(64) NOT NULL,
  CONSTRAINT UQ_signal_candidate_pair UNIQUE(signal_id, candidate_id)
);
CREATE TABLE dbo.candidate_decisions (
  candidate_id nvarchar(128) NOT NULL REFERENCES dbo.candidates(candidate_id),
  gate_id nvarchar(64) NOT NULL,
  gate_state nvarchar(16) NOT NULL CHECK (gate_state IN (N'PASS',N'FAIL',N'UNKNOWN')),
  reason_codes_json nvarchar(max) NOT NULL,
  CONSTRAINT PK_candidate_decisions PRIMARY KEY (candidate_id, gate_id)
);
CREATE TABLE dbo.indicator_values (
  candidate_id nvarchar(128) NOT NULL REFERENCES dbo.candidates(candidate_id),
  indicator_id nvarchar(64) NOT NULL,
  availability nvarchar(24) NOT NULL CHECK (availability IN (N'PRESENT',N'MISSING',N'INVALID',N'NOT_IMPLEMENTED')),
  evaluation nvarchar(12) NOT NULL CHECK (evaluation IN (N'PASS',N'FAIL',N'UNKNOWN')),
  raw_value nvarchar(255) NULL,
  numeric_value decimal(38,16) NULL,
  unit nvarchar(32) NULL,
  timeframe nvarchar(16) NULL,
  source_name nvarchar(128) NULL,
  as_of_utc datetime2(6) NULL,
  version nvarchar(64) NULL,
  threshold_json nvarchar(max) NULL,
  reason_codes_json nvarchar(max) NOT NULL,
  CONSTRAINT PK_indicator_values PRIMARY KEY (candidate_id, indicator_id)
);
CREATE TABLE dbo.signal_features (
  signal_id nvarchar(128) NOT NULL REFERENCES dbo.signals(signal_id),
  indicator_id nvarchar(64) NOT NULL,
  feature_version nvarchar(64) NOT NULL,
  feature_json nvarchar(max) NOT NULL,
  CONSTRAINT PK_signal_features PRIMARY KEY (signal_id, indicator_id, feature_version)
);
CREATE TABLE dbo.telegram_deliveries (
  delivery_id char(64) NOT NULL PRIMARY KEY,
  candidate_id nvarchar(128) NOT NULL REFERENCES dbo.candidates(candidate_id),
  signal_id nvarchar(128) NULL REFERENCES dbo.signals(signal_id),
  bot_id nvarchar(32) NOT NULL CHECK (bot_id IN (N'SIGNALS',N'ANALYTICS',N'INTERACTIVE')),
  destination_label nvarchar(24) NOT NULL,
  chat_id nvarchar(64) NULL,
  telegram_message_id bigint NULL,
  status nvarchar(32) NOT NULL,
  delivery_attempt_id char(64) NULL,
  dispatch_attempt_at_utc datetime2(6) NULL,
  telegram_accepted_at_utc datetime2(6) NULL,
  telegram_message_date_at_utc datetime2(0) NULL,
  receipt_sha256 char(64) NULL,
  CONSTRAINT UQ_telegram_delivery_identity UNIQUE (candidate_id, bot_id, destination_label),
  CONSTRAINT FK_delivery_signal_same_candidate
    FOREIGN KEY (signal_id, candidate_id) REFERENCES dbo.signals(signal_id, candidate_id)
);
CREATE UNIQUE INDEX UQ_telegram_actual_message
  ON dbo.telegram_deliveries(bot_id, chat_id, telegram_message_id)
  WHERE chat_id IS NOT NULL AND telegram_message_id IS NOT NULL;
CREATE TABLE dbo.delivery_attempts (
  delivery_attempt_id char(64) NOT NULL PRIMARY KEY,
  delivery_id char(64) NOT NULL REFERENCES dbo.telegram_deliveries(delivery_id),
  attempt_no int NOT NULL CHECK (attempt_no BETWEEN 1 AND 3),
  started_at_utc datetime2(6) NOT NULL,
  finished_at_utc datetime2(6) NULL,
  outcome nvarchar(32) NULL,
  retry_after_at_utc datetime2(6) NULL,
  CONSTRAINT UQ_attempt_seq UNIQUE(delivery_id,attempt_no)
);
CREATE TABLE dbo.trade_plans (
  trade_plan_id nvarchar(128) NOT NULL PRIMARY KEY,
  signal_id nvarchar(128) NOT NULL REFERENCES dbo.signals(signal_id),
  plan_version nvarchar(64) NOT NULL,
  approved bit NOT NULL,
  plan_json nvarchar(max) NOT NULL,
  CONSTRAINT UQ_trade_plan_version UNIQUE(signal_id,plan_version)
);
CREATE TABLE dbo.signal_outcomes (
  outcome_id nvarchar(128) NOT NULL PRIMARY KEY,
  signal_id nvarchar(128) NOT NULL REFERENCES dbo.signals(signal_id),
  outcome_version nvarchar(64) NOT NULL,
  measured_at_utc datetime2(6) NOT NULL,
  outcome_json nvarchar(max) NOT NULL,
  CONSTRAINT UQ_outcome_version UNIQUE(signal_id,outcome_version)
);
CREATE TABLE dbo.signal_updates (
  update_id nvarchar(128) NOT NULL PRIMARY KEY,
  signal_id nvarchar(128) NOT NULL REFERENCES dbo.signals(signal_id),
  update_version nvarchar(64) NOT NULL,
  recorded_at_utc datetime2(6) NOT NULL,
  update_json nvarchar(max) NOT NULL,
  CONSTRAINT UQ_update_version UNIQUE(signal_id,update_version)
);
CREATE TABLE dbo.analysis_requests (
  analysis_request_id char(64) NOT NULL PRIMARY KEY,
  asset_id nvarchar(32) NOT NULL REFERENCES dbo.assets(asset_id),
  received_at_utc datetime2(6) NOT NULL,
  result_status nvarchar(32) NOT NULL,
  result_json nvarchar(max) NULL
);
-- Import policy: verify canonical SHA before insert; reject differing bytes
-- for an existing PK/UNIQUE key; append outcomes/updates without rewriting the
-- original decision snapshot. Real Telegram Desktop export/SQL roundtrip is
-- the later Stage06B acceptance, NOT yet certified by this DDL.
