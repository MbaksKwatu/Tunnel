-- Migration: Musa Ventures simple integration
-- Tables: musa_sessions, api_keys

CREATE TABLE IF NOT EXISTS musa_sessions (
  session_id    varchar PRIMARY KEY,
  venture_id    text NOT NULL,
  venture_name  text NOT NULL,
  deal_id       uuid REFERENCES pds_deals(id) ON DELETE SET NULL,
  status        text NOT NULL DEFAULT 'processing'
                  CHECK (status IN ('processing', 'complete', 'failed')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz
);

CREATE INDEX IF NOT EXISTS idx_musa_sessions_deal_id
  ON musa_sessions(deal_id);

CREATE INDEX IF NOT EXISTS idx_musa_sessions_status
  ON musa_sessions(status);

CREATE TABLE IF NOT EXISTS api_keys (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  partner_name  text NOT NULL,
  api_key_hash  text NOT NULL,
  active        boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_active
  ON api_keys(active);
