import type { SupabaseClient } from '@supabase/supabase-js'

// Anonymized by design (PAR-42): only these pds_deals columns may ever be
// returned from the Ontology QA API. pds_deals also holds name, company_name
// and analyst_notes — never add them here.
export const ONTOLOGY_QA_DEAL_COLUMNS = 'id, currency, created_at, accrual_period_start, accrual_period_end'

const PAGE_SIZE = 1000
const CHUNK_SIZE = 100

export type NeedsReviewDeal = {
  id: string
  currency: string
  created_at: string
  accrual_period_start: string | null
  accrual_period_end: string | null
  needs_review_count: number
}

export function countByDeal(rows: { deal_id: string }[]): Map<string, number> {
  const counts = new Map<string, number>()
  for (const row of rows) counts.set(row.deal_id, (counts.get(row.deal_id) ?? 0) + 1)
  return counts
}

// Same source of truth as the per-deal page: pds_txn_entity_map.role.
async function fetchNeedsReviewRows(supabase: SupabaseClient) {
  const rows: { deal_id: string }[] = []
  let offset = 0
  for (;;) {
    const { data, error } = await supabase
      .from('pds_txn_entity_map')
      .select('deal_id')
      .eq('role', 'needs_review')
      .order('txn_id', { ascending: true })
      .range(offset, offset + PAGE_SIZE - 1)
    if (error) throw error
    rows.push(...(data ?? []))
    if (!data || data.length < PAGE_SIZE) break
    offset += PAGE_SIZE
  }
  return rows
}

// Deals that have at least one needs_review transaction, newest first.
export async function fetchDealsWithNeedsReview(supabase: SupabaseClient): Promise<NeedsReviewDeal[]> {
  const counts = countByDeal(await fetchNeedsReviewRows(supabase))
  const dealIds = [...counts.keys()]
  const deals: NeedsReviewDeal[] = []
  for (let i = 0; i < dealIds.length; i += CHUNK_SIZE) {
    const { data, error } = await supabase
      .from('pds_deals')
      .select(ONTOLOGY_QA_DEAL_COLUMNS)
      .in('id', dealIds.slice(i, i + CHUNK_SIZE))
    if (error) throw error
    for (const deal of (data ?? []) as Omit<NeedsReviewDeal, 'needs_review_count'>[]) {
      deals.push({ ...deal, needs_review_count: counts.get(deal.id) ?? 0 })
    }
  }
  return deals.sort((a, b) => (a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : 0))
}
