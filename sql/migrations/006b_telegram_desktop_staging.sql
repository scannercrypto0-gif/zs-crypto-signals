-- Stage06B owner-authorized offline SQL Server staging schema, v1
-- Run only on an approved LOCAL SQL Server DB using explicit credentials.
-- No production trading/order tables are modified; no network connects here.
-- Safe to reapply: table creation only if missing; no destructive DROP.
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID(N'dbo.zs06b_candidates', N'U') IS NULL
CREATE TABLE dbo.zs06b_candidates (
    candidate_id varchar(128) NOT NULL CONSTRAINT pk_zs06b_candidates PRIMARY KEY,
    event_sha256 char(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
    source_manifest_sha256 char(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
    qualification_status varchar(16) NOT NULL,
    CONSTRAINT ck_zs06b_qualification CHECK (qualification_status IN ('QUALIFIED','REJECTED'))
);

IF OBJECT_ID(N'dbo.zs06b_signals', N'U') IS NULL
CREATE TABLE dbo.zs06b_signals (
    signal_id varchar(128) NOT NULL CONSTRAINT pk_zs06b_signals PRIMARY KEY,
    candidate_id varchar(128) NOT NULL,
    CONSTRAINT fk_zs06b_signal_candidate FOREIGN KEY (candidate_id)
        REFERENCES dbo.zs06b_candidates(candidate_id)
);

IF OBJECT_ID(N'dbo.zs06b_candidate_decisions', N'U') IS NULL
CREATE TABLE dbo.zs06b_candidate_decisions (
    candidate_id varchar(128) NOT NULL,
    gate_id varchar(128) NOT NULL,
    payload_sha256 char(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_zs06b_decisions PRIMARY KEY (candidate_id, gate_id),
    CONSTRAINT fk_zs06b_decisions_candidate FOREIGN KEY (candidate_id)
        REFERENCES dbo.zs06b_candidates(candidate_id),
    CONSTRAINT ck_zs06b_decision_json CHECK (ISJSON(payload_json) = 1)
);

IF OBJECT_ID(N'dbo.zs06b_indicator_values', N'U') IS NULL
CREATE TABLE dbo.zs06b_indicator_values (
    candidate_id varchar(128) NOT NULL,
    indicator_id varchar(128) NOT NULL,
    payload_sha256 char(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
    payload_json nvarchar(max) NOT NULL,
    CONSTRAINT pk_zs06b_indicators PRIMARY KEY (candidate_id, indicator_id),
    CONSTRAINT fk_zs06b_indicators_candidate FOREIGN KEY (candidate_id)
        REFERENCES dbo.zs06b_candidates(candidate_id),
    CONSTRAINT ck_zs06b_indicator_json CHECK (ISJSON(payload_json) = 1)
);

IF OBJECT_ID(N'dbo.zs06b_messages', N'U') IS NULL
CREATE TABLE dbo.zs06b_messages (
    bot_id bigint NOT NULL,
    chat_id bigint NOT NULL,
    message_id bigint NOT NULL,
    role varchar(32) NOT NULL,
    telegram_date_utc datetime2(0) NOT NULL,
    message_type varchar(12) NOT NULL,
    text_sha256 char(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
    attachment_sha256 char(64) COLLATE Latin1_General_100_BIN2 NULL,
    archive_sha256 char(64) COLLATE Latin1_General_100_BIN2 NULL,
    candidate_id varchar(128) NULL,
    signal_id varchar(128) NULL,
    CONSTRAINT pk_zs06b_messages PRIMARY KEY (bot_id, chat_id, message_id),
    CONSTRAINT ck_zs06b_roles CHECK (role IN (
        'SIGNALS_A','SIGNALS_B','ANALYTICS_C','INTERACTIVE_A','INTERACTIVE_B')),
    CONSTRAINT fk_zs06b_message_candidate FOREIGN KEY (candidate_id)
        REFERENCES dbo.zs06b_candidates(candidate_id),
    CONSTRAINT fk_zs06b_message_signal FOREIGN KEY (signal_id)
        REFERENCES dbo.zs06b_signals(signal_id)
);

IF OBJECT_ID(N'dbo.zs06b_attachments', N'U') IS NULL
CREATE TABLE dbo.zs06b_attachments (
    bot_id bigint NOT NULL,
    chat_id bigint NOT NULL,
    path_sha256 char(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
    attachment_sha256 char(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
    CONSTRAINT pk_zs06b_attachments PRIMARY KEY (bot_id, chat_id, path_sha256)
);
COMMIT TRANSACTION;
