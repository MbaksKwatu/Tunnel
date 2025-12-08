-- Complete Setup for Parity Supabase Project
-- Run this in your new Supabase Project's SQL Editor

-- 1. Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Create Tables

-- Documents Table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID, -- Can map to auth.users id
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'csv', 'xlsx')),
    file_url TEXT,
    format_detected TEXT,
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'completed', 'failed')),
    rows_count INTEGER DEFAULT 0,
    anomalies_count INTEGER DEFAULT 0,
    error_message TEXT,
    insights_summary JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Extracted Rows Table
CREATE TABLE IF NOT EXISTS extracted_rows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    raw_json JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(document_id, row_index)
);

-- Anomalies Table
CREATE TABLE IF NOT EXISTS anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    row_index INTEGER,
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    description TEXT NOT NULL,
    score REAL,
    suggested_action TEXT,
    metadata JSONB,
    raw_json JSONB,
    evidence JSONB,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Notes Table (for future compatibility, used in delete cleanup)
CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    anomaly_id UUID,
    parent_id UUID REFERENCES notes(id),
    author TEXT DEFAULT 'system',
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Create Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_extracted_rows_document_id ON extracted_rows(document_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_document_id ON anomalies(document_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity);

-- 4. Storage Bucket Setup
-- Note: You might need to create the bucket 'uploads' manually in the Supabase Dashboard -> Storage
INSERT INTO storage.buckets (id, name, public) 
VALUES ('uploads', 'uploads', false)
ON CONFLICT (id) DO NOTHING;

-- 5. Security Policies (RLS)

-- Enable RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;

-- Documents Policies
CREATE POLICY "Public access for demo" ON documents FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public access for demo rows" ON extracted_rows FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public access for demo anomalies" ON anomalies FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public access for demo notes" ON notes FOR ALL USING (true) WITH CHECK (true);

-- Storage Policies
CREATE POLICY "Public upload access" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'uploads');
CREATE POLICY "Public view access" ON storage.objects FOR SELECT USING (bucket_id = 'uploads');
CREATE POLICY "Public delete access" ON storage.objects FOR DELETE USING (bucket_id = 'uploads');

-- Note: The above policies are set to PUBLIC/ALL for the demo/MVP simplicity.
-- For production, you would restrict them to authenticated users (auth.uid() = user_id).
