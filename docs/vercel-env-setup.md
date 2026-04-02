# Vercel environment variables (PDS frontend)

**Scope:** `ParitySME/Tunnel` only — the Next.js app deployed as **`v0-fund-iq-1-0`** on Vercel. Backend lives on Render; Supabase is shared. Do not conflate this with other folders in the monorepo.

---

## Required variables

Set these in Vercel → **Settings** → **Environment Variables** for **Production** (and Preview/Development if you use them).

| Key | Source | Production value (PDS) |
|-----|--------|-------------------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → **Settings** → **API** → Project URL | `https://ifcdbhbuucmjgtjkluna.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Same page → **anon** `public` key (JWT, starts with `eyJ`) | Copy from dashboard (do not use service role) |
| `NEXT_PUBLIC_API_URL` | Render Parity API | `https://paritytunnel-w7d2.onrender.com` |

Wrong or missing **`NEXT_PUBLIC_SUPABASE_*`** causes **“Sign-in is taking too long”** — the browser client in `lib/supabase.ts` cannot initialize auth.

---

## Fix broken production login

1. **Supabase** — Open project **`ifcdbhbuucmjgtjkluna`** → Settings → API → copy **Project URL** and **anon public** key.
2. **Vercel** — Project **`v0-fund-iq-1-0`** → Environment Variables → set/update the three keys above for **Production**.
3. **Redeploy** — Deployments → latest → **Redeploy**. Next.js inlines `NEXT_PUBLIC_*` at **build** time; env-only changes do nothing until a new deployment runs.

---

## Do not change

- **Render:** `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` — server-side only; separate from the anon key above.
- **Local:** `ParitySME/Tunnel/.env.local` — placeholders for dev; not used by Vercel.

---

## Verify

- Open the production URL in an **incognito** window.
- **Network:** requests to **`ifcdbhbuucmjgtjkluna.supabase.co`** (auth/session) should return **200**, not hang or fail CORS.
- Sign-in should finish in a few seconds.

---

## Why builds fail without Supabase env

If `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` are missing at build time, Next.js may error (e.g. URL and key required) or ship a client that cannot authenticate.
