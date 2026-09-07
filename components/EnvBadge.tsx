// PAR-265: environment indicator badge for the main app.
//
// Reimplemented from admin/components/EnvBadge.tsx (PAR-181) — cannot share
// the admin component directly because they are separate Next.js apps with no
// shared component library. Visual design is identical; the env type set
// differs (admin uses prod/staging/sandbox, main app uses prod/staging/preview).
//
// Env is derived from NEXT_PUBLIC_APP_ENV (see lib/app-env.ts); set that
// var in Vercel project settings per environment — do not hardcode env strings
// in page components.

import { getAppEnv, type AppEnv } from '@/lib/app-env'

const STYLES: Record<AppEnv, { border: string; background: string; color: string; label: string }> = {
  prod:    { border: '#E24B4A44', background: '#2C1515', color: '#E24B4A', label: '● PROD' },
  staging: { border: '#1D9E7544', background: '#122117', color: '#1D9E75', label: '● STAGING' },
  preview: { border: '#C9A22744', background: '#241D0D', color: '#C9A227', label: '● PREVIEW' },
}

export function EnvBadge() {
  const env = getAppEnv()
  const s = STYLES[env]
  return (
    <span style={{
      fontFamily: "'IBM Plex Mono', monospace",
      fontSize: 10,
      fontWeight: 500,
      padding: '2px 8px',
      borderRadius: 3,
      border: `1px solid ${s.border}`,
      background: s.background,
      color: s.color,
      letterSpacing: '0.05em',
    }}>
      {s.label}
    </span>
  )
}
