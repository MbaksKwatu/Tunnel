'use client'

import { useRouter } from 'next/navigation'
import { createBrowserClient } from '@/lib/supabase'
import { ThemeToggle } from '@/components/ThemeToggle'

// Account-level sidebar (no deal context): Dashboard, Deals, Bank Parsers.
// Shared by /deals and /parsers so the nav stays identical between them.
export type AccountNavItem = 'dashboard' | 'parsers'

const navBtn = (active: boolean): React.CSSProperties => ({
  display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '9px 16px',
  background: active ? 'rgba(20,184,166,0.1)' : 'transparent',
  borderLeft: `2px solid ${active ? 'var(--accent)' : 'transparent'}`,
  border: 'none', color: active ? 'var(--accent)' : 'var(--t1)', fontSize: 13, cursor: 'pointer', textAlign: 'left',
  fontFamily: "'IBM Plex Sans', sans-serif",
})
const tag: React.CSSProperties = { fontSize: 10, color: 'var(--t2)', fontFamily: "'IBM Plex Mono', monospace" }

export function AccountSidebar({ active, email, dealCount }: { active: AccountNavItem; email: string; dealCount?: number }) {
  const router = useRouter()
  const initials = email ? email.slice(0, 2).toUpperCase() : 'AN'
  return (
    <aside style={{ width: 200, background: 'var(--s1)', borderRight: '1px solid var(--s3)', display: 'flex', flexDirection: 'column', padding: '20px 0', position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 50 }}>
      <div style={{ padding: '0 16px 16px', borderBottom: '1px solid var(--s3)' }}>
        <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, fontWeight: 700, letterSpacing: '0.08em' }}>
          <span style={{ color: 'var(--accent)' }}>P/</span> <span style={{ color: '#fff' }}>PARITY</span><span style={{ fontSize: 9, verticalAlign: 'super', color: 'var(--t1)' }}>v2.0</span>
        </div>
        <div style={{ fontSize: 9, color: 'var(--t2)', marginTop: 4, letterSpacing: '0.12em' }}>DETERMINISTIC</div>
      </div>
      {email && (
        <div style={{ margin: '10px 16px', background: 'var(--s1)', border: '1px solid var(--b1)', borderRadius: 4, padding: '4px 8px', fontSize: 10, color: 'var(--t1)', display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontWeight: 700, color: 'var(--t1)' }}>{initials}</span>
          <span>PARITY DEMO</span>
        </div>
      )}
      <nav style={{ flex: 1, padding: '8px 0' }}>
        <div style={{ padding: '6px 16px', fontSize: 9, color: 'var(--t2)', letterSpacing: '0.12em', fontWeight: 600 }}>OPERATIONS</div>
        <button onClick={() => router.push('/deals')} style={navBtn(active === 'dashboard')}>
          Dashboard <span style={tag}>SYS</span>
        </button>
        <button onClick={() => router.push('/deals')} style={navBtn(false)}>
          Deals {dealCount !== undefined && <span style={tag}>{String(dealCount).padStart(2, '0')}</span>}
        </button>
        <button onClick={() => router.push('/parsers')} style={navBtn(active === 'parsers')}>
          Bank Parsers
        </button>
        <div style={{ padding: '12px 16px 6px', fontSize: 9, color: 'var(--t2)', letterSpacing: '0.12em', fontWeight: 600, marginTop: 4 }}>INTELLIGENCE</div>
        <div style={{ padding: '9px 16px', color: 'var(--t2)', fontSize: 13 }}>Parity Review</div>
        <div style={{ padding: '9px 16px', color: 'var(--t2)', fontSize: 13 }}>Benchmarks</div>
      </nav>
      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--s3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ fontSize: 10, color: 'var(--t2)', fontFamily: "'IBM Plex Mono', monospace", overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{email}</div>
          <ThemeToggle />
        </div>
        <button
          onClick={async () => { const sb = createBrowserClient(); if (sb) await sb.auth.signOut(); router.push('/login') }}
          style={{ width: '100%', padding: '6px 0', background: 'transparent', border: '1px solid var(--s3)', borderRadius: 4, color: 'var(--t2)', fontSize: 12, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
        >Sign out</button>
      </div>
    </aside>
  )
}
