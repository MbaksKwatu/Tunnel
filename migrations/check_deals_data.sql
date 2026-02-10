-- Check deals data (bypasses RLS when run with service role)
-- This will show all deals regardless of RLS policies

-- 1. Check if any deals exist
SELECT COUNT(*) as total_deals FROM deals;

-- 2. Show all deals with their created_by values
SELECT 
    id, 
    company_name, 
    created_by, 
    created_by::text as created_by_text,
    status,
    created_at 
FROM deals 
ORDER BY created_at DESC
LIMIT 20;

-- 3. Check what user IDs exist in auth.users (to see valid user IDs)
SELECT id, email, created_at 
FROM auth.users 
ORDER BY created_at DESC
LIMIT 10;

-- 4. Compare: deals created_by vs actual user IDs
-- This helps identify if there's a mismatch
SELECT 
    d.id as deal_id,
    d.company_name,
    d.created_by::text as deal_created_by,
    u.id::text as user_id,
    u.email,
    CASE 
        WHEN d.created_by::text = u.id::text THEN 'MATCH'
        ELSE 'NO MATCH'
    END as match_status
FROM deals d
LEFT JOIN auth.users u ON d.created_by::text = u.id::text
ORDER BY d.created_at DESC;
