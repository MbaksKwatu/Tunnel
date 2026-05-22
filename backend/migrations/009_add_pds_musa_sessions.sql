-- Migration 009: Musa async job queue
-- Separate from musa_sessions (venture-oriented); this table is file-URL-centric
-- for the polling-worker integration pattern.

CREATE TABLE IF NOT EXISTS pds_musa_sessions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     VARCHAR(255) UNIQUE NOT NULL,
    deal_id        UUID REFERENCES pds_deals(id) ON DELETE SET NULL,
    status         VARCHAR(50) NOT NULL DEFAULT 'pending'
                       CONSTRAINT check_pds_musa_status
                       CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    file_urls      JSONB NOT NULL,
    webhook_url    VARCHAR(500),
    metadata       JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at     TIMESTAMPTZ,
    completed_at   TIMESTAMPTZ,
    error_message  TEXT,
    retry_count    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pds_musa_sessions_status
    ON pds_musa_sessions(status, created_at);

CREATE INDEX IF NOT EXISTS idx_pds_musa_sessions_session_id
    ON pds_musa_sessions(session_id);

COMMENT ON TABLE pds_musa_sessions IS
    'Async job queue for Musa Ventures file-URL processing (polling-worker pattern)';
COMMENT ON COLUMN pds_musa_sessions.file_urls IS
    'JSONB array of signed file URLs to download and ingest';
COMMENT ON COLUMN pds_musa_sessions.webhook_url IS
    'Musa endpoint to POST results to on completion or failure';
COMMENT ON COLUMN pds_musa_sessions.retry_count IS
    'Processing attempts so far; worker stops retrying at 3';
