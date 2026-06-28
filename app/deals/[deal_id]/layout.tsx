'use client'

import { useParams, usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/components/AuthProvider'

const NAV_ACTIVE = [
  { label: 'Upload', href: (id: string) => `/v1/deal?deal_id=${id}`, key: 'upload' },
  { label: 'Overrides', href: (id: string) => `/deals/${id}/overrides`, key: 'overrides' },
  { label: 'Review', href: (id: string) => `/deals/${id}/review`, key: 'review' },
  { label: 'Export', href: (id: string) => `/deals/${id}/export`, key: 'export' },
]

const NAV_FUTURE = ['Benchmark', 'Monitor', 'Registry']

export default function DealLayout({ children }: { children: React.ReactNode }) {
  const params = useParams()
  const pathname = usePathname()
  const router = useRouter()
  const { user, signOut } = useAuth()

  const dealId = params?.deal_id as string | undefined
  const email = user?.email ?? ''
  const initials = email
    ? email.slice(0, 2).toUpperCase()
    : 'AN'

  const isActive = (key: string) => {
    if (!dealId) return false
    if (key === 'upload') return pathname === '/v1/deal' || pathname.startsWith('/v1/deal')
    return pathname.includes(`/${key}`)
  }

  const handleSignOut = async () => {
    await signOut()
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#080C18', color: '#E2E8F0', fontFamily: "'IBM Plex Sans', sans-serif" }}>
      {/* Sidebar */}
      <aside style={{
        width: 220,
        background: '#0D1220',
        borderRight: '1px solid #1E2A3A',
        display: 'flex',
        flexDirection: 'column',
        padding: '24px 0',
        position: 'fixed',
        top: 0,
        left: 0,
        bottom: 0,
        zIndex: 50,
      }}>
        {/* Logo */}
        <div style={{ padding: '0 20px 24px', borderBottom: '1px solid #1E2A3A' }}>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, letterSpacing: '0.1em', fontWeight: 700 }}>
            <span style={{ color: '#14B8A6' }}>P/</span> <span style={{ color: '#fff' }}>PARITY</span>
          </div>
          <div style={{ fontSize: 11, color: '#4A5568', marginTop: 2, letterSpacing: '0.08em' }}>
            INTELLIGENCE INFRASTRUCTURE
          </div>
        </div>

        {/* Active nav */}
        <nav style={{ flex: 1, padding: '16px 0' }}>
          <div style={{ padding: '0 12px 8px', fontSize: 10, color: '#4A5568', letterSpacing: '0.12em', fontWeight: 600 }}>
            DEAL WORKFLOW
          </div>
          {NAV_ACTIVE.map((item) => {
            const active = isActive(item.key)
            return (
              <button
                key={item.key}
                onClick={() => dealId && router.push(item.href(dealId))}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  width: '100%',
                  padding: '10px 20px',
                  background: active ? 'rgba(20,184,166,0.12)' : 'transparent',
                  borderLeft: active ? '2px solid #14B8A6' : '2px solid transparent',
                  border: 'none',
                  color: active ? '#5EEAD4' : '#64748B',
                  fontSize: 13,
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s',
                  letterSpacing: '0.01em',
                }}
              >
                {item.label}
              </button>
            )
          })}

          <div style={{ padding: '16px 12px 8px', fontSize: 10, color: '#2D3748', letterSpacing: '0.12em', fontWeight: 600, marginTop: 8 }}>
            COMING SOON
          </div>
          {NAV_FUTURE.map((label) => (
            <div
              key={label}
              style={{
                padding: '10px 20px',
                color: '#2D3748',
                fontSize: 13,
                letterSpacing: '0.01em',
                borderLeft: '2px solid transparent',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              {label}
              <span style={{ fontSize: 9, background: '#1A2235', color: '#374151', padding: '1px 5px', borderRadius: 3, letterSpacing: '0.05em' }}>
                SOON
              </span>
            </div>
          ))}
        </nav>

        {/* User chip + sign out */}
        <div style={{ padding: '16px 20px', borderTop: '1px solid #1E2A3A' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <div style={{
              width: 30,
              height: 30,
              borderRadius: '50%',
              background: 'rgba(20,184,166,0.2)',
              border: '1px solid rgba(20,184,166,0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 11,
              fontWeight: 700,
              color: '#5EEAD4',
              fontFamily: "'IBM Plex Mono', monospace",
              flexShrink: 0,
            }}>
              {initials}
            </div>
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontSize: 12, color: '#94A3B8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {email || 'analyst'}
              </div>
            </div>
          </div>
          <button
            onClick={handleSignOut}
            style={{
              width: '100%',
              padding: '7px 0',
              background: 'transparent',
              border: '1px solid #1E2A3A',
              borderRadius: 4,
              color: '#4A5568',
              fontSize: 12,
              fontFamily: "'IBM Plex Sans', sans-serif",
              cursor: 'pointer',
              letterSpacing: '0.03em',
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ marginLeft: 220, flex: 1, minHeight: '100vh' }}>
        {children}
      </main>
    </div>
  )
}
