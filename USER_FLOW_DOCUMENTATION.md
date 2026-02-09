# User Flow Documentation

**Date**: February 9, 2026  
**Status**: Complete

## 🔄 Core User Flows

### 1. Authentication Flow

```
1. User visits app → AuthProvider checks session
2. If no session → Redirect to /login
3. User signs in → AuthProvider.onAuthStateChange('SIGNED_IN')
4. Check if user has thesis:
   - No thesis → Redirect to /onboarding/thesis
   - Has thesis → Redirect to /deals
5. User signs out → Redirect to /login
```

**API Calls**:
- `GET /api/thesis` - Check if thesis exists
- `POST /api/thesis` - Create thesis (onboarding)

**Components**:
- `AuthProvider.tsx` - Manages auth state
- `Login.tsx` - Sign in/sign up UI
- `ThesisOnboarding.tsx` - Thesis creation

---

### 2. Document Upload Flow

```
1. User navigates to /upload
2. User drags/drops file → FileUpload component
3. File validation (PDF, CSV, XLSX)
4. Upload file:
   - Local mode: POST /parse (multipart/form-data)
   - Supabase mode: Upload to storage → POST /parse (JSON)
5. Backend processes:
   - Parse file → Extract rows
   - Detect anomalies
   - Generate insights
   - Store in database
6. Show upload progress → Update status
7. On completion:
   - Show investee confirmation modal (if name detected)
   - Refresh document list
8. User can view document → Navigate to document detail
```

**API Calls**:
- `POST /parse` - Upload and parse file
- `GET /documents` - List documents
- `GET /document/{id}` - Get document info

**Components**:
- `FileUpload.tsx` - File upload UI
- `DocumentList.tsx` - Document listing
- `InvesteeConfirmModal.tsx` - Investee name confirmation

---

### 3. Document Review Flow

```
1. User clicks "View" on document → Navigate to document detail
2. Load document data:
   - GET /document/{id}
   - GET /document/{id}/rows
   - GET /document/{id}/anomalies
3. Display in tabs:
   - Table: Show extracted rows
   - JSON: Show raw JSON
   - Anomalies: Show detected anomalies
   - Evaluate: Show metrics and charts
4. User interactions:
   - Filter/sort anomalies
   - Re-run detection: POST /analyze
   - Generate report: GET /document/{id}/report
   - Add notes: POST /document/{id}/notes
```

**API Calls**:
- `GET /document/{id}/rows` - Get extracted rows
- `GET /document/{id}/anomalies` - Get anomalies ✅
- `POST /analyze` - Re-run anomaly detection ✅
- `GET /document/{id}/evaluate` - Get metrics
- `GET /document/{id}/insights` - Get insights
- `GET /document/{id}/report` - Generate PDF ✅
- `POST /document/{id}/notes` - Create note

**Components**:
- `DataReview.tsx` - Main review interface
- `AnomalyTable.tsx` - Anomalies display
- `EvaluateView.tsx` - Metrics dashboard
- `NotesPanel.tsx` - Notes management

---

### 4. Deal Management Flow

```
1. User navigates to /deals
2. List deals: GET /api/deals
3. Create deal: POST /api/deals
4. View deal: GET /api/deals/{id}
5. Upload evidence: POST /api/deals/{id}/evidence
6. Run judgment: POST /api/deals/{id}/judge
7. View judgment: GET /api/deals/{id}/judgment
8. Ask Parity: POST /api/deals/{id}/ask
```

**API Calls**:
- `GET /api/deals` - List deals
- `POST /api/deals` - Create deal
- `GET /api/deals/{id}` - Get deal
- `POST /api/deals/{id}/evidence` - Upload evidence
- `POST /api/deals/{id}/judge` - Run judgment
- `GET /api/deals/{id}/judgment` - Get judgment
- `POST /api/deals/{id}/ask` - Ask Parity AI
- `GET /api/deals/{id}/conversation` - Get conversation

**Components**:
- `DealList.tsx` - Deal listing
- `DealCreate.tsx` - Create deal form
- `DealDetail.tsx` - Deal detail view
- `JudgmentCards.tsx` - Judgment display
- `AskParityChat.tsx` - AI chat interface

---

### 5. Dashboard Flow

```
1. User navigates to /dashboard
2. Load data:
   - GET /investees
   - GET /dashboards
   - GET /reports
3. Select investee → View dashboard
4. Save dashboard: POST /dashboards/save
5. View reports: GET /reports
```

**API Calls**:
- `GET /investees` - List investees
- `GET /dashboards` - List dashboards
- `POST /dashboards/save` - Save dashboard
- `GET /dashboards/{id}` - Get dashboard
- `GET /reports` - List reports

**Components**:
- `app/dashboard/page.tsx` - Dashboard page
- `DynamicDashboard.tsx` - Dashboard renderer
- `SaveDashboardModal.tsx` - Save dialog

---

## 🔍 Error Handling Flows

### Upload Errors
```
1. File validation fails → Show error message
2. Upload fails → Update status to 'error', show retry button
3. Password required → Show password modal
4. Processing timeout → Show timeout message, allow retry
```

### API Errors
```
1. Network error → Show connection error
2. 404 Not Found → Show "not found" message
3. 500 Server Error → Show generic error, log details
4. Auth error → Redirect to login
```

---

## 📊 Data Flow Diagrams

### Document Processing Pipeline
```
File Upload
    ↓
Parse File (PDF/CSV/XLSX)
    ↓
Extract Rows
    ↓
Store Rows in Database
    ↓
Detect Anomalies
    ↓
Generate Insights
    ↓
Update Document Status
    ↓
Return Success
```

### Anomaly Detection Flow
```
Get Document Rows
    ↓
Run Detection Algorithms:
  - Revenue Anomaly Detection
  - Expense Integrity Check
  - Cash Flow Consistency
  - Payroll Pattern Analysis
  - Declared Mismatch Check
  - Unsupervised Outlier Detection
    ↓
Store Anomalies
    ↓
Generate Insights
    ↓
Update Document Metadata
```

---

## 🎯 Key User Actions

| Action | Endpoint | Component | Flow |
|--------|----------|-----------|------|
| Upload File | `POST /parse` | FileUpload | Upload → Parse → Store |
| View Anomalies | `GET /document/{id}/anomalies` | AnomalyTable | Load → Display → Filter |
| Re-run Detection | `POST /analyze` | AnomalyTable | Trigger → Process → Refresh |
| Generate Report | `GET /document/{id}/report` | EvaluateView | Request → Generate → Download |
| Create Deal | `POST /api/deals` | DealCreate | Form → Submit → Redirect |
| Run Judgment | `POST /api/deals/{id}/judge` | DealDetail | Trigger → Process → Display |
| Ask Parity | `POST /api/deals/{id}/ask` | AskParityChat | Send → Process → Display |

---

## 🔐 Authentication & Authorization

### Public Endpoints
- `GET /` - Health check
- `GET /health` - Health check

### Protected Endpoints (Require Auth)
- All `/document/*` endpoints
- All `/api/deals/*` endpoints
- All `/api/thesis` endpoints
- All `/dashboards/*` endpoints

### Authorization
- Users can only access their own documents/deals
- RLS policies enforce data isolation in Supabase
- Frontend checks auth state before API calls

---

## 📱 Frontend Route Structure

```
/                    → Home page (redirects based on auth)
/login               → Login/signup page
/onboarding/thesis   → Thesis creation (first-time users)
/deals               → Deal list
/deals/new           → Create deal
/deals/{id}          → Deal detail
/upload              → File upload
/dashboard           → Dashboard page
/settings/thesis     → Thesis settings
```

---

## 🧪 Testing User Flows

### Test Scenarios

1. **New User Flow**
   - Sign up → Onboarding → Create thesis → View deals

2. **Document Upload Flow**
   - Upload PDF → Wait for processing → View anomalies → Generate report

3. **Deal Evaluation Flow**
   - Create deal → Upload evidence → Run judgment → Ask Parity

4. **Error Recovery Flow**
   - Upload fails → Retry → Success

---

## 📝 Notes

- All API calls use `fetchApi` helper for consistent auth headers
- Error states are handled gracefully with user-friendly messages
- Loading states provide feedback during async operations
- Optimistic updates improve perceived performance

---

**Last Updated**: February 9, 2026
