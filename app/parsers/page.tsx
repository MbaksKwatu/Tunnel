'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { createBrowserClient } from '@/lib/supabase'
import { AccountSidebar } from '@/components/AccountSidebar'
import { ParserBanners } from '@/components/parsers/ParserBanners'
import { accountParserRequestsKey, useAccountParserRequests } from '@/lib/queries/parser-requests'
import { toClientParserStatus, parserRequestLabel } from '@/lib/parser-request-status'

const mono = "'IBM Plex Mono', monospace"
const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

const badgeStyle = (ready: boolean): React.CSSProperties => ({
  display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: mono, fontSize: 10, letterSpacing: '0.05em',
  padding: '3px 9px', borderRadius: 3, whiteSpace: 'nowrap',
  background: ready ? 'rgba(16,185,129,0.1)' : 'rgba(242,184,75,0.1)',
  color: ready ? 'var(--green)' : 'var(--amber)',
  border: `1px solid ${ready ? 'rgba(16,185,129,0.28)' : 'rgba(242,184,75,0.28)'}`,
})

const inputStyle: React.CSSProperties = {
  width: '100%', background: 'var(--bg)', border: '1px solid var(--b1)', borderRadius: 4, padding: '9px 11px',
  fontSize: 13, color: 'var(--t0)', outline: 'none', boxSizing: 'border-box', fontFamily: "'IBM Plex Sans', sans-serif",
}
const labelStyle: React.CSSProperties = {
  display: 'block', fontFamily: mono, fontSize: 10, letterSpacing: '0.06em', color: 'var(--t2)',
  textTransform: 'uppercase', marginBottom: 6, textAlign: 'left',
}

export default function BankParsersPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [userId, setUserId] = useState<string | undefined>()
  const [sessionEmail, setSessionEmail] = useState('')
  const [tab, setTab] = useState<'all' | 'upload'>('all')
  const [expanded, setExpanded] = useState<string | null>(null)

  const [bankName, setBankName] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [justSubmitted, setJustSubmitted] = useState('')

  useEffect(() => {
    const supabase = createBrowserClient()
    if (!supabase) { router.replace('/login'); return }
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) { router.replace('/login'); return }
      const email = session.user.email ?? ''
      setUserId(session.user.id)
      setSessionEmail(email)
      setContactEmail((prev) => prev || email)
    })
  }, [router])

  const requestsQuery = useAccountParserRequests(userId)
  const requests = requestsQuery.data?.parser_requests ?? []

  const canSubmit = !!bankName.trim() && !!contactEmail.trim() && !!file && !submitting

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit || !file) return
    setSubmitting(true)
    setError('')
    try {
      // Fresh token at submit time — the server verifies it to attribute created_by.
      const supabase = createBrowserClient()
      const { data: { session } } = supabase ? await supabase.auth.getSession() : { data: { session: null } }
      const form = new FormData()
      form.append('bank_name', bankName.trim())
      form.append('contact_email', contactEmail.trim())
      form.append('sample_file', file)
      if (session?.access_token) form.append('access_token', session.access_token)

      const res = await fetch('/api/request-parser', { method: 'POST', body: form })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error((data as { error?: string }).error ?? `Error ${res.status}`)
      }
      setJustSubmitted(bankName.trim())
      setBankName('')
      setFile(null)
      await queryClient.invalidateQueries({ queryKey: accountParserRequestsKey(userId) })
      setTab('all')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed — please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const goToDeal = (dealId: string) => router.push(`/v1/deal?deal_id=${dealId}`)

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', fontFamily: "'IBM Plex Sans', sans-serif", color: 'var(--t0)' }}>
      <AccountSidebar active="parsers" email={sessionEmail} />

      <div style={{ marginLeft: 200, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 40px', height: 48, borderBottom: '1px solid var(--s3)', background: 'var(--s1)' }}>
          <div style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--t2)', fontFamily: mono, letterSpacing: '0.08em' }}>
            <span style={{ color: 'var(--accent)' }}>PARITY</span><span>·</span><span style={{ color: 'var(--t0)' }}>BANK PARSERS</span>
          </div>
        </div>

        <div style={{ maxWidth: 900, margin: '0 auto', padding: '40px 32px 100px' }}>
          <h1 style={{ fontSize: 22, fontWeight: 500, margin: '0 0 6px' }}>Bank Parsers</h1>
          <p style={{ fontSize: 13, color: 'var(--t1)', lineHeight: 1.6, maxWidth: 560, margin: '0 0 24px' }}>
            Every bank-format request you&apos;ve made, and whether it&apos;s ready to use. Upload a sample statement directly if your bank isn&apos;t yet supported.
          </p>

          <ParserBanners userId={userId} requests={requests} />

          <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--b1)', marginBottom: 24 }}>
            {([['all', 'All requests'], ['upload', 'Upload new']] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                style={{ padding: '9px 4px', marginRight: 22, fontSize: 12.5, background: 'none', border: 'none', cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif", color: tab === key ? 'var(--t0)' : 'var(--t1)', borderBottom: `2px solid ${tab === key ? 'var(--accent)' : 'transparent'}` }}
              >{label}</button>
            ))}
          </div>

          {tab === 'all' && (
            <>
              {justSubmitted && (
                <div style={{ fontSize: 12.5, padding: '10px 14px', borderRadius: 5, marginBottom: 14, background: 'rgba(20,184,166,0.08)', border: '1px solid rgba(20,184,166,0.3)', color: 'var(--t0)' }}>
                  Request for <b>{justSubmitted}</b> submitted. It will show below as Processing, and we&apos;ll email you when it&apos;s ready.
                </div>
              )}
              <div style={{ border: '1px solid var(--b1)', borderRadius: 5, overflow: 'hidden', background: 'var(--s1)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 150px 120px 160px', gap: 16, padding: '10px 18px', fontFamily: mono, fontSize: 9, letterSpacing: '0.08em', color: 'var(--t2)', textTransform: 'uppercase', borderBottom: '1px solid var(--b1)' }}>
                  <div>Bank</div><div>Status</div><div>Requested</div><div />
                </div>
                {(!userId || requestsQuery.isLoading) && <div style={{ padding: 24, textAlign: 'center', color: 'var(--t2)', fontSize: 12 }}>Loading…</div>}
                {!!userId && requestsQuery.isError && <div style={{ padding: 24, textAlign: 'center', color: 'var(--red)', fontSize: 12 }}>Couldn&apos;t load your requests. Please refresh.</div>}
                {!!userId && !requestsQuery.isLoading && !requestsQuery.isError && requests.length === 0 && (
                  <div style={{ padding: 32, textAlign: 'center', color: 'var(--t2)', fontSize: 13 }}>
                    No bank parser requests yet.{' '}
                    <span style={{ color: 'var(--accent)', cursor: 'pointer' }} onClick={() => setTab('upload')}>Request one →</span>
                  </div>
                )}
                {requests.map((r) => {
                  const st = toClientParserStatus(r.status)
                  const ready = st.key === 'ready'
                  const open = expanded === r.id
                  return (
                    <div key={r.id} data-testid="parser-request-row" style={{ borderBottom: '1px solid var(--b1)' }}>
                      <div
                        onClick={() => setExpanded(open ? null : r.id)}
                        style={{ display: 'grid', gridTemplateColumns: '1fr 150px 120px 160px', gap: 16, alignItems: 'center', padding: '14px 18px', cursor: 'pointer' }}
                      >
                        <div>
                          <div style={{ fontSize: 13 }}>{parserRequestLabel(r)}</div>
                          <div style={{ fontFamily: mono, fontSize: 9.5, color: 'var(--t2)', marginTop: 2 }}>{r.deal_name || (r.deal_id ? 'Linked deal' : 'No linked deal')}</div>
                        </div>
                        <div><span style={badgeStyle(ready)}><span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor' }} />{st.label.toUpperCase()}</span></div>
                        <div style={{ fontFamily: mono, fontSize: 10.5, color: 'var(--t2)' }}>{fmtDate(r.created_at)}</div>
                        <div style={{ fontFamily: mono, fontSize: 10.5, textAlign: 'right', color: ready ? 'var(--accent)' : 'var(--t2)' }}>
                          {ready ? (r.deal_id ? 'Go to deal →' : 'Upload a new statement') : open ? 'Hide ↑' : 'View →'}
                        </div>
                      </div>
                      {open && (
                        <div style={{ padding: '4px 18px 18px', background: 'rgba(255,255,255,0.015)' }}>
                          {[
                            ['FILE SUBMITTED', r.original_filename || '—'],
                            ['REQUESTED', fmtDate(r.created_at)],
                            ['LINKED DEAL', r.deal_name || (r.deal_id ? 'Linked deal' : 'None')],
                          ].map(([k, v]) => (
                            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', fontSize: 12, borderBottom: '1px solid var(--b1)' }}>
                              <span style={{ color: 'var(--t2)', fontFamily: mono, fontSize: 10, letterSpacing: '0.04em' }}>{k}</span>
                              <span>{v}</span>
                            </div>
                          ))}
                          {ready && (
                            <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                              {r.deal_id && (
                                <button onClick={() => goToDeal(r.deal_id!)} style={{ background: 'var(--accent)', color: '#080C18', border: 'none', borderRadius: 3, fontSize: 12, fontWeight: 500, padding: '9px 16px', cursor: 'pointer' }}>Go to deal →</button>
                              )}
                              <button onClick={() => router.push('/deals/new')} style={{ background: 'transparent', color: 'var(--t0)', border: '1px solid var(--b1)', borderRadius: 3, fontSize: 12, padding: '9px 16px', cursor: 'pointer' }}>Upload a new statement</button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          )}

          {tab === 'upload' && (
            <form onSubmit={handleSubmit} style={{ border: '1px dashed var(--b1)', borderRadius: 6, padding: '32px 24px', background: 'var(--s1)' }}>
              <div style={{ textAlign: 'center', marginBottom: 18 }}>
                <div style={{ fontSize: 13.5, fontWeight: 500, marginBottom: 4 }}>Request a new bank format</div>
                <div style={{ fontSize: 11.5, color: 'var(--t2)' }}>Drop a sample statement and we&apos;ll build the parser. Most are ready within a few hours.</div>
              </div>
              <div style={{ display: 'grid', gap: 14, maxWidth: 420, margin: '0 auto' }}>
                <div>
                  <label style={labelStyle} htmlFor="bp-bank">Bank name *</label>
                  <input id="bp-bank" required value={bankName} onChange={(e) => setBankName(e.target.value)} placeholder="e.g. SBM Bank Kenya" style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle} htmlFor="bp-email">Contact email *</label>
                  <input id="bp-email" type="email" required value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} style={inputStyle} />
                  <div style={{ fontFamily: mono, fontSize: 9.5, color: 'var(--t2)', marginTop: 5, textAlign: 'left' }}>
                    {sessionEmail && contactEmail.trim() && contactEmail.trim() !== sessionEmail
                      ? 'This updates your account’s contact email going forward, not just this request.'
                      : 'Pre-filled from your account · editable'}
                  </div>
                </div>
                <div>
                  <label style={labelStyle}>Sample statement *</label>
                  <input ref={fileInputRef} type="file" accept=".pdf,.xlsx,.xls,.csv" style={{ display: 'none' }} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                  <button type="button" onClick={() => fileInputRef.current?.click()} style={{ ...inputStyle, textAlign: 'left', cursor: 'pointer', color: file ? 'var(--t0)' : 'var(--t2)' }}>
                    {file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : 'Choose a PDF, XLSX or CSV…'}
                  </button>
                </div>
                {error && (
                  <div style={{ fontSize: 12, color: 'var(--red)', background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', borderRadius: 4, padding: '8px 12px' }}>{error}</div>
                )}
                <button type="submit" disabled={!canSubmit} style={{ width: '100%', background: canSubmit ? 'var(--accent)' : 'var(--s3)', color: canSubmit ? '#080C18' : 'var(--t2)', border: 'none', borderRadius: 3, fontSize: 12.5, fontWeight: 500, padding: '10px 18px', cursor: canSubmit ? 'pointer' : 'not-allowed' }}>
                  {submitting ? 'Submitting…' : 'Upload statement →'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
