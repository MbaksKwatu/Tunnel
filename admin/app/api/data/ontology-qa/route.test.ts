import { describe, it, expect, vi, beforeEach } from 'vitest'
import { NextResponse } from 'next/server'
import type { AdminSession } from '@/lib/require-admin-session'
import { createFakeSupabase } from '@/lib/fake-supabase.test-util'

const rows = [{ id: 'd1', currency: 'KES', created_at: '2026-07-01T00:00:00Z' }]

const queryMock = {
  select: vi.fn().mockReturnThis(),
  order: vi.fn().mockReturnThis(),
  limit: vi.fn().mockResolvedValue({ data: rows, error: null }),
}
const fromMock = vi.fn(() => queryMock)
const requireAdminSessionMock = vi.fn<() => Promise<AdminSession | NextResponse>>(async () => ({ email: 'weevermbakaya@gmail.com' }))

let activeClient: { from: (t: string) => unknown } = { from: fromMock }

vi.mock('@/lib/supabase-staging', () => ({
  getSupabaseStaging: () => activeClient,
}))

vi.mock('@/lib/require-admin-session', () => ({
  requireAdminSession: () => requireAdminSessionMock(),
}))

describe('GET /api/data/ontology-qa', () => {
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
    const res = await GET()
    expect(res.status).toBe(401)
    expect(fromMock).not.toHaveBeenCalled()
  })

  it('returns 403 and never queries supabase when the email is not ontology-qa allowlisted', async () => {
    requireAdminSessionMock.mockImplementation(async () => ({ email: 'kwatukham@gmail.com' }))
    const { GET } = await import('./route')
    const res = await GET()
    expect(res.status).toBe(403)
    expect(fromMock).not.toHaveBeenCalled()
  })

  it('returns deals data for an ontology-qa allowlisted session', async () => {
    const { GET } = await import('./route')
    const res = await GET()
    const body = await res.json()
    expect(fromMock).toHaveBeenCalledWith('pds_deals')
    expect(body.deals).toEqual(rows)
  })

  describe('?needs_review=1 (deal picker source)', () => {
    const req = () => new Request('http://x/api/data/ontology-qa?needs_review=1')
    const setup = () => {
      const fake = createFakeSupabase({
        pds_deals: [
          { id: 'd1', currency: 'KES', created_at: '2026-07-01T00:00:00Z', accrual_period_start: null, accrual_period_end: null, company_name: 'Secret Co', name: 'Secret', analyst_notes: 'Secret' },
          { id: 'd2', currency: 'KES', created_at: '2026-08-01T00:00:00Z', accrual_period_start: null, accrual_period_end: null, company_name: 'Secret Co', name: 'Secret', analyst_notes: 'Secret' },
        ],
        pds_txn_entity_map: [
          { deal_id: 'd1', txn_id: 't1', role: 'needs_review' },
          { deal_id: 'd2', txn_id: 't2', role: 'revenue' },
        ],
      })
      activeClient = fake.client
      return fake
    }

    it('returns only deals with needs_review items, with counts', async () => {
      setup()
      const { GET } = await import('./route')
      const body = await (await GET(req())).json()
      expect(body.deals.map((d: { id: string; needs_review_count: number }) => [d.id, d.needs_review_count])).toEqual([['d1', 1]])
    })

    it('does not leak company-identifying fields', async () => {
      setup()
      const { GET } = await import('./route')
      const text = JSON.stringify(await (await GET(req())).json())
      expect(text).not.toMatch(/Secret|company_name|analyst_notes/)
    })

    it('still enforces the ontology-qa allowlist', async () => {
      requireAdminSessionMock.mockImplementation(async () => ({ email: 'kwatukham@gmail.com' }))
      setup()
      const { GET } = await import('./route')
      expect((await GET(req())).status).toBe(403)
    })

    it('leaves the default (no query param) response unchanged', async () => {
      const { GET } = await import('./route')
      const body = await (await GET(new Request('http://x/api/data/ontology-qa'))).json()
      expect(body.deals).toEqual(rows)
    })
  })
})
