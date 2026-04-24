# Thesis Creation Fix Guide

## Issues Fixed

1. **Database Schema Error**: Missing columns in `thesis` table
2. **Authentication Errors**: 401 errors when creating thesis
3. **Performance Issues**: Slow saves and unresponsive skip button

## Solution Steps

### Step 1: Run Database Migration

The `thesis` table is missing several columns. Run this SQL in your Supabase SQL Editor:

**File**: `migrations/fix_thesis_table.sql`

```sql
-- Add missing columns to thesis table
ALTER TABLE thesis 
ADD COLUMN IF NOT EXISTS geography_constraints JSONB,
ADD COLUMN IF NOT EXISTS stage_preferences JSONB,
ADD COLUMN IF NOT EXISTS min_revenue_usd NUMERIC,
ADD COLUMN IF NOT EXISTS governance_requirements JSONB,
ADD COLUMN IF NOT EXISTS financial_thresholds JSONB,
ADD COLUMN IF NOT EXISTS data_confidence_tolerance TEXT,
ADD COLUMN IF NOT EXISTS impact_requirements JSONB,
ADD COLUMN IF NOT EXISTS name TEXT,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();
```

**How to run:**
1. Go to your Supabase Dashboard
2. Navigate to SQL Editor
3. Copy and paste the SQL above
4. Click "Run"

### Step 2: Verify Migration

After running the migration, verify the columns exist:

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'thesis'
ORDER BY ordinal_position;
```

You should see all columns including:
- `geography_constraints`
- `stage_preferences`
- `min_revenue_usd`
- `governance_requirements`
- `financial_thresholds`
- `data_confidence_tolerance`
- `impact_requirements`
- `name`
- `created_at`

### Step 3: Code Changes Made

#### Backend (`backend/routes/deals.py`)
- Updated `create_thesis` endpoint to only insert/update columns that exist
- Added better error messages for schema errors
- Improved error handling

#### Frontend (`components/ThesisOnboarding.tsx`)
- Made `handleSkip` async with proper loading state
- Added loading indicator to skip button
- Improved error handling

#### API Client (`lib/api.ts`)
- Enhanced session handling with refresh on 401 errors
- Better error recovery for authentication issues

## Testing

After running the migration:

1. **Test Thesis Creation**:
   - Go to `/onboarding/thesis`
   - Fill out the form and click "Save"
   - Should save successfully without errors

2. **Test Skip Button**:
   - Go to `/onboarding/thesis`
   - Click "Skip (Use Defaults)"
   - Button should show "Creating..." and complete quickly
   - Should redirect to `/deals` after success

3. **Test Authentication**:
   - Ensure you're logged in
   - Check browser console for any 401 errors
   - Should not see "Not authenticated" warnings

## Troubleshooting

### Still Getting "Column not found" Error?

1. Verify the migration ran successfully (use Step 2 SQL)
2. Check that you're running the SQL in the correct Supabase project
3. Ensure you have the correct database selected

### Still Getting 401 Errors?

1. Check that your session is valid:
   - Open browser console
   - Check for session errors
   - Try logging out and back in

2. Verify environment variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` (should point to your backend)

3. Check backend logs for authentication errors

### Skip Button Still Not Responsive?

1. Check browser console for errors
2. Verify the API endpoint is responding
3. Check network tab for failed requests

## Next Steps

After fixing these issues, you should be able to:
- ✅ Create a thesis successfully
- ✅ Use the skip button without delays
- ✅ Avoid authentication errors during thesis creation
