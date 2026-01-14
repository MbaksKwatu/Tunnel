-- Create deals table
CREATE TABLE deals (
    id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    geography TEXT NOT NULL,
    deal_type TEXT NOT NULL,
    stage TEXT NOT NULL,
    revenue_usd NUMERIC,
    created_by TEXT REFERENCES users(id),
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create thesis table
CREATE TABLE thesis (
    id TEXT PRIMARY KEY,
    fund_id TEXT REFERENCES users(id),
    investment_focus TEXT,
    sector_preferences JSONB,
    kill_conditions JSONB,
    weights JSONB,
    is_default BOOLEAN DEFAULT FALSE
);

-- Create evidence table
CREATE TABLE evidence (
    id TEXT PRIMARY KEY,
    deal_id TEXT REFERENCES deals(id) ON DELETE CASCADE,
    document_id TEXT REFERENCES documents(id),
    evidence_type TEXT NOT NULL,
    extracted_data JSONB,
    confidence_score FLOAT DEFAULT 0.7,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Create judgments table
CREATE TABLE judgments (
    id TEXT PRIMARY KEY,
    deal_id TEXT REFERENCES deals(id) ON DELETE CASCADE,
    investment_readiness TEXT,
    thesis_alignment TEXT,
    kill_signals JSONB,
    confidence_level TEXT,
    dimension_scores JSONB,
    explanations JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_deals_created_by ON deals(created_by);
CREATE INDEX idx_evidence_deal_id ON evidence(deal_id);
CREATE INDEX idx_judgments_deal_id ON judgments(deal_id);
