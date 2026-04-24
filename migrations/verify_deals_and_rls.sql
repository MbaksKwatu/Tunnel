-- Verification queries for deals and RLS policies
-- Run these one by one to diagnose the issue

-- 1. Check if RLS policies were created
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual 
FROM pg_policies 
WHERE tablename = 'deals';

-- 2. Check the data type of created_by column
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'deals' AND column_name = 'created_by';

-- 3. Check if RLS is enabled
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE tablename = 'deals';

-- 4. Get your current authenticated user ID
SELECT auth.uid() as current_user_id, auth.uid()::text as current_user_id_text;

-- 5. Check ALL deals in the table (bypasses RLS - use service role key)
SELECT id, company_name, created_by, created_by::text as created_by_text, created_at 
FROM deals 
ORDER BY created_at DESC
LIMIT 10;

-- 6. Check deals for your specific user (replace YOUR_USER_ID with the UUID from query 4)
-- First, get your user ID from query 4, then run:
-- SELECT id, company_name, created_by, created_by::text as created_by_text, created_at 
-- FROM deals 
-- WHERE created_by::text = 'YOUR_USER_ID'
-- ORDER BY created_at DESC;

-- 7. Test if you can see deals with current policies (should return rows if policies work)
SELECT id, company_name, created_by, created_at 
FROM deals 
WHERE created_by::text = auth.uid()::text
ORDER BY created_at DESC;
