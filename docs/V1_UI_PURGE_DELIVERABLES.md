# V1 UI Purge + Auth Safety — Deliverables

## 1. Deleted/Disabled UI Routes

All legacy routes now **redirect** to `/v1/deal` (no 404s):

| Route | Action |
|-------|--------|
| `/deals` | Redirect → `/v1/deal` |
| `/deals/new` | Redirect → `/v1/deal` |
| `/deals/[deal_id]` | Redirect → `/v1/deal` |
| `/deals/[deal_id]/edit` | Redirect → `/v1/deal` |
| `/dashboard` | Redirect → `/v1/deal` |
| `/reports` | Redirect → `/v1/deal` |
| `/actions` | Redirect → `/v1/deal` |
| `/connect-data` | Redirect → `/v1/deal` |
| `/upload` | Redirect → `/v1/deal` |
| `/onboarding/thesis` | Redirect → `/v1/deal` |
| `/settings/thesis` | Redirect → `/v1/deal` |

**Kept (active):**
- `/` → redirects to `/v1/deal`
- `/v1/deal` → main analyst entry point
- `/login` → auth (redirects to `/v1/deal` after sign-in)
- `/auth/callback` → OAuth/magic link callback
- `/auth/reset-password` → password reset flow

---

## 2. Confirmation: No UI Route Except /v1/deal (+ /auth)

- **Analyst entry point:** `/v1/deal` only
- **Auth routes:** `/login`, `/auth/callback`, `/auth/reset-password` (all land on `/v1/deal` after success)
- **No** legacy screens: no "Judged", "Draft", "Thesis", "Reports", "Dashboard" surfaces
- **No** UI text mentioning judgment, scoring, thesis, reports

---

## 3. Auth Decision: **SAFE** (with modifications)

**Original state:** NOT SAFE
- `AuthProvider` redirected to `/onboarding/thesis` or `/deals` on sign-in
- Queried `thesis` table (legacy)
- Navigation showed "Deals", "New Deal", "Investment Thesis"

**Changes made:**
- `AuthProvider` (lines 61–80): Removed thesis check; now redirects to `/v1/deal` on `SIGNED_IN`
- `auth/callback/page.tsx`: Removed thesis check; redirects to `/v1/deal`
- `Navigation.tsx`: Replaced "Deals" / "New Deal" with single "Deal Analysis (v1)" → `/v1/deal`
- Removed "Investment Thesis" from user dropdown

**Result:** Auth is now v1-only. Sign-in lands directly on `/v1/deal`. No legacy nav or flows.

**Files modified:**
- `components/AuthProvider.tsx`
- `app/auth/callback/page.tsx`
- `components/Navigation.tsx`
- `components/Layout/Sidebar.tsx`

---

## 4. Route/Endpoint Integrity Check

**Location:** `lib/api.ts`

- `fetchApi()` now **throws** if `endpoint` does not start with `/v1`
- Error: `Legacy API call blocked: "{endpoint}". All API calls must use /v1/* routes.`
- Ensures no accidental calls to `/api/*`, `/documents`, `/parse`, etc.

---

## 5. Debug Instrumentation Removed

- `components/DocumentList.tsx` — agent log fetch calls removed
- `lib/supabase.ts` — agent log fetch calls removed
- `components/DealDetail.tsx` — ingest() calls removed
- `components/Login.tsx` — ingest() calls removed

---

## 6. Summary

| Item | Status |
|------|--------|
| Legacy UI routes purged | ✅ All redirect to `/v1/deal` |
| Sidebar: Deal Analysis (v1) only | ✅ |
| Navigation: Deal Analysis (v1) only | ✅ |
| Auth redirects to `/v1/deal` | ✅ |
| Thesis check removed | ✅ |
| fetchApi guard | ✅ Throws on non-/v1 |
| Debug instrumentation removed | ✅ |
