# Architecture

## System Overview

```
Browser (Next.js 14)
        │
        ▼
  FastAPI Backend  ──►  Supabase (PostgreSQL + Storage)
        │
        ▼
  Parsing Pipeline
  (PDF / CSV / XLSX)
```

## Request Flow

1. User uploads a financial document via the frontend
2. Frontend POSTs to `/v1/evidence/upload`
3. Backend stores the file in Supabase Storage
4. Parsing pipeline extracts structured rows
5. Rows are written to Supabase and linked to a deal
6. Frontend polls deal status; displays extracted data when ready

## Backend Modules

| Module | Purpose |
|--------|---------|
| `v1/api.py` | All route definitions and request handling |
| `v1/parsing/` | Format-specific parsers (PDF via pdfplumber/reportlab, CSV, XLSX via openpyxl) |
| `v1/ingestion/` | Orchestrates file intake, deduplication, status updates |
| `v1/core/` | Deal scoring, anomaly detection |
| `v1/analytics.py` | Aggregations for dashboard and reports |
| `v1/ask.py` | Natural language query layer |
| `v1/db/` | Supabase client, table models, query helpers |

## Frontend Routes

| Route | Purpose |
|-------|---------|
| `/dashboard` | Summary view of all deals |
| `/deals` | Deal list and detail |
| `/upload` | File upload flow |
| `/reports` | Analytics reports + PDF/CSV export |
| `/connect-data` | Data source connections |
| `/settings` | User and org settings |
| `/onboarding` | New user setup |

## Database

Managed by Supabase. Schema lives in `supabase/`. Migrations are in `backend/v1/migrations/`.

The backend always connects with the **service role key** to bypass Row Level Security for server-side writes. The frontend uses the **anon key** with RLS enforced.

## Deployment Topology

```
Vercel (frontend)  ──►  Render/Railway (backend)  ──►  Supabase (DB + Storage)
```

DNS, CORS origins, and `NEXT_PUBLIC_API_URL` must be updated together when changing the backend host.
