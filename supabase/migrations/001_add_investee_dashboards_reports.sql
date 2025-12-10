-- Migration: Add investee_name, dashboards, and reports tables
-- Run this in Supabase SQL Editor after initial setup

-- 1. Add investee_name to documents table
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS investee_name TEXT;

-- 2. Create index for investee_name lookups
CREATE INDEX IF NOT EXISTS idx_documents_investee_name ON documents(investee_name);

-- 3. Create dashboards table for saved dashboard configurations
CREATE TABLE IF NOT EXISTS dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investee_name TEXT NOT NULL,
    dashboard_name TEXT NOT NULL,
    spec JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Create reports table for generated reports
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investee_name TEXT NOT NULL,
    report_name TEXT NOT NULL,
    report_type TEXT DEFAULT 'ic_report',
    dashboard_spec JSONB,
    storage_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Create analysis_results table for storing evaluation metrics
CREATE TABLE IF NOT EXISTS analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    analysis_type TEXT NOT NULL,
    results JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Create indexes for new tables
CREATE INDEX IF NOT EXISTS idx_dashboards_investee ON dashboards(investee_name);
CREATE INDEX IF NOT EXISTS idx_reports_investee ON reports(investee_name);
CREATE INDEX IF NOT EXISTS idx_analysis_document ON analysis_results(document_id);

-- 7. Enable RLS on new tables
ALTER TABLE dashboards ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;

-- 8. Create public access policies for demo
CREATE POLICY "Public access for dashboards" ON dashboards FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public access for reports" ON reports FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public access for analysis" ON analysis_results FOR ALL USING (true) WITH CHECK (true);
