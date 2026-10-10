import { describe, it, expect, vi, beforeEach } from 'vitest'
import { NextResponse } from 'next/server'
import type { AdminSession } from '@/lib/require-admin-session'
import { createFakeSupabase } from '@/lib/fake-supabase.test-util'

const fromMock = vi.fn()
const requireAdminSessionMock = vi.fn<() => Promise<AdminSession | NextResponse>>(async () => ({ email: 'weevermbakaya@gmail.com' }))

let activeClient: { from: (t: string) => unknown } = { from: fromMock }

vi.mock('@/lib/supabase-staging', () => ({
  getSupabaseStaging: () => activeClient,
}))

vi.mock('@/lib/require-admin-session', () => ({
  requireAdminSession: () => requireAdminSessionMock(),
}))

const params = Promise.resolve({ id: 'd1' })

describe('GET /api/data/ontology-qa/[id]', () => {
  beforeEach(() => {
    fromMock.mockClear()
    activeClient = { from: fromMock }
    requireAdminSessionMock.mockClear()
    requireAdminSessionMock.mockImplementation(async () => ({ email: 'weevermbakaya@gmail.com' }))
  })

  it('returns 401 and never queries supabase when there is no session', async () => {
    requireAdminSessionMock.mockImplementation(async () =>
      NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    )
    const { GET } = await import('./route')
    const res = await GET(new Request('http://x') as never, { params })
    expect(res.status).toBe(401)
    expect(fromMock).not.toHaveBeenCalled()
  })

  it('returns 403 and never queries supabase when the email is not ontology-qa allowlisted', async () => {
    requireAdminSessionMock.mockImplementation(async () => ({ email: 'kwatukham@gmail.com' }))
    const { GET } = await import('./route')
    const res = await GET(new Request('http://x') as never, { params })
    expect(res.status).toBe(403)
    expect(fromMock).not.toHaveBeenCalled()
  })

  describe('deal scoping', () => {
    const dealRow = (id: string) => ({ id, currency: 'KES', created_at: '2026-07-01T00:00:00Z', accrual_period_start: null, accrual_period_end: null, company_name: 'Secret Co', name: 'Secret', analyst_notes: 'Secret' })
    const txn = (id: string, deal_id: string) => ({ id, deal_id, txn_date: '2026-07-02', account_id: 'a', signed_amount_cents: 100, abs_amount_cents: 100, is_transfer: false, created_at: '2026-07-02T00:00:00Z' })
    const tables = {
      pds_deals: [dealRow('d1'), dealRow('d2')],
      pds_raw_transactions: [txn('t1', 'd1'), txn('t2', 'd1'), txn('t3', 'd2')],
      pds_txn_entity_map: [
        { deal_id: 'd1', txn_id: 't1', entity_id: 'e1', role: 'needs_review', role_reason: 'KES 340,000 credit, 4.2x median' },
        { deal_id: 'd1', txn_id: 't2', entity_id: 'e2', role: 'revenue', role_reason: null },
        { deal_id: 'd2', txn_id: 't3', entity_id: 'e3', role: 'needs_review', role_reason: 'other deal reason' },
      ],
      pds_override_log: [],
      pds_overrides: [],
      pds_classification_overrides: [],
    }

    it('returns only the selected deal\'s transactions, roles and reasons', async () => {
      activeClient = createFakeSupabase(tables).client
      const { GET } = await import('./route')
      const res = await GET(new Request('http://x') as never, { params })
      const body = await res.json()
      expect(body.deal.id).toBe('d1')
      expect(body.transactions.map((t: { id: string }) => t.id).sort()).toEqual(['t1', 't2'])
      const t1 = body.transactions.find((t: { id: string }) => t.id === 't1')
      expect(t1.role).toBe('needs_review')
      expect(t1.role_reason).toBe('KES 340,000 credit, 4.2x median')
      expect(JSON.stringify(body)).not.toMatch(/other deal reason/)
    })

    it('does not leak company-identifying fields', async () => {
      activeClient = createFakeSupabase(tables).client
      const { GET } = await import('./route')
      const text = JSON.stringify(await (await GET(new Request('http://x') as never, { params })).json())
      expect(text).not.toMatch(/Secret|company_name|analyst_notes/)
    })
  })
})
