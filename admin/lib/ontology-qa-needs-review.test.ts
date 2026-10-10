import { describe, it, expect } from 'vitest'
import type { SupabaseClient } from '@supabase/supabase-js'
import { countByDeal, fetchDealsWithNeedsReview, ONTOLOGY_QA_DEAL_COLUMNS } from './ontology-qa-needs-review'
import { createFakeSupabase } from './fake-supabase.test-util'

const deal = (id: string, created_at: string) => ({
  id,
  currency: 'KES',
  created_at,
  accrual_period_start: null,
  accrual_period_end: null,
  // Identifying columns that must never reach the picker.
  name: `Secret name ${id}`,
  company_name: `Secret Co ${id}`,
  analyst_notes: `Secret notes ${id}`,
})

const entityRow = (deal_id: string, txn_id: string, role: string) => ({ deal_id, txn_id, role })

describe('countByDeal', () => {
  it('counts rows per deal_id', () => {
    const counts = countByDeal([{ deal_id: 'a' }, { deal_id: 'b' }, { deal_id: 'a' }])
    expect(counts.get('a')).toBe(2)
    expect(counts.get('b')).toBe(1)
    expect(counts.size).toBe(2)
  })
})

describe('fetchDealsWithNeedsReview', () => {
  const tables = {
    pds_deals: [deal('d-old', '2026-01-01T00:00:00Z'), deal('d-new', '2026-06-01T00:00:00Z'), deal('d-clean', '2026-09-01T00:00:00Z')],
    pds_txn_entity_map: [
      entityRow('d-old', 't1', 'needs_review'),
      entityRow('d-new', 't2', 'needs_review'),
      entityRow('d-new', 't3', 'needs_review'),
      entityRow('d-new', 't4', 'revenue'),
      entityRow('d-clean', 't5', 'revenue'),
    ],
  }

  it('returns exactly the deals that have needs_review items, excluding deals with none', async () => {
    const { client } = createFakeSupabase(tables)
    const result = await fetchDealsWithNeedsReview(client as unknown as SupabaseClient)
    expect(result.map((d) => d.id).sort()).toEqual(['d-new', 'd-old'])
    expect(result.find((d) => d.id === 'd-clean')).toBeUndefined()
  })

  it('counts only needs_review transactions per deal and sorts newest first', async () => {
    const { client } = createFakeSupabase(tables)
    const result = await fetchDealsWithNeedsReview(client as unknown as SupabaseClient)
    expect(result.map((d) => [d.id, d.needs_review_count])).toEqual([
      ['d-new', 2],
      ['d-old', 1],
    ])
  })

  it('returns an empty list when no deal has needs_review items', async () => {
    const { client } = createFakeSupabase({ pds_deals: tables.pds_deals, pds_txn_entity_map: [entityRow('d-clean', 't5', 'revenue')] })
    expect(await fetchDealsWithNeedsReview(client as unknown as SupabaseClient)).toEqual([])
  })

  it('pages past the 1000-row limit when counting', async () => {
    const many = Array.from({ length: 1500 }, (_, i) => entityRow('d-new', `t${i}`, 'needs_review'))
    const { client } = createFakeSupabase({ pds_deals: tables.pds_deals, pds_txn_entity_map: many })
    const result = await fetchDealsWithNeedsReview(client as unknown as SupabaseClient)
    expect(result).toHaveLength(1)
    expect(result[0].needs_review_count).toBe(1500)
  })

  it('never selects or returns identifying deal columns', async () => {
    const { client, selects } = createFakeSupabase(tables)
    const result = await fetchDealsWithNeedsReview(client as unknown as SupabaseClient)
    const dealSelects = selects.filter((s) => s.table === 'pds_deals')
    expect(dealSelects.length).toBeGreaterThan(0)
    for (const s of dealSelects) expect(s.columns).toBe(ONTOLOGY_QA_DEAL_COLUMNS)
    for (const d of result) {
      expect(Object.keys(d).sort()).toEqual(
        ['accrual_period_end', 'accrual_period_start', 'created_at', 'currency', 'id', 'needs_review_count']
      )
    }
    expect(JSON.stringify(result)).not.toMatch(/Secret/)
  })
})

describe('ONTOLOGY_QA_DEAL_COLUMNS', () => {
  it('excludes name, company_name and analyst_notes', () => {
    expect(ONTOLOGY_QA_DEAL_COLUMNS).not.toMatch(/name|analyst_notes|created_by|user_id/)
  })
})
