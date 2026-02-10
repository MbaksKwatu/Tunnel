# End-to-End Testing Guide: ParitySME Full Flow

This guide walks through testing the complete user flow from account creation to Ask Parity engagement.

---

## Prerequisites

1. **Backend running**: `cd backend && python -m uvicorn main:app --reload`
2. **Frontend running**: `npm run dev`
3. **Supabase configured**: Environment variables set
4. **OpenAI API key**: Set in backend environment (`OPENAI_API_KEY`)

---

## Complete Flow Test

### Step 1: User Account Creation ✅

**URL**: `http://localhost:3000/login`

**Test Steps**:
1. Navigate to `/login`
2. Click "Sign up" or toggle to signup mode
3. Enter:
   - Email: `test@example.com`
   - Password: `TestPassword123!`
4. Click "Sign Up"
5. **Expected**: 
   - Success message: "Check your email to confirm your account!"
   - OR redirect to `/onboarding/thesis` if email confirmation is disabled

**Verification**:
- Check Supabase Auth dashboard for new user
- User should be created in `auth.users` table

---

### Step 2: Thesis Creation or Default Selection ✅

**URL**: `http://localhost:3000/onboarding/thesis`

**Test Steps**:
1. After signup/login, you should be redirected here
2. **Option A - Create Custom Thesis**:
   - Fill out thesis form:
     - Investment Focus: Select (e.g., "debt")
     - Sector Preferences: Select (e.g., ["fintech", "logistics"])
     - Geography Constraints: Select (e.g., ["kenya", "nigeria"])
     - Stage Preferences: Select (e.g., ["early_revenue", "growth"])
     - Minimum Revenue: Enter (e.g., 100000)
     - Kill Conditions: Add (e.g., ["No license for fintech"])
     - Governance Requirements: Add (e.g., ["Board structure"])
     - Financial Thresholds: Set (e.g., `{"min_margin": 0.15}`)
     - Weights: Adjust (e.g., `{"financial": 40, "governance": 20, ...}`)
   - Click "Save Thesis"
   - **Expected**: Redirect to `/deals`

3. **Option B - Use Default Thesis**:
   - Click "Skip" or "Use Default"
   - **Expected**: Creates default thesis and redirects to `/deals`

**Verification**:
- Check `thesis` table in Supabase
- Should have one record with `fund_id` = user's ID
- If skipped, `is_default` should be `true`

---

### Step 3: Create a Deal ✅

**URL**: `http://localhost:3000/deals/new`

**Test Steps**:
1. Navigate to `/deals/new` (or click "New Deal" from deals list)
2. Fill out deal form:
   - Company Name: `Test Company Ltd`
   - Sector: `fintech`
   - Geography: `kenya`
   - Deal Type: `debt`
   - Stage: `early_revenue`
   - Revenue (Optional): `250000`
3. Click "Create Deal"
4. **Expected**: 
   - Redirect to `/deals/{deal_id}`
   - Deal detail page shows deal information

**Verification**:
- Check `deals` table in Supabase
- Deal should have `created_by` = user's ID
- Status should be `draft`

---

### Step 4: Upload Evidence ✅

**URL**: `http://localhost:3000/deals/{deal_id}`

**Test Steps**:
1. On deal detail page, find "Upload Evidence" section
2. Click file input or drag & drop files
3. Upload test files:
   - `financial_statements.pdf` (or CSV/XLSX)
   - `bank_statements.pdf`
   - `governance_docs.pdf` (optional)
4. **Expected**:
   - Files upload successfully
   - Evidence list updates
   - Files appear in "Evidence" section
   - Processing status shows

**Verification**:
- Check `evidence` table in Supabase
- Should have records with `deal_id` matching the deal
- Check `documents` table for uploaded files
- Check `extracted_rows` table for parsed data (if processing completed)

**Test Files**:
- Use sample PDF/CSV/XLSX files from `backend/test_data/` if available
- Or create simple test files:
  - CSV with financial data
  - PDF with tables
  - Excel with transaction data

---

### Step 5: Run Judgment ✅

**URL**: `http://localhost:3000/deals/{deal_id}`

**Test Steps**:
1. Ensure at least one evidence file is uploaded
2. Scroll to "Actions" section
3. Click "Run Judgment" button
4. **Expected**:
   - Button shows "Running Judgment..." with spinner
   - After completion (5-30 seconds):
     - "Judgment Results" section appears
     - Shows:
       - Investment Readiness (READY/CONDITIONALLY_READY/NOT_READY)
       - Thesis Alignment (ALIGNED/PARTIALLY_ALIGNED/MISALIGNED)
       - Dimension Scores (Financial, Governance, Market, Team, Product, Data Confidence)
       - Kill Signals (if any)
       - Explanations
       - Missing Evidence Suggestions

**Verification**:
- Check `judgments` table in Supabase
- Should have one record with `deal_id` matching the deal
- `dimension_scores` should be a JSON object with scores
- `explanations` should contain explanation text
- `investment_readiness` and `thesis_alignment` should be set

**Expected Judgment Output**:
```json
{
  "investment_readiness": "CONDITIONALLY_READY",
  "thesis_alignment": "PARTIALLY_ALIGNED",
  "confidence_level": "MEDIUM",
  "dimension_scores": {
    "financial": 65.0,
    "governance": 55.0,
    "market": 70.0,
    "team": 50.0,
    "product": 60.0,
    "data_confidence": 70.0
  },
  "kill_signals": {
    "type": "NONE"
  },
  "explanations": {
    "investment_readiness": "...",
    "thesis_alignment": "...",
    "kill_signals": "..."
  }
}
```

---

### Step 6: Ask Parity - Engage with Judgment ✅

**URL**: `http://localhost:3000/deals/{deal_id}`

**Test Steps**:
1. Scroll to "Ask Parity" chat section
2. **Test Questions** (try these in order):

   **a) Before Judgment**:
   - "What evidence do we have for this deal?"
   - **Expected**: Lists evidence types (financials, bank statements, governance)
   - "Can you explain the investment readiness?"
   - **Expected**: "Judgment has not yet been run for this deal, so I cannot explain scores."

   **b) After Judgment**:
   - "Explain the financial score"
   - **Expected**: Explains what the financial score (e.g., 65/100) means, references the explanation
   
   - "What does the judgment say about this deal?"
   - **Expected**: Summarizes investment readiness, thesis alignment, key scores
   
   - "Why is the governance score low?"
   - **Expected**: References governance score and explanation, discusses what might improve it
   
   - "What evidence are we missing?"
   - **Expected**: Lists missing evidence suggestions from judgment
   
   - "What would improve the investment readiness score?"
   - **Expected**: Discusses missing evidence and how it could improve scores
   
   - "Summarize this deal"
   - **Expected**: Company, sector, stage, evidence present, judgment status, readiness level, alignment

3. **Expected Behavior**:
   - Messages appear in chat
   - Parity responds with context-aware answers
   - Responses reference judgment results when available
   - Responses explain scores and what they mean
   - Responses suggest follow-up actions (soft language)

**Verification**:
- Check `deal_conversations` table in Supabase
- Should have conversation history with user and assistant messages
- Messages should be ordered by `created_at`

**Enhanced Features** (after our update):
- ✅ Parity includes all dimension scores in context
- ✅ Parity can explain judgment results in detail
- ✅ Parity references explanations from judgment
- ✅ Parity discusses missing evidence suggestions
- ✅ Parity helps understand scores in context

---

## Troubleshooting

### Issue: Authentication not working
- **Check**: Supabase environment variables (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`)
- **Check**: Supabase Auth is enabled in dashboard
- **Check**: Email confirmation settings (may need to disable for testing)

### Issue: Thesis creation fails
- **Check**: `thesis` table exists in Supabase
- **Check**: Backend API endpoint `/api/thesis` is accessible
- **Check**: User ID is correctly passed

### Issue: Deal creation fails
- **Check**: `deals` table exists in Supabase
- **Check**: Backend API endpoint `/api/deals` is accessible
- **Check**: User is authenticated (check `session`)

### Issue: Evidence upload fails
- **Check**: File size limits
- **Check**: File type is supported (PDF, CSV, XLSX)
- **Check**: Backend `/api/deals/{deal_id}/evidence` endpoint
- **Check**: Supabase Storage bucket `uploads` exists

### Issue: Judgment fails
- **Check**: At least one evidence file is uploaded
- **Check**: Thesis exists for the user
- **Check**: Backend logs for errors
- **Check**: Judgment engine has all required data

### Issue: Ask Parity not responding
- **Check**: `OPENAI_API_KEY` is set in backend environment
- **Check**: Backend logs for OpenAI API errors
- **Check**: `deal_conversations` table exists (run migration)
- **Check**: Network connectivity to OpenAI API

---

## Quick Test Checklist

- [ ] User can sign up
- [ ] User can log in
- [ ] User is redirected to thesis onboarding if no thesis exists
- [ ] User can create custom thesis
- [ ] User can skip to default thesis
- [ ] User can create a deal
- [ ] User can upload evidence files
- [ ] Evidence files are processed
- [ ] User can run judgment
- [ ] Judgment results are displayed
- [ ] Ask Parity responds before judgment (with "not run" message)
- [ ] Ask Parity responds after judgment (with judgment context)
- [ ] Ask Parity explains scores
- [ ] Ask Parity references judgment explanations
- [ ] Ask Parity discusses missing evidence
- [ ] Conversation history persists

---

## Sample Test Data

### Test Deal 1: Fintech Company
- Company: `Mpesa Fintech Ltd`
- Sector: `fintech`
- Geography: `kenya`
- Deal Type: `debt`
- Stage: `early_revenue`
- Revenue: `500000`

### Test Deal 2: Logistics Company
- Company: `Fast Logistics Kenya`
- Sector: `logistics`
- Geography: `kenya`
- Deal Type: `equity`
- Stage: `growth`
- Revenue: `2000000`

---

## Next Steps After Testing

1. **Fix any bugs** found during testing
2. **Enhance UX** based on testing experience
3. **Add more test cases** for edge cases
4. **Document** any issues found
5. **Deploy** to staging/production

---

## Success Criteria

✅ **Full flow works end-to-end**:
- User can complete all 6 steps without errors
- All data persists correctly
- Ask Parity provides helpful, context-aware responses
- Judgment results are accurate and useful

✅ **Ask Parity enhancement works**:
- Includes all judgment context
- Explains scores meaningfully
- References explanations
- Discusses missing evidence
- Helps user understand judgment results

---

**Last Updated**: February 9, 2026
**Status**: Ready for Testing
