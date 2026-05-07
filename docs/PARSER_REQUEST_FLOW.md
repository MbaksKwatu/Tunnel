# Parser Request Flow

## Overview

When a user uploads a bank statement in a format Parity doesn't yet support, the system
detects the failure, surfaces a clear error, and routes the request to a parser-request
queue. You receive an email with all the context needed to build a new extractor.

---

## User Journey

```
1. User uploads NCBA (or any unsupported) bank statement
        ↓
2. parity-ingestion router returns UNSUPPORTED_FORMAT (HTTP 415)
        ↓
3. backend/v1/ingestion/service.py catches InvalidSchemaError
   → sets error_type = "InvalidSchemaError"
   → sets next_action = "request_parser"
        ↓
4. Frontend polls /v1/documents/{id}/status
   → detects error_type === "InvalidSchemaError" + message includes "not recognised"
        ↓
5a. Modal pops up automatically on the deal page
    → User fills bank name, country, account type, notes
    → On submit:
        - Row inserted into pds_parser_requests (Supabase)
        - POST /api/request-parser (email notification)
        ↓
    Confirmation: "We've logged [bank] for the engineering queue"

5b. FileRow shows amber "NO PARSER" badge + "Request parser →" inline button
    (same modal opens on click)

5c. Sidebar has 🔧 "Request Parser" link → /parsers/request
    (standalone page with file upload for attaching a sample statement)
```

---

## Email Notifications

### To kwatukham@gmail.com
- Subject: `🔧 Parser Request: [Bank Name]`
- Contains: bank name, country, account type, deal ID, document ID, filename, notes
- Attachment: sample PDF (when submitted via /parsers/request page)

### To requester (when contact email provided)
- Subject: `Parser Request Received — Parity`
- Confirms turnaround of 4–7 hours

---

## Environment Variables

Add to `.env.local` and Vercel:

```bash
RESEND_API_KEY=re_xxxxxxxxxxxx   # From https://resend.com/api-keys
```

---

## Building a New Parser (Your Process)

When you receive a parser request email:

1. **Download the PDF** (attached, or fetch from Supabase by document_id)
2. **Save sample**: `parity-ingestion/fixtures/[bank_name]_sample.pdf`
3. **Build extractor** — use `equity_extractor.py` as the template:
   ```bash
   # Prompt for Claude Code:
   # Build extractor for [Bank Name] following equity_extractor.py pattern.
   # Sample: fixtures/[bank_name]_sample.pdf
   # Add tests. Register in router.py. Deploy when passing.
   ```
4. **Register in router**: `parity-ingestion/app/extractors/router.py`
   - Add `detect_[bank]` and `extract_[bank]_pdf` to the detection chain
5. **Add tests**: `parity-ingestion/tests/test_[bank]_extractor.py`
6. **Deploy**:
   ```bash
   gcloud run deploy parity-ingestion --source .
   ```
7. **Email requester**: "Your parser is ready — please re-upload your statement"

---

## File Locations

| File | Purpose |
|------|---------|
| `app/parsers/request/page.tsx` | Standalone parser request page with file upload |
| `app/api/request-parser/route.ts` | Next.js API route — sends email via Resend |
| `app/v1/deal/page.tsx` | Deal page — modal + inline FileRow CTA |
| `backend/v1/ingestion/service.py` | Sets `error_type="InvalidSchemaError"` for unsupported formats |
| `parity-ingestion/app/extractors/router.py` | Bank format detection + routing |
| `parity-ingestion/app/extractors/` | Individual extractor files (one per bank) |

---

## Supported Formats (as of May 2026)

KCB · KCB Online · Equity Bank · Equity CLMS · NCBA · ABSA · Co-op · M-Pesa (CSV + PDF) · Stanbic · SCB

---

## Supabase Table: `pds_parser_requests`

```sql
create table public.pds_parser_requests (
  id            uuid primary key default gen_random_uuid(),
  deal_id       text,
  document_id   text,
  original_filename text,
  bank_name     text not null,
  country       text,
  account_type  text,
  notes         text,
  error_type    text,
  error_message text,
  created_at    timestamptz default now()
);
-- RLS: authenticated users can insert + select their own rows
```
