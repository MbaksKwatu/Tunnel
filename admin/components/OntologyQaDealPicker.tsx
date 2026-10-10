'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

interface PickerDeal {
  id: string
  currency: string
  needs_review_count: number
}

// Deal picker for Ontology QA review sessions (PAR-140). Lists only deals that
// have needs_review transactions; selecting one routes to the existing
// per-deal page (/ontology-qa/[id]), which already scopes the anonymized
// transaction table to that deal_id. Shows deal_id and counts only — nothing
// that could identify a company.
export function OntologyQaDealPicker({ currentDealId }: { currentDealId?: string }) {
  const router = useRouter()
  const [deals, setDeals] = useState<PickerDeal[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    let cancelled = false
    fetch('/api/data/ontology-qa?needs_review=1')
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return
        if (data.error) {
          setStatus('error')
        } else {
          setDeals(data.deals ?? [])
          setStatus('ready')
        }
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const placeholder =
    status === 'loading'
      ? 'Loading deals…'
      : status === 'error'
        ? 'Could not load deals'
        : deals.length === 0
          ? 'No deals with needs_review items'
          : 'Select a deal with needs_review items…'

  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 24, maxWidth: 560 }}>
      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, letterSpacing: '0.08em', color: 'var(--t2)' }}>
        REVIEW DEAL
      </span>
      <select
        aria-label="Select a deal to review"
        value={currentDealId && deals.some((d) => d.id === currentDealId) ? currentDealId : ''}
        disabled={status !== 'ready' || deals.length === 0}
        onChange={(e) => {
          if (e.target.value) router.push(`/ontology-qa/${e.target.value}`)
        }}
        style={{
          border: '1px solid var(--border)',
          background: 'var(--paper)',
          borderRadius: 6,
          padding: '8px 10px',
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 12,
          color: 'var(--t0)',
        }}
      >
        <option value="">{placeholder}</option>
        {deals.map((d) => (
          <option key={d.id} value={d.id}>
            {d.id} · {d.currency ?? '—'} · {d.needs_review_count} needs review
          </option>
        ))}
      </select>
    </label>
  )
}
