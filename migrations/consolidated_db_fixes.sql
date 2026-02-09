-- Consolidated DB fixes for Parity Tunnel
-- Run in Supabase SQL Editor if you encounter missing columns or tables.

-- 1. Evidence: ensure uploaded_at exists (some schemas use upload_date)
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- 2. Judgments: add updated_at for upsert support
ALTER TABLE judgments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- 3. Documents: ensure columns used by backend exist
ALTER TABLE documents ADD COLUMN IF NOT EXISTS anomalies_count INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS insights_summary JSONB;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS investee_name TEXT;

-- 4. Deals/Thesis: reference auth.users if using Supabase Auth (optional)
-- If you get FK errors on created_by/fund_id, run:
-- ALTER TABLE deals DROP CONSTRAINT IF EXISTS deals_created_by_fkey;
-- ALTER TABLE deals ADD CONSTRAINT deals_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id);
-- ALTER TABLE thesis DROP CONSTRAINT IF EXISTS thesis_fund_id_fkey;
-- ALTER TABLE thesis ADD CONSTRAINT thesis_fund_id_fkey FOREIGN KEY (fund_id) REFERENCES auth.users(id);

-- 5. Dashboards/Reports: created if not exist by 001_add_investee_dashboards_reports.sql
-- No change needed if that migration was run.
