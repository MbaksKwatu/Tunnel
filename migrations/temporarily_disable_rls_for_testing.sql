-- Temporarily disable RLS to test if that's blocking deal creation
-- WARNING: Only use for testing! Re-enable RLS after testing.

-- Check current RLS status
SELECT tablename, rowsecurity FROM pg_tables WHERE tablename = 'deals';

-- Temporarily disable RLS (for testing only)
ALTER TABLE deals DISABLE ROW LEVEL SECURITY;

-- After testing, re-enable with:
-- ALTER TABLE deals ENABLE ROW LEVEL SECURITY;
