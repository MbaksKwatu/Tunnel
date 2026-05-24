# Vercel environment variables (PDS frontend)

**Scope:** `ParitySME/Tunnel` — Next.js apps on Vercel. Backends run on **GCP Cloud Run** (not Render). Two Vercel projects map to prod vs staging.

---

## Infrastructure map (May 2026)

| Role | Vercel project | Production URL | Backend (`NEXT_PUBLIC_API_URL`) | Supabase |
|------|----------------|----------------|----------------------------------|----------|
| **Production** | `parityplatform` (`v0-fund-iq-1-0`) | https://parityfinance.vercel.app | `https://parity-backend-prod-121148713552.us-central1.run.app` | `ifcdbhbuucmjgtjkluna` |
| **Staging** | `parity-sme-staging` | https://parity-sme-staging.vercel.app | `https://parity-backend-121148713552.us-central1.run.app` | `kstuensfekanfberjubz` |

**GCP Cloud Run (us-central1, project `parity-491822`):**

| Service | URL |
|---------|-----|
| Backend prod | `https://parity-backend-prod-121148713552.us-central1.run.app` |
| Backend staging | `https://parity-backend-121148713552.us-central1.run.app` |
| Ingestion | `https://parity-ingestion-121148713552.us-central1.run.app` |

**Legacy Render (keep until Musa webhook migrated + 48h stable):**

| Service | URL |
|---------|-----|
| API (old prod frontend target) | `https://parity-ingestion.onrender.com` |
| API (alternate) | `https://paritytunnel-w7d2.onrender.com` |

---

## Production — `parityplatform`

Set in Vercel → **parityplatform** → Settings → Environment Variables → **Production**:

| Key | Value |
|-----|--------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://ifcdbhbuucmjgtjkluna.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon key from prod Supabase dashboard |
| `NEXT_PUBLIC_API_URL` | `https://parity-backend-prod-121148713552.us-central1.run.app` |

After any `NEXT_PUBLIC_*` change: **Deployments → Redeploy** (values are inlined at build time).

Verify:

```bash
cd Tunnel && vercel link --project parityplatform --yes
vercel env run --environment=production -- sh -c 'echo $NEXT_PUBLIC_API_URL'
```

---

## Staging — `parity-sme-staging`

Set in Vercel → **parity-sme-staging** → Settings → Environment Variables → **Production**:

| Key | Value |
|-----|--------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://kstuensfekanfberjubz.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon key from staging Supabase (or copy from `STAGING_SUPABASE_ANON_KEY`) |
| `NEXT_PUBLIC_API_URL` | `https://parity-backend-121148713552.us-central1.run.app` |

**Note:** Use `--no-sensitive` when adding `NEXT_PUBLIC_API_URL` via CLI; marking it sensitive can store an empty value in non-interactive mode.

Verify:

```bash
cd Tunnel && vercel link --project parity-sme-staging --yes
vercel env run --environment=production -- sh -c 'echo $NEXT_PUBLIC_API_URL'
```

In the browser (DevTools → Network), API calls should hit `parity-backend-…run.app`, not `localhost:8000` or Render.

---

## Musa integration

Musa partner API (not a `/webhook/musa` path):

- `POST https://parity-backend-prod-121148713552.us-central1.run.app/api/musa/sessions`
- Requires `X-API-Key` (see `backend/v1/integrations/auth.py`)

Coordinate with Musa to point their integration at the GCP prod URL. Keep Render URLs live during transition.

---

## Rollback

**Production:** set `NEXT_PUBLIC_API_URL` back to `https://parity-ingestion.onrender.com` and redeploy.

**Staging:** restore previous env or leave empty (previous state was broken).

---

## Do not change on Vercel

- `STAGING_*` server-side vars — not read by the Next.js client; used for reference or future server routes only.
- Local `Tunnel/.env.local` — dev only.

---

## Recent deploy commits

| Hash | Subject |
|------|---------|
| `c0f2539` | chore(deploy): backend Dockerfile and Cloud Build config |
| `08072e3` | docs: Vercel env handoff for PDS Tunnel frontend |
