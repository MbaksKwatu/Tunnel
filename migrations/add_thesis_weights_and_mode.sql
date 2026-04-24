-- Add thesis scoring weights and judgment mode (Phase 1 defaults)
-- Run in Supabase SQL editor or psql against the same database.

ALTER TABLE thesis
ADD COLUMN IF NOT EXISTS weights JSONB,
ADD COLUMN IF NOT EXISTS judgment_mode TEXT DEFAULT 'default';

-- Backfill existing rows with default weights if NULL
UPDATE thesis
SET weights = '{"cashflow":40,"governance":20,"team":20,"market":20}'::jsonb
WHERE weights IS NULL;

-- Ensure judgment_mode has a default value
UPDATE thesis
SET judgment_mode = COALESCE(judgment_mode, 'default');

-- Verify
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'thesis';
