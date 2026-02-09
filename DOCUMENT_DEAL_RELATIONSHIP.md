# Document Upload vs Deal Management - Relationship Analysis

**Date**: February 9, 2026  
**Status**: Analysis Complete - Improvements Needed

## 🔍 Current Relationship

### Database Schema

**Evidence Table**:
```sql
CREATE TABLE evidence (
    id TEXT PRIMARY KEY,
    deal_id TEXT REFERENCES deals(id) ON DELETE CASCADE,
    document_id TEXT REFERENCES documents(id),  -- ⚠️ NULLABLE - Currently not used!
    evidence_type TEXT NOT NULL,
    extracted_data JSONB,
    confidence_score FLOAT DEFAULT 0.7,
    uploaded_at TIMESTAMP DEFAULT NOW()
);
```

**Key Finding**: 
- ✅ Evidence table **has** `document_id` field (can link to documents)
- ❌ Evidence upload **doesn't** actually process documents
- ❌ Evidence upload **doesn't** link to document records
- ❌ Documents uploaded standalone **aren't** linked to deals

---

## 📊 Current Flow (Disconnected)

### Flow 1: Standalone Document Upload
```
1. User goes to /upload
2. Uploads file → POST /parse
3. Document processed → Stored in documents table
4. User can view document → /document/{id}
5. ❌ NO CONNECTION TO DEALS
```

### Flow 2: Deal Evidence Upload (Incomplete)
```
1. User creates deal → POST /api/deals
2. User uploads evidence → POST /api/deals/{id}/evidence
3. File metadata stored → Evidence record created
4. ❌ Document NOT processed/parsed
5. ❌ document_id field is NULL
6. ❌ No anomaly detection
7. ❌ No insights generated
```

---

## 🎯 Ideal Flow (Your Vision)

```
1. ✅ User creates account
2. ✅ User sets up thesis (or uses default)
3. ✅ User creates a deal
4. ⚠️  User adds evidence (documents) → NEEDS IMPROVEMENT
5. ✅ User gets judgment
6. ✅ User engages Ask Parity
7. ✅ User checks dashboard (investees, dashboards, reports)
```

---

## ⚠️ Current Problems

### Problem 1: Evidence Upload Doesn't Process Documents
**Current Code** (`backend/routes/deals.py:342-395`):
```python
@router.post("/deals/{deal_id}/evidence")
async def upload_evidence(...):
    # Just stores metadata, doesn't parse!
    evidence_data = {
        'deal_id': deal_id,
        'evidence_type': evidence_type,
        'extracted_data': {
            'filename': file.filename,
            'file_type': file_type,
            'file_size': len(file_content)
        },
        # document_id is NULL!
    }
```

**What's Missing**:
- ❌ No document parsing
- ❌ No anomaly detection
- ❌ No insights generation
- ❌ document_id remains NULL

### Problem 2: Standalone Documents Can't Link to Deals
**Current State**:
- Documents uploaded via `/upload` are standalone
- No way to link existing document to a deal
- No UI to select document as evidence

### Problem 3: Two Separate Upload Flows
- `/upload` page → Standalone documents
- Deal detail page → Evidence upload (incomplete)
- **Confusing for users!**

---

## ✅ Proposed Solution

### Option A: Enhance Evidence Upload (Recommended)

**Make evidence upload process documents**:

```python
@router.post("/deals/{deal_id}/evidence")
async def upload_evidence(...):
    # 1. Upload and parse document (like /parse endpoint)
    document_id = str(uuid.uuid4())
    # ... parse file ...
    
    # 2. Create document record
    storage.store_document({
        'id': document_id,
        'user_id': user_id,
        'file_name': file.filename,
        'file_type': file_type,
        'status': 'completed',
        # ... other fields ...
    })
    
    # 3. Process document (anomalies, insights)
    rows = await parser.parse(...)
    storage.store_rows(document_id, rows)
    anomalies = anomaly_detector.detect_all(rows)
    storage.store_anomalies(document_id, anomalies)
    
    # 4. Create evidence record WITH document_id
    evidence_data = {
        'id': str(uuid.uuid4()),
        'deal_id': deal_id,
        'document_id': document_id,  # ✅ NOW LINKED!
        'evidence_type': evidence_type,
        'extracted_data': {
            'rows_count': len(rows),
            'anomalies_count': len(anomalies),
            # ... other metadata ...
        }
    }
    
    return {"evidence": evidence, "document_id": document_id}
```

**Benefits**:
- ✅ Evidence upload processes documents
- ✅ Documents linked to deals
- ✅ Anomaly detection works
- ✅ Judgment engine can use document data

### Option B: Link Existing Documents

**Add endpoint to link existing document to deal**:

```python
@router.post("/deals/{deal_id}/evidence/link")
async def link_document_as_evidence(
    deal_id: str,
    document_id: str,
    evidence_type: str
):
    # Verify document exists and belongs to user
    doc = storage.get_document(document_id)
    
    # Create evidence record linking to document
    evidence_data = {
        'deal_id': deal_id,
        'document_id': document_id,  # ✅ LINKED!
        'evidence_type': evidence_type,
        'extracted_data': {
            'rows_count': doc.get('rows_count'),
            'anomalies_count': doc.get('anomalies_count'),
        }
    }
    
    return {"evidence": evidence}
```

**Benefits**:
- ✅ Can reuse existing documents
- ✅ No duplicate processing
- ✅ Flexible workflow

### Option C: Unified Upload Flow (Best UX)

**Single upload component that works for both**:

```typescript
// FileUpload component with deal context
<FileUpload 
  userId={userId}
  dealId={dealId}  // Optional - if provided, uploads as evidence
  onUploadComplete={handleComplete}
/>
```

**Flow**:
- If `dealId` provided → Upload as evidence, process, link to deal
- If no `dealId` → Upload as standalone document

---

## 🔄 Recommended Implementation Plan

### Phase 1: Enhance Evidence Upload (Immediate)
1. ✅ Update `POST /api/deals/{id}/evidence` to process documents
2. ✅ Link document_id in evidence record
3. ✅ Run anomaly detection
4. ✅ Generate insights

### Phase 2: Link Existing Documents (Next)
1. ✅ Add `POST /api/deals/{id}/evidence/link` endpoint
2. ✅ Add UI to select existing documents
3. ✅ Allow users to choose: upload new or link existing

### Phase 3: Unified Flow (Future)
1. ✅ Update FileUpload component to support deal context
2. ✅ Update navigation flow
3. ✅ Remove standalone upload page (or make it optional)

---

## 📋 Updated Ideal Flow (With Improvements)

```
1. ✅ User creates account
2. ✅ User sets up thesis (or uses default)
3. ✅ User creates a deal
4. ✅ User adds evidence:
   a. Option A: Upload new document → Processes → Links to deal
   b. Option B: Link existing document → Links to deal
5. ✅ User gets judgment (uses document data from evidence)
6. ✅ User engages Ask Parity (can reference document insights)
7. ✅ User checks dashboard:
   - Investees: Grouped by investee_name from documents
   - Dashboards: Based on document data
   - Reports: Generated from document insights
```

---

## 🎯 Key Conditions & Relationships

### When Documents Link to Deals:
- ✅ Evidence upload processes document → Creates document record → Links via evidence.document_id
- ✅ Judgment engine can access document data via evidence
- ✅ Ask Parity can reference document insights
- ✅ Dashboard can show deal-related documents

### When Documents Are Standalone:
- ✅ User uploads via /upload page
- ✅ Document processed normally
- ✅ Can later be linked to deal via link endpoint
- ✅ Useful for bulk uploads or pre-processing

### Judgment Engine Usage:
- ✅ Currently uses evidence.evidence_type (just metadata)
- ⚠️ Should use evidence.document_id to get actual data
- ⚠️ Should use document anomalies/insights for scoring

---

## 🚀 Next Steps

1. **Immediate**: Enhance evidence upload endpoint
2. **Short-term**: Add link existing document feature
3. **Long-term**: Unified upload flow

**Priority**: HIGH - This is a core workflow gap!
