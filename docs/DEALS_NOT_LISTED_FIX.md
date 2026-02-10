# Fix: Deals Created But Not Listed

## Problem
- Deals are created "successfully" but don't appear in the deals list
- Network tab shows `204 No Content` for `/deals` request
- Evidence upload section not visible (actually it is visible on deal detail page)

## Root Causes

1. **RLS Policies**: Row Level Security might be blocking reads
2. **User ID Format**: UUID format mismatch between `created_by` and `auth.uid()`
3. **Response Format**: Backend should always return 200 with array (not 204)

## Solutions

### Step 1: Fix RLS Policies

Run this SQL in Supabase SQL Editor:

**File**: `migrations/fix_deals_rls.sql`

```sql
-- Enable RLS
ALTER TABLE deals ENABLE ROW LEVEL SECURITY;

-- Drop existing policies
DROP POLICY IF EXISTS "Users can view their own deals" ON deals;
DROP POLICY IF EXISTS "Users can insert their own deals" ON deals;
DROP POLICY IF EXISTS "Users can update their own deals" ON deals;
DROP POLICY IF EXISTS "Users can delete their own deals" ON deals;

-- Create policies
CREATE POLICY "Users can view their own deals"
ON deals FOR SELECT
USING (auth.uid()::text = created_by);

CREATE POLICY "Users can insert their own deals"
ON deals FOR INSERT
WITH CHECK (auth.uid()::text = created_by);

CREATE POLICY "Users can update their own deals"
ON deals FOR UPDATE
USING (auth.uid()::text = created_by)
WITH CHECK (auth.uid()::text = created_by);

CREATE POLICY "Users can delete their own deals"
ON deals FOR DELETE
USING (auth.uid()::text = created_by);
```

### Step 2: Verify Deals Exist

Check if deals are actually in the database:

```sql
-- Check all deals
SELECT id, company_name, created_by, created_at 
FROM deals 
ORDER BY created_at DESC;

-- Check deals for a specific user (replace USER_ID)
SELECT id, company_name, created_by, created_at 
FROM deals 
WHERE created_by = 'USER_ID'
ORDER BY created_at DESC;
```

### Step 3: Check Your User ID

Get your current user ID from Supabase:

```sql
-- Get current authenticated user
SELECT auth.uid() as current_user_id;
```

Then verify your deals match:

```sql
-- Replace YOUR_USER_ID with the UUID from above
SELECT * FROM deals WHERE created_by = 'YOUR_USER_ID';
```

### Step 4: Code Changes Made

1. **Backend** (`backend/routes/deals.py`):
   - Added logging to track user_id and deal count
   - Ensured endpoint always returns 200 with `{"deals": []}` even if empty
   - Better error handling

2. **Storage** (`backend/local_storage.py`):
   - Added logging to track queries
   - Better error messages

## Testing

After running the migration:

1. **Create a new deal**:
   - Go to `/deals/new`
   - Fill out the form and submit
   - Should see success message

2. **Check deals list**:
   - Go to `/deals`
   - Should see your newly created deal
   - Network tab should show `200 OK` with `{"deals": [...]}`

3. **View deal detail**:
   - Click on a deal
   - Should see "Evidence Upload" section
   - Should be able to upload files

## Troubleshooting

### Still seeing 204 No Content?

1. Check browser console for errors
2. Check backend logs for authentication errors
3. Verify your session token is valid

### Deals still not showing?

1. Run the verification SQL queries above
2. Check if `created_by` field matches your user ID
3. Check RLS policies are active:
   ```sql
   SELECT * FROM pg_policies WHERE tablename = 'deals';
   ```

### Evidence upload not visible?

The evidence upload section is on the deal detail page (`/deals/{deal_id}`), not the deals list page. Make sure you're viewing a specific deal.

## Next Steps

1. Run the RLS migration SQL
2. Test creating a new deal
3. Verify it appears in the list
4. Check backend logs if issues persist
