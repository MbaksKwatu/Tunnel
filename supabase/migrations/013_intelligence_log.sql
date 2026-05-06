-- Immutable log of all intelligence queries and responses
CREATE TABLE IF NOT EXISTS pds_intelligence_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id UUID NOT NULL REFERENCES pds_deals(id) ON DELETE CASCADE,
  query_text TEXT NOT NULL,
  query_type TEXT NOT NULL CHECK (query_type IN ('classification', 'computation', 'pattern')),
  user_role TEXT NOT NULL CHECK (user_role IN ('analyst', 'officer')),
  user_id UUID REFERENCES auth.users(id),
  analyst_initials TEXT,
  response_text TEXT NOT NULL,
  basis_sources JSONB,
  computation_steps JSONB,
  is_logged BOOLEAN DEFAULT false,
  logged_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intelligence_log_deal ON pds_intelligence_log(deal_id);
CREATE INDEX IF NOT EXISTS idx_intelligence_log_logged ON pds_intelligence_log(deal_id, is_logged);
