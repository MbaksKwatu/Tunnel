# Deal conversations migration (Ask Parity)

The Ask Parity chat stores messages in a table called `deal_conversations`. That table must exist in your Supabase database before the feature works.

## What “run the migration” means

- **Migration** = the SQL that creates the `deal_conversations` table (and its indexes).
- **“Run” it** = execute that SQL once in your Supabase project.

If you never run it, the backend will get errors when saving or loading chat (e.g. “relation deal_conversations does not exist”).

## How to run it in Supabase

1. Open [Supabase Dashboard](https://app.supabase.com) and select your project.
2. In the left sidebar, go to **SQL Editor**.
3. Click **New query**.
4. Paste the contents of `add_deal_conversations.sql` (or the SQL below).
5. Click **Run** (or press Cmd/Ctrl+Enter).

## SQL to run

```sql
-- Ask Parity v0: conversation storage per deal
CREATE TABLE deal_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id TEXT NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_deal_conversations_deal_id ON deal_conversations(deal_id);
CREATE INDEX idx_deal_conversations_created_at ON deal_conversations(deal_id, created_at DESC);
```

## If it’s already applied

If `deal_conversations` already exists (e.g. you ran this before), running the SQL again will cause “relation already exists” errors. In that case you can ignore the migration; the feature is already set up.

## Quick check

In Supabase: **Table Editor** → look for a table named `deal_conversations`.  
If it’s there, the migration has already been applied.
