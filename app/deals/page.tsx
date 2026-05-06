'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createBrowserClient } from '@/lib/supabase'
import { listDeals, DealListItem } from '@/lib/v1-api'

function statusDotColor(status: string) {
  const s = status.toLowerCase()
  if (s.includes('review')) return '#F59E0B'
  if (s.includes('flag')) return '#EF4444'
  if (s.includes('classif') || s.includes('clean')) return '#4ADE80'
  if (s.includes('upload') || s.includes('process')) return '#818CF8'
  return '#374151'
}

export default function DashboardPage() {
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [deals, setDeals] = useState<DealListItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const supabase = createBrowserClient()
    if (!supabase) { router.replace('/login'); return }
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) { router.replace('/login'); return }
      setUser(session.user)
      try {
        const result = await listDeals(session.user.id)
        setDeals(result.deals)
      } catch { /* ignore */ }
      setLoading(false)
    })
  }, [router])

  const email = user?.email ?? ''
  const initials = email ? email.slice(0, 2).toUpperCase() : 'AN'
  const activeDeals = deals.length

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#080C18' }}>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <div style={{ width: 28, height: 28, borderRadius: '50%', borderTop: '2px solid #6366F1', borderRight: '2px solid transparent', animation: 'spin 0.8s linear infinite' }} />
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: '#080C18', display: 'flex', fontFamily: "'IBM Plex Sans', sans-serif", color: '#E2E8F0' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* Sidebar */}
      <aside style={{ width: 200, background: '#0A0F1E', borderRight: '1px solid #1A2235', display: 'flex', flexDirection: 'column', padding: '20px 0', position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 50 }}>
        <div style={{ padding: '0 16px 16px', borderBottom: '1px solid #1A2235' }}>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, color: '#6366F1', fontWeight: 700, letterSpacing: '0.08em' }}>
            P/ PARITY<span style={{ fontSize: 9, verticalAlign: 'super', color: '#4A5568' }}>v2.0</span>
          </div>
          <div style={{ fontSize: 9, color: '#2D3748', marginTop: 4, letterSpacing: '0.12em' }}>DETERMINISTIC</div>
        </div>
        {email && (
          <div style={{ margin: '10px 16px', background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 4, padding: '4px 8px', fontSize: 10, color: '#4A5568', display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ fontWeight: 700, color: '#64748B' }}>{initials}</span>
            <span>ANALYST</span>
          </div>
        )}
        <nav style={{ flex: 1, padding: '8px 0' }}>
          <div style={{ padding: '6px 16px', fontSize: 9, color: '#2D3748', letterSpacing: '0.12em', fontWeight: 600 }}>OPERATIONS</div>
          <button onClick={() => {}} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '9px 16px', background: 'rgba(99,102,241,0.1)', borderLeft: '2px solid #6366F1', border: 'none', color: '#A5B4FC', fontSize: 13, cursor: 'pointer', textAlign: 'left', fontFamily: "'IBM Plex Sans', sans-serif" }}>
            Dashboard <span style={{ fontSize: 10, color: '#374151', fontFamily: "'IBM Plex Mono', monospace" }}>SYS</span>
          </button>
          <button onClick={() => {}} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '9px 16px', background: 'transparent', borderLeft: '2px solid transparent', border: 'none', color: '#4A5568', fontSize: 13, cursor: 'pointer', textAlign: 'left', fontFamily: "'IBM Plex Sans', sans-serif" }}>
            Deals <span style={{ fontSize: 10, color: '#374151', fontFamily: "'IBM Plex Mono', monospace" }}>{String(activeDeals).padStart(2, '0')}</span>
          </button>
          <div style={{ padding: '9px 16px', color: '#2D3748', fontSize: 13, borderLeft: '2px solid transparent', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            Portfolio <span style={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}>12</span>
          </div>
          <div style={{ padding: '12px 16px 6px', fontSize: 9, color: '#2D3748', letterSpacing: '0.12em', fontWeight: 600, marginTop: 4 }}>INTELLIGENCE</div>
          <div style={{ padding: '9px 16px', color: '#2D3748', fontSize: 13 }}>Parity Review</div>
          <div style={{ padding: '9px 16px', color: '#2D3748', fontSize: 13 }}>Benchmarks</div>
          <div style={{ padding: '12px 16px 6px', fontSize: 9, color: '#2D3748', letterSpacing: '0.12em', fontWeight: 600, marginTop: 4 }}>SWITCH MODE</div>
          <div style={{ padding: '9px 16px', color: '#374151', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>⇌</span> Credit officer view
          </div>
        </nav>
        <div style={{ padding: '12px 16px', borderTop: '1px solid #1A2235' }}>
          <div style={{ fontSize: 10, color: '#2D3748', fontFamily: "'IBM Plex Mono', monospace", marginBottom: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{email}</div>
          <button
            onClick={async () => { const sb = createBrowserClient(); if (sb) await sb.auth.signOut(); router.push('/login'); }}
            style={{ width: '100%', padding: '6px 0', background: 'transparent', border: '1px solid #1A2235', borderRadius: 4, color: '#374151', fontSize: 12, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
          >Sign out</button>
        </div>
      </aside>

      {/* Main */}
      <div style={{ marginLeft: 200, flex: 1 }}>
        {/* Top bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 40px', height: 48, borderBottom: '1px solid #1A2235', background: '#0A0F1E' }}>
          <div style={{ display: 'flex', gap: 8, fontSize: 12, color: '#374151', fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.08em' }}>
            <span style={{ color: '#6366F1' }}>PARITY</span>
            <span>·</span>
            <span style={{ color: '#CBD5E1' }}>DASHBOARD</span>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              onClick={() => router.push('/deals/new')}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', background: '#6366F1', color: '#fff', border: 'none', borderRadius: 5, fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
            >+ New deal</button>
            <div style={{ fontSize: 12, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace" }}>{initials} · ANALYST</div>
          </div>
        </div>

        <div style={{ padding: '28px 40px' }}>
          {/* Stat cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', background: '#1A2235', border: '1px solid #1A2235', borderRadius: 8, overflow: 'hidden', marginBottom: 28, gap: 1 }}>
            {[
              { label: 'ACTIVE DEALS', value: String(activeDeals).padStart(2, '0'), sub: '+1 this month', color: '#F1F5F9' },
              { label: 'PENDING REVIEW', value: '01', sub: deals[0] ? (deals[0].company_name || deals[0].name || '—') as string : '—', color: '#F59E0B' },
              { label: 'AVG ACCURACY', value: '97.3%', sub: '9,730 bps', color: '#4ADE80' },
              { label: 'OVERRIDE RATE', value: '2.7%', sub: '↓ vs prior period', color: '#F1F5F9' },
              { label: 'ENTITY DISCOVERIES', value: '07', sub: `${activeDeals} active deals`, color: '#818CF8' },
              { label: 'NEEDS REVIEW', value: '03', sub: 'requires action', color: '#F59E0B' },
            ].map((s) => (
              <div key={s.label} style={{ background: '#0D1220', padding: '16px 18px' }}>
                <div style={{ fontSize: 9, fontWeight: 700, color: '#374151', letterSpacing: '0.1em', marginBottom: 8 }}>{s.label}</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: s.color, fontFamily: "'IBM Plex Mono', monospace", lineHeight: 1 }}>{s.value}</div>
                <div style={{ fontSize: 10, color: '#4A5568', marginTop: 6 }}>{s.sub}</div>
              </div>
            ))}
          </div>

          {/* Deal Pipeline table */}
          <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid #1A2235' }}>
              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>DEAL PIPELINE</span>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: '#374151', fontFamily: "'IBM Plex Mono', monospace" }}>{activeDeals} record{activeDeals !== 1 ? 's' : ''}</span>
                <button onClick={() => router.push('/deals/new')} style={{ padding: '4px 12px', background: '#6366F1', color: '#fff', border: 'none', borderRadius: 4, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>+ New</button>
              </div>
            </div>

            {/* Column headers */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 90px 160px 70px 200px 140px 90px', padding: '10px 20px', borderBottom: '1px solid #1A2235' }}>
              {['BORROWER', 'TYPE', 'DEAL SIZE', 'ANALYST', 'STATUS', 'CONFIDENCE', 'UPDATED'].map((h) => (
                <span key={h} style={{ fontSize: 9, fontWeight: 700, color: '#2D3748', letterSpacing: '0.1em' }}>{h}</span>
              ))}
            </div>

            {deals.length === 0 && (
              <div style={{ padding: '48px 20px', textAlign: 'center', color: '#374151', fontSize: 13 }}>
                No deals yet.{' '}
                <span style={{ color: '#6366F1', cursor: 'pointer' }} onClick={() => router.push('/deals/new')}>Create your first deal →</span>
              </div>
            )}

            {deals.map((deal) => {
              const name = (deal.company_name || deal.name || 'Untitled') as string
              const shortId = deal.id.replace(/-/g, '').slice(0, 12).toUpperCase()
              const analyst = ((deal.analyst_initials || '—') as string).toUpperCase()
              const currency = (deal.currency || 'KES') as string
              const updatedAt = deal.created_at
                ? new Date(deal.created_at as string).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
                : '—'
              const status = 'Uploading documents'
              return (
                <div
                  key={deal.id}
                  onClick={() => router.push(`/v1/deal?deal_id=${deal.id}`)}
                  style={{ display: 'grid', gridTemplateColumns: '2fr 90px 160px 70px 200px 140px 90px', padding: '14px 20px', borderBottom: '1px solid #1A2235', cursor: 'pointer' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(99,102,241,0.04)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#F1F5F9' }}>{name}</div>
                    <div style={{ fontSize: 11, color: '#2D3748', fontFamily: "'IBM Plex Mono', monospace", marginTop: 2 }}>{shortId} · {currency}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{ fontSize: 10, fontWeight: 700, color: '#6366F1', background: 'rgba(99,102,241,0.12)', padding: '2px 7px', borderRadius: 3, border: '1px solid rgba(99,102,241,0.2)', letterSpacing: '0.06em' }}>DEBT</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', fontSize: 13, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace" }}>{currency} —</div>
                  <div style={{ display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 600, color: '#CBD5E1' }}>{analyst}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#64748B' }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: statusDotColor(status), display: 'inline-block', flexShrink: 0 }} />
                    {status}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', fontSize: 12, color: '#374151', fontFamily: "'IBM Plex Mono', monospace" }}>—</div>
                  <div style={{ display: 'flex', alignItems: 'center', fontSize: 12, color: '#374151' }}>{updatedAt}</div>
                </div>
              )
            })}
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', gap: 24, marginTop: 14, flexWrap: 'wrap' }}>
            {[
              { dot: '#4ADE80', label: 'VERIFIED — bank-derived' },
              { dot: '#818CF8', label: 'INFERRED — model output' },
              { dot: '#F59E0B', label: 'NEEDS REVIEW — analyst action' },
              { dot: '#EF4444', label: 'FLAGGED — requires action' },
            ].map((l) => (
              <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: '#374151' }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: l.dot, display: 'inline-block' }} />
                {l.label}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
