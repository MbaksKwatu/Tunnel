-- Ask Parity v0: conversation storage per deal
-- Run in Supabase SQL Editor or via migration process

CREATE TABLE deal_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id TEXT NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_deal_conversations_deal_id ON deal_conversations(deal_id);
CREATE INDEX idx_deal_conversations_created_at ON deal_conversations(deal_id, created_at DESC);
