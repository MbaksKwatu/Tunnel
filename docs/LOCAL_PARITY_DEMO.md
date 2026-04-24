# Parity — Local Ingestion via ngrok (Demo Setup)

## Goal

Run `parity-ingestion` locally and expose it via ngrok so the backend can call it as a public API.

---

## Step 1 — Verify ngrok is installed

Run:

```bash
ngrok version
```

If it returns a version, ngrok is installed.

If not, install via:

```bash
brew install ngrok/ngrok/ngrok
```

---

## Step 2 — Authenticate ngrok

Get your auth token from: [https://dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)

Then run:

```bash
ngrok config add-authtoken <YOUR_TOKEN>
```

---

## Step 3 — Run ingestion service locally

```bash
cd /Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel/parity-ingestion
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl -sS http://localhost:8000/
```

Expected:

```json
{"status":"ok","service":"parity-ingestion"}
```

---

## Step 4 — Start ngrok tunnel

Open a new terminal:

```bash
ngrok http 8000
```

You will get a URL like:

```bash
https://abc123.ngrok-free.app
```

---

## Step 5 — Configure backend

Set environment variable:

```bash
PARITY_INGESTION_URL=https://abc123.ngrok-free.app
```

Restart backend server.

---

## Step 6 — Verify end-to-end

Test flow:

1. Upload a statement (start with June)
2. Confirm:

   * ingestion completes
   * no timeout
   * rows returned

---

## Notes

* ngrok URL changes on restart (free tier)
* Do NOT hardcode URL — always use env variable
* Keep ngrok + ingestion running during demo
* Keep laptop awake (use `caffeinate`)

---

## Success Criteria

* Upload completes in < 60 seconds
* No “processing timeout”
* Transactions visible in UI
* April file processes without failure

---

---

# Parity — Backend Wiring for ngrok (Critical Fixes)

## Goal

Ensure backend correctly connects to local ingestion via ngrok with proper ports and environment configuration.

---

## Step 1 — Run ingestion (port 8000)

```bash
cd /Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel/parity-ingestion
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Step 2 — Validate ingestion is alive (MANDATORY)

```bash
curl http://localhost:8000/
```

Expected response:

```json
{"status": "ok", "service": "parity-ingestion"}
```

Do NOT proceed if this fails.

---

## Step 3 — Start ngrok (new terminal)

```bash
ngrok http 8000
```

Copy HTTPS URL:

```bash
https://xxxx.ngrok-free.app
```

Rules:

* No trailing slash
* Do NOT append endpoints

---

## Step 4 — Run backend on DIFFERENT port (8001)

```bash
cd /Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel/backend
PARITY_INGESTION_URL=https://xxxx.ngrok-free.app CORS_ORIGINS=http://localhost:3000 python3 -m uvicorn main:app --host 0.0.0.0 --port 8001
```

This ensures:

* correct env injection
* no port conflict

---

## Step 5 — Verify backend wiring

Upload flow should:

* hit ngrok URL
* forward to local ingestion
* return parsed transactions

---

## Common Failure Cases

### 1. Port conflict

Symptom:

* server fails to start

Fix:

* ingestion = 8000
* backend = 8001

---

### 2. Wrong env variable

Symptom:

* ingestion never called

Fix:

* must use PARITY_INGESTION_URL

---

### 3. Trailing slash in URL

Symptom:

* double slash in request

Fix:

* remove trailing slash

---

### 4. ngrok restarted

Symptom:

* requests fail suddenly

Fix:

* update URL and restart backend

---

## Success Criteria

* curl localhost:8000 works
* ngrok URL accessible
* backend starts on 8001
* upload completes without timeout

---

---

# Parity — Local Demo Setup (No ngrok)

## Goal

Run the full Parity pipeline locally (ingestion + backend + frontend) and access via browser for a complete demo.

---

## Architecture (Local Only)

* Ingestion service → port 8000
* Backend API → port 8001
* Frontend UI → port 3000 (or configured port)

All communication between services happens via localhost (note: Supabase is still used for auth over the internet).

---

## Step 1 — Start ingestion service

```bash
cd /Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel/parity-ingestion
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/
```

Expected:

```json
{"status": "ok", "service": "parity-ingestion"}
```

---

## Step 2 — Start backend (connect to local ingestion)

```bash
cd /Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel/backend
PARITY_INGESTION_URL=http://localhost:8000 CORS_ORIGINS=http://localhost:3000 python3 -m uvicorn main:app --host 0.0.0.0 --port 8001
```

Notes:

* Must use `PARITY_INGESTION_URL`
* No trailing slash
* Backend must NOT run on 8000

---

## Step 3 — Start frontend

```bash
cd /Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel
npm run dev
```

If env needed:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8001
```

---

## Step 4 — Open application

In browser:

```
http://localhost:3000
```

---

## Step 5 — Run demo flow

1. Upload bank statement (start with June)
2. Click analyze
3. Observe processing
4. Review:

   * transactions
   * classification
   * reconciliation
   * insight
   * snapshot

---

## Step 6 — Validate outputs

Ensure:

* No timeout errors
* Transactions appear
* Reconciliation block visible
* Insight sentence present
* Snapshot generated

---

## Common Issues

### Backend not calling ingestion

* Check `PARITY_INGESTION_URL`
* Ensure ingestion is running

### Port conflict

* ingestion → 8000
* backend → 8001

### Frontend not loading data

* Check `NEXT_PUBLIC_API_URL`

---

## Demo Safety Checklist

* Run `caffeinate -dimsu`
* Keep laptop plugged in
* Do not restart services mid-demo
* Pre-test at least one full successful upload

---

## Success Criteria

* Full upload → processing → snapshot works locally
* Core parsing runs on localhost; only Supabase auth is remote
* Stable demo environment

---

---

# Cursor Instructions — Full Local UI Demo (Ask Questions Enabled)

## Objective

Set up and validate a **full browser-based Parity demo locally** (frontend + backend + ingestion + Supabase auth).

Cursor should:

* execute steps sequentially
* validate each step
* ASK QUESTIONS if anything is unclear or fails

---

## Step 1 — Validate Supabase Configuration

Check `.env.local` exists at:

```
ParitySME/Tunnel/.env.local
```

If NOT present, create it and ALSO ensure it is gitignored:

```bash
# add to .gitignore if missing
echo ".env.local" >> .gitignore
```

Use placeholders in this document (real values go ONLY in your local file `ParitySME/Tunnel/.env.local`):

```env
NEXT_PUBLIC_SUPABASE_URL=<from Supabase Dashboard → Settings → API>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon public key>
NEXT_PUBLIC_API_URL=http://localhost:8001
```

Notes:

* Do NOT commit real keys to this document
* Put real values only in `ParitySME/Tunnel/.env.local` (gitignored)
* Keys can be rotated later

---

## Step 2 — Start ingestion service (port 8000)

```bash
cd /Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel/parity-ingestion
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Validate:

```bash
curl http://localhost:8000/
```

Expected:

```json
{"status": "ok", "service": "parity-ingestion"}
```

### If failure:

Ask:

* "What error do you see when starting ingestion?"

---

## Step 3 — Start backend (port 8001)

```bash
cd /Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel/backend
PARITY_INGESTION_URL=http://localhost:8000 CORS_ORIGINS=http://localhost:3000 python3 -m uvicorn main:app --host 0.0.0.0 --port 8001
```

Validate:

```bash
curl http://localhost:8001/
```

### If failure:

Ask:

* "Is port 8001 already in use?"

---

## Step 4 — Start frontend (port 3000)

```bash
cd /Users/mbakswatu/Desktop/Fintelligence/ParitySME/Tunnel
npm run dev
```

Validate in browser:

```
http://localhost:3000
```

---

## Step 5 — Authentication flow

Open:

```
http://localhost:3000/login
```

### If login fails:

Ask:

* "Are Supabase env variables correct?"
* "Is the project active and accessible?"

---

## Step 6 — Full demo flow

Open:

```
http://localhost:3000/v1/deal
```

Execute:

1. Create deal
2. Upload PDF
3. Click analyze

Validate:

* ingestion triggered
* processing completes
* transactions appear
* reconciliation appears
* insight appears
* snapshot generated

---

## Step 7 — Failure handling

If ANY step fails, Cursor must:

1. Stop execution
2. Identify failing layer:

   * frontend
   * backend
   * ingestion
   * Supabase
3. Ask a targeted question
4. Suggest ONE fix only

---

## Rules for Cursor

* Do NOT introduce ngrok
* Do NOT suggest Railway
* Do NOT refactor code
* Focus only on getting demo working

---

## Success Criteria

* User can access UI in browser
* Login works
* Upload works
* Processing completes
* Snapshot visible

---
