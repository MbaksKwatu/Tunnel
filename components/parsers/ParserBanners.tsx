'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import type { AccountParserRequestItem } from '@/lib/v1-api'
import { toClientParserStatus, parserRequestLabel } from '@/lib/parser-request-status'

// Dismissal is an explicit click, persisted per user. The key includes the
// client-facing state, so a dismissed "Processing" banner does not suppress
// the "Ready" banner when the same request is later resolved.
// Stored in localStorage only: no backend field exists for this (see PR notes).
const storageKey = (userId: string) => `parity:parser-banners-dismissed:${userId}`
const bannerId = (r: AccountParserRequestItem) => `${r.id}:${toClientParserStatus(r.status).key}`

function readDismissed(userId: string): string[] {
  try {
    const raw = localStorage.getItem(storageKey(userId))
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function ParserBanners({ userId, requests }: { userId: string | undefined; requests: AccountParserRequestItem[] }) {
  const router = useRouter()
  const [dismissed, setDismissed] = useState<string[] | null>(null)

  useEffect(() => {
    if (userId) setDismissed(readDismissed(userId))
  }, [userId])

  // Wait for the stored set so a previously-dismissed banner never flashes.
  if (!userId || dismissed === null) return null

  const dismiss = (id: string) => {
    const next = [...dismissed, id]
    setDismissed(next)
    try { localStorage.setItem(storageKey(userId), JSON.stringify(next)) } catch { /* private mode: dismiss lasts this page view */ }
  }

  const visible = requests
    .filter((r) => !dismissed.includes(bannerId(r)))
    // Ready first — it's the actionable one.
    .sort((a, b) => Number(toClientParserStatus(b.status).key === 'ready') - Number(toClientParserStatus(a.status).key === 'ready'))
  if (visible.length === 0) return null

  return (
    <div data-testid="parser-banners" style={{ marginBottom: 20 }}>
      {visible.map((r) => {
        const ready = toClientParserStatus(r.status).key === 'ready'
        const color = ready ? '16,185,129' : '242,184,75'
        const submitted = r.created_at
          ? new Date(r.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
          : null
        return (
          <div
            key={bannerId(r)}
            data-testid={ready ? 'parser-banner-ready' : 'parser-banner-processing'}
            style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderRadius: 6, marginBottom: 10, fontSize: 12.5, background: `rgba(${color},0.1)`, border: `1px solid rgba(${color},0.28)`, color: 'var(--t0)' }}
          >
            <span style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: `rgb(${color})` }} />
            <div style={{ flex: 1 }}>
              <div>
                <b>{parserRequestLabel(r)}</b>
                {ready ? ' is ready. Re-upload your statement to process it.' : ' is still processing.'}
              </div>
              {!ready && submitted && (
                <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, opacity: 0.65, marginTop: 2 }}>Submitted {submitted}</div>
              )}
            </div>
            {ready && (
              <button
                onClick={() => router.push(r.deal_id ? `/v1/deal?deal_id=${r.deal_id}` : '/deals/new')}
                style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, padding: '5px 11px', borderRadius: 4, border: 'none', background: `rgb(${color})`, color: '#080C18', fontWeight: 600, cursor: 'pointer', flexShrink: 0 }}
              >
                {r.deal_id ? 'Go to deal →' : 'Upload a new statement'}
              </button>
            )}
            <button
              onClick={() => dismiss(bannerId(r))}
              aria-label="Dismiss"
              title="Dismiss"
              style={{ background: 'none', border: 'none', color: 'inherit', opacity: 0.6, fontSize: 15, padding: '0 2px', cursor: 'pointer', flexShrink: 0 }}
            >✕</button>
          </div>
        )
      })}
    </div>
  )
}
