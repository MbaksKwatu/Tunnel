// PAR-265: single source of truth for which deployment environment this
// instance of the main app is running in.
//
// The admin app (PAR-181) derives its env from which Supabase project an API
// route connects to — that pattern is appropriate there because the admin has
// three separate DB projects. The main app has one DB per deployment, so env
// is a build-time property of the deployment itself, not the DB connection.
//
// NEXT_PUBLIC_APP_ENV must be set in Vercel project settings:
//   Production environment  → "prod"
//   Preview environment     → "preview"
//   Staging branch deploy   → "staging"
// Local dev falls back to "preview" so the badge is always visible.

export type AppEnv = 'prod' | 'staging' | 'preview'

export function getAppEnv(): AppEnv {
  const raw = process.env.NEXT_PUBLIC_APP_ENV
  if (raw === 'prod' || raw === 'staging' || raw === 'preview') return raw
  return 'preview'
}
