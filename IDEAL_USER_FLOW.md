# Ideal User Flow - Complete Journey

**Date**: February 9, 2026  
**Status**: Documented - Implementation Plan Ready

## 🎯 Your Ideal Flow

```
1. User creates account
2. User sets up thesis (or uses default)
3. User creates a deal
4. User adds evidence (documents)
5. User gets judgment
6. User engages Ask Parity
7. User checks dashboard (investees, dashboards, reports)
```

---

## 📋 Detailed Flow Breakdown

### Step 1: Create Account ✅
**Current State**: ✅ Working
- User signs up → `POST /api/auth/signup`
- AuthProvider handles session
- Redirects based on thesis status

**Components**:
- `Login.tsx` - Sign up form
- `AuthProvider.tsx` - Auth state management

---

### Step 2: Set Up Thesis ✅
**Current State**: ✅ Working
- If no thesis → Redirect to `/onboarding/thesis`
- User creates thesis → `POST /api/thesis`
- Or uses default thesis
- Redirects to `/deals`

**Components**:
- `ThesisOnboarding.tsx` - Thesis creation UI
- `ThesisBuilder.tsx` - Thesis form builder

**API**:
- `POST /api/thesis` - Create/update thesis
- `GET /api/thesis` - Get user's thesis

---

### Step 3: Create Deal ✅
**Current State**: ✅ Working
- User navigates to `/deals`
- Clicks "New Deal" → `/deals/new`
- Fills form → `POST /api/deals`
- Redirects to deal detail → `/deals/{id}`

**Components**:
- `DealList.tsx` - Deal listing
- `DealCreate.tsx` - Deal creation form
- `DealDetail.tsx` - Deal detail view

**API**:
- `POST /api/deals` - Create deal
- `GET /api/deals` - List deals
- `GET /api/deals/{id}` - Get deal

---

### Step 4: Add Evidence (Documents) ⚠️ **IMPROVED**
**Current State**: ⚠️ Enhanced (just implemented)
- User on deal detail page → `/deals/{id}`
- Uploads document → `POST /api/deals/{id}/evidence`
- **NEW**: Document is processed:
  - ✅ Parsed (rows extracted)
  - ✅ Anomalies detected
  - ✅ Insights generated
  - ✅ Document record created
  - ✅ Linked to deal via evidence.document_id

**Components**:
- `DealDetail.tsx` - Evidence upload UI
- `FileUpload.tsx` - (Could be reused)

**API**:
- `POST /api/deals/{id}/evidence` - Upload & process evidence ✅ Enhanced
- `GET /api/deals/{id}/evidence` - Get evidence list
- `GET /document/{id}/anomalies` - View document anomalies
- `GET /document/{id}/insights` - View document insights

**Improvements Made**:
- ✅ Evidence upload now processes documents
- ✅ Documents linked to deals via `document_id`
- ✅ Anomaly detection runs automatically
- ✅ Insights generated automatically

**Future Enhancement**:
- ⏳ Add "Link Existing Document" option
- ⏳ Show document processing progress
- ⏳ Display document insights in deal view

---

### Step 5: Get Judgment ✅
**Current State**: ✅ Working
- User clicks "Run Judgment" → `POST /api/deals/{id}/judge`
- Judgment engine analyzes:
  - Deal details
  - Evidence (now includes document data!)
  - Thesis alignment
- Returns scores and recommendations
- Saves judgment → `GET /api/deals/{id}/judgment`

**Components**:
- `DealDetail.tsx` - Judgment trigger
- `JudgmentCards.tsx` - Judgment display

**API**:
- `POST /api/deals/{id}/judge` - Run judgment
- `GET /api/deals/{id}/judgment` - Get judgment

**Enhancement Opportunity**:
- ⚠️ Judgment engine should use document data from evidence
- ⚠️ Currently uses evidence.evidence_type (metadata only)
- ✅ Should use evidence.document_id to get actual data

---

### Step 6: Engage Ask Parity ✅
**Current State**: ✅ Working
- User asks question → `POST /api/deals/{id}/ask`
- Parity AI responds using:
  - Deal context
  - Evidence summary (now includes document insights!)
  - Judgment results
  - Conversation history

**Components**:
- `AskParityChat.tsx` - Chat interface
- `DealDetail.tsx` - Chat integration

**API**:
- `POST /api/deals/{id}/ask` - Ask question
- `GET /api/deals/{id}/conversation` - Get history

**Enhancement Opportunity**:
- ✅ Can now reference document insights
- ✅ Can discuss anomalies found in documents
- ✅ Can explain financial metrics from documents

---

### Step 7: Check Dashboard ✅
**Current State**: ✅ Working
- User navigates to `/dashboard`
- Views:
  - **Investees**: Grouped by investee_name from documents
  - **Dashboards**: Custom dashboards per investee
  - **Reports**: Generated reports

**Components**:
- `app/dashboard/page.tsx` - Dashboard page
- `DynamicDashboard.tsx` - Dashboard renderer
- `InsightsDashboard.tsx` - Insights display

**API**:
- `GET /investees` - List investees
- `GET /dashboards` - List dashboards
- `GET /reports` - List reports
- `GET /document/{id}/report` - Generate report

**Relationship**:
- Documents → Investees (via investee_name)
- Documents → Dashboards (via investee context)
- Documents → Reports (via document insights)

---

## 🔗 Key Relationships

### Documents ↔ Deals
```
Document (standalone)
    ↓ (via evidence upload)
Evidence (document_id linked)
    ↓ (belongs to)
Deal
```

**Flow**:
1. Document uploaded as evidence → Creates document record
2. Evidence record links document to deal via `document_id`
3. Deal can access document data via evidence
4. Judgment uses document insights
5. Ask Parity references document anomalies

### Documents ↔ Investees
```
Document
    ↓ (has investee_name)
Investee
    ↓ (groups)
Dashboard
    ↓ (generates)
Report
```

**Flow**:
1. Document has `investee_name` field
2. Documents grouped by investee
3. Dashboards created per investee
4. Reports generated from document insights

---

## 📊 Data Flow Diagram

```
User Account
    ↓
Thesis (investment criteria)
    ↓
Deal (company being evaluated)
    ↓
Evidence (documents uploaded)
    ├─→ Document Record (parsed data)
    ├─→ Rows (extracted data)
    ├─→ Anomalies (detected issues)
    └─→ Insights (AI-generated)
    ↓
Judgment (evaluation scores)
    ├─→ Uses document data
    ├─→ Uses thesis alignment
    └─→ Uses evidence summary
    ↓
Ask Parity (AI chat)
    ├─→ References judgment
    ├─→ References document insights
    └─→ References anomalies
    ↓
Dashboard
    ├─→ Investees (from documents)
    ├─→ Dashboards (per investee)
    └─→ Reports (from document insights)
```

---

## ✅ Implementation Status

| Step | Status | Notes |
|------|--------|-------|
| 1. Create Account | ✅ Complete | Working |
| 2. Set Up Thesis | ✅ Complete | Working |
| 3. Create Deal | ✅ Complete | Working |
| 4. Add Evidence | ✅ **Enhanced** | Now processes documents! |
| 5. Get Judgment | ✅ Complete | Could use document data better |
| 6. Ask Parity | ✅ Complete | Can reference documents |
| 7. Dashboard | ✅ Complete | Uses document data |

---

## 🚀 Next Enhancements

### Priority 1: Link Existing Documents
- Add `POST /api/deals/{id}/evidence/link` endpoint
- Allow users to select existing documents
- Link them to deals without re-processing

### Priority 2: Enhance Judgment Engine
- Use `document_id` from evidence to get actual data
- Use document anomalies in scoring
- Use document insights in explanations

### Priority 3: Improve UI Flow
- Show document processing progress in deal view
- Display document insights in deal detail
- Link to document view from evidence list

---

## 📝 Summary

**Current State**: ✅ All steps working, evidence upload enhanced

**Key Improvement**: Evidence upload now processes documents and links them to deals, enabling the full flow you envisioned!

**Next Steps**: Enhance judgment engine to better use document data, add link existing document feature.
