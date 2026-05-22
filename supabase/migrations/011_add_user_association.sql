-- Add user association and deal metadata to pds_deals
ALTER TABLE pds_deals ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE pds_deals ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE pds_deals ADD COLUMN IF NOT EXISTS analyst_initials VARCHAR(3);

CREATE INDEX IF NOT EXISTS idx_deals_user_id ON pds_deals(user_id);
