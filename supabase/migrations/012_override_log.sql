-- Convert role column to TEXT so the full classifier ontology can be stored
-- (role_enum only has 6 legacy values; classifier emits 25+ roles including needs_review)
ALTER TABLE pds_txn_entity_map ALTER COLUMN role TYPE TEXT USING role::TEXT;

-- Immutable audit log for transaction-level manual overrides
CREATE TABLE IF NOT EXISTS pds_override_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id UUID NOT NULL REFERENCES pds_deals(id) ON DELETE CASCADE,
  txn_uuid UUID NOT NULL,
  txn_hash TEXT NOT NULL,
  original_role TEXT NOT NULL,
  override_role TEXT NOT NULL,
  analyst_initials TEXT NOT NULL,
  user_id UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_override_log_deal ON pds_override_log(deal_id);
CREATE INDEX IF NOT EXISTS idx_override_log_txn ON pds_override_log(txn_uuid);
