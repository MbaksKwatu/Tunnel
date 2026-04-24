# Parity SME — FundIQ

AI-powered financial intelligence platform for investment teams. Processes PDFs, CSVs, and Excel files to extract structured deal data, run anomaly detection, and generate reports.

**Stack:** Next.js 14 · FastAPI · Supabase (PostgreSQL + Storage)

---

## Prerequisites

- Node.js 18+
- Python 3.9+
- Access to the Supabase project (get credentials from the team)

---

## Local Setup

### 1. Frontend

```bash
cd Tunnel
npm install
cp .env.local.example .env.local   # fill in values from team vault
npm run dev                         # http://localhost:3000
```

### 2. Backend

```bash
cd Tunnel/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # fill in values from team vault
python main.py                      # http://localhost:8000
```

### Environment Variables

**Frontend (`Tunnel/.env.local`)**

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon/public key |
| `NEXT_PUBLIC_API_URL` | Backend API URL (default: `http://localhost:8000`) |

**Backend (`Tunnel/backend/.env`)**

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (server-side only — never expose to frontend) |

---

## Running Tests

```bash
cd Tunnel/backend
source .venv/bin/activate
bash RUN_TESTS.sh
```

---

## Project Structure

```
Tunnel/
├── app/                    # Next.js pages
│   ├── dashboard/
│   ├── deals/
│   ├── upload/
│   ├── reports/
│   ├── connect-data/
│   ├── settings/
│   └── auth/ · login/ · onboarding/
├── components/             # React components
├── lib/                    # Supabase client, types, utilities
├── backend/
│   ├── main.py             # FastAPI entrypoint (routes to v1)
│   └── v1/
│       ├── api.py          # All API route handlers
│       ├── parsing/        # PDF, CSV, XLSX parsers
│       ├── ingestion/      # File processing pipeline
│       ├── core/           # Deal logic, anomaly detection
│       ├── analytics.py    # Analytics calculations
│       ├── ask.py          # Query engine
│       └── db/             # Database models
└── supabase/               # Schema and migrations
```

---

## API

All routes are under `/v1/`. See `backend/v1/api.py` for the full list.

Key groups:
- `/v1/deals` — CRUD for deals
- `/v1/evidence` — File upload and parsing
- `/v1/parity/judge` — Judgment engine
- `/v1/analytics` — Analytics and reporting
- `/v1/ask` — Natural language query

---

## Deployment

- **Frontend:** Vercel (auto-deploys from `main` branch of Tunnel repo)
- **Backend:** Render/Railway — root directory `backend`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Database:** Supabase (managed)

Set all environment variables in the platform dashboard before deploying.

---

## Troubleshooting

**Port conflicts**
```bash
lsof -ti:3000,8000 | xargs kill -9
```

**Missing Python packages**
```bash
cd backend && source .venv/bin/activate && pip install -r requirements.txt
```

**Supabase RLS errors** — confirm backend is using the service role key, not the anon key.
