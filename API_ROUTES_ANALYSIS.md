# API Routes Analysis & Simplification Plan

**Date**: February 9, 2026  
**Status**: Analysis Complete - Ready for Simplification

## 📊 Current API Endpoints

### Health & Status
- `GET /` - Root health check
- `GET /health` - Detailed health check
- `GET /health/db` - Database health check

### Document Management
- `POST /parse` - Parse document (supports both file upload and URL)
- `GET /documents` - List all documents
- `GET /document/{document_id}` - Get document info
- `DELETE /document/{document_id}` - Delete document
- `POST /document/{document_id}/cancel` - Cancel processing
- `POST /document/{document_id}/retry` - Retry processing

### Document Data
- `GET /document/{document_id}/rows` - Get extracted rows
- `GET /document/{document_id}/anomalies` - Get anomalies
- `GET /api/anomalies?doc_id={id}` - **DUPLICATE** - Get anomalies (alias)
- `POST /analyze` - Re-run anomaly detection
- `POST /api/anomalies/run` - **DUPLICATE** - Re-run anomaly detection (alias)
- `POST /api/documents/{doc_id}/detect` - Unsupervised anomaly detection
- `GET /document/{document_id}/evaluate` - Calculate financial metrics
- `GET /document/{document_id}/insights` - Get insights
- `GET /document/{document_id}/report` - Generate IC report PDF
- `GET /api/report?doc_id={id}` - **DUPLICATE** - Generate IC report (alias)

### Notes
- `GET /document/{document_id}/notes` - Get document notes
- `POST /document/{document_id}/notes` - Create document note
- `POST /anomalies/{anomaly_id}/notes` - Create anomaly note
- `GET /notes/{note_id}/replies` - Get note replies

### Investees
- `POST /documents/{document_id}/set-investee` - Set investee name
- `GET /investees` - List investees
- `GET /investees/{investee_name}/full` - Get investee full context

### Dashboards
- `POST /dashboards/save` - Save dashboard
- `GET /dashboards` - List dashboards
- `GET /dashboards/{dashboard_id}` - Get dashboard

### Reports
- `GET /reports` - List reports

### Debug
- `GET /debug/logs` - Get debug logs
- `POST /cleanup/stuck-files` - Cleanup stuck files

### Parity AI Routes (from routes/)
- `POST /mutate-dashboard` - Dashboard mutation (LLM)
- `POST /api/deals` - Create deal
- `GET /api/deals` - List deals
- `GET /api/deals/{deal_id}` - Get deal
- `DELETE /api/deals/{deal_id}` - Delete deal
- `POST /api/deals/{deal_id}/evidence` - Upload evidence
- `GET /api/deals/{deal_id}/evidence` - Get evidence
- `POST /api/deals/{deal_id}/judge` - Run judgment
- `GET /api/deals/{deal_id}/judgment` - Get judgment
- `GET /api/deals/{deal_id}/conversation` - Get conversation
- `POST /api/deals/{deal_id}/ask` - Ask Parity
- `POST /api/thesis` - Create/update thesis
- `GET /api/thesis` - Get thesis
- `PUT /api/thesis` - Update thesis

---

## 🔍 Issues Identified

### 1. **Duplicate Endpoints** (High Priority)
- `/api/anomalies` vs `/document/{id}/anomalies` - Same functionality
- `/api/anomalies/run` vs `/analyze` - Same functionality  
- `/api/report` vs `/document/{id}/report` - Same functionality

### 2. **Inconsistent Naming** (Medium Priority)
- Mix of `/document/{id}/...` and `/api/...` patterns
- Some endpoints use query params, others use path params
- Inconsistent pluralization (`/documents` vs `/document/{id}`)

### 3. **Route Organization** (Medium Priority)
- Main routes in `main.py` (1000+ lines)
- Parity AI routes in separate `routes/` directory
- Could benefit from better organization

### 4. **Missing Standardization** (Low Priority)
- No consistent error response format
- No API versioning
- No rate limiting
- No request/response logging middleware

---

## ✅ Simplification Plan

### Phase 1: Remove Duplicates (Immediate)

**Action**: Remove alias endpoints, keep canonical ones

1. **Remove** `/api/anomalies` → Use `/document/{id}/anomalies`
2. **Remove** `/api/anomalies/run` → Use `/analyze`  
3. **Remove** `/api/report` → Use `/document/{id}/report`

**Impact**: 
- Reduces endpoint count by 3
- Simplifies frontend code (one way to call each endpoint)
- Easier to maintain

### Phase 2: Standardize Naming (Next)

**Action**: Use consistent REST patterns

**Proposed Structure**:
```
/documents          - List/create documents
/documents/{id}     - Get/update/delete document
/documents/{id}/rows
/documents/{id}/anomalies
/documents/{id}/analyze
/documents/{id}/evaluate
/documents/{id}/insights
/documents/{id}/report
/documents/{id}/notes
```

**Keep as-is** (already good):
- `/investees`
- `/dashboards`
- `/reports`
- `/api/deals` (Parity AI routes)

**Impact**:
- More intuitive API
- Easier to discover endpoints
- Better REST compliance

### Phase 3: Organize Routes (Future)

**Action**: Split main.py into route modules

**Structure**:
```
backend/
  routes/
    __init__.py
    health.py       - Health checks
    documents.py    - Document CRUD
    analysis.py     - Anomalies, insights, evaluation
    notes.py        - Notes management
    investees.py    - Investee management
    dashboards.py   - Dashboard management
    reports.py      - Report generation
    deals.py        - Already exists
    llm_actions.py  - Already exists
    dashboard_mutation.py - Already exists
```

---

## 🧪 Testing Plan

### Critical Endpoints to Test

1. **Document Upload Flow**
   - `POST /parse` (file upload mode)
   - `GET /documents`
   - `GET /document/{id}/rows`

2. **Anomaly Detection**
   - `POST /analyze`
   - `GET /document/{id}/anomalies`

3. **Evaluation**
   - `GET /document/{id}/evaluate`
   - `GET /document/{id}/insights`

4. **Report Generation**
   - `GET /document/{id}/report`

5. **Deal Management** (Parity AI)
   - `POST /api/deals`
   - `GET /api/deals`
   - `POST /api/deals/{id}/judge`

---

## 📝 Implementation Steps

### Step 1: Remove Duplicate Endpoints
- [ ] Remove `/api/anomalies` endpoint
- [ ] Remove `/api/anomalies/run` endpoint  
- [ ] Remove `/api/report` endpoint
- [ ] Update frontend to use canonical endpoints
- [ ] Test all affected flows

### Step 2: Update Frontend
- [ ] Search for `/api/anomalies` usage → replace with `/document/{id}/anomalies`
- [ ] Search for `/api/anomalies/run` → replace with `/analyze`
- [ ] Search for `/api/report` → replace with `/document/{id}/report`

### Step 3: Document Changes
- [ ] Update API documentation
- [ ] Add migration guide
- [ ] Update frontend API client

---

## 🎯 Expected Benefits

1. **Reduced Complexity**: 3 fewer endpoints to maintain
2. **Better Consistency**: One way to do each thing
3. **Easier Onboarding**: Clearer API structure
4. **Less Confusion**: No duplicate functionality
5. **Easier Testing**: Fewer endpoints to test

---

## ⚠️ Breaking Changes

**Note**: Removing duplicate endpoints will require frontend updates.

**Affected Files** (estimated):
- `components/AnomalyTable.tsx` - Uses `/api/anomalies`
- `components/EvaluateView.tsx` - Uses `/api/anomalies`
- `components/DataReview.tsx` - May use `/api/anomalies`
- Any other components using alias endpoints

**Migration**: Update all references before removing endpoints (or keep aliases temporarily with deprecation warnings).
