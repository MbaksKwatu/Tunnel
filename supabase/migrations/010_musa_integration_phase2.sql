-- Migration: Musa Ventures integration phase 2
-- Adds document URL storage, error tracking, and venture country to musa_sessions

ALTER TABLE musa_sessions ADD COLUMN IF NOT EXISTS venture_country TEXT;
ALTER TABLE musa_sessions ADD COLUMN IF NOT EXISTS document_urls   JSONB;
ALTER TABLE musa_sessions ADD COLUMN IF NOT EXISTS error_message   TEXT;

-- Indexes already exist from 009 — IF NOT EXISTS keeps this idempotent
CREATE INDEX IF NOT EXISTS idx_musa_sessions_status  ON musa_sessions(status);
CREATE INDEX IF NOT EXISTS idx_musa_sessions_deal_id ON musa_sessions(deal_id);
