import { getSupabaseStaging } from '@/lib/supabase-staging'
import { requireAdminSession } from '@/lib/require-admin-session'
import { isOntologyQaAllowed } from '@/lib/ontology-qa-access'
import { NextResponse } from 'next/server'
import { fetchDealsWithNeedsReview, ONTOLOGY_QA_DEAL_COLUMNS } from '@/lib/ontology-qa-needs-review'

// ?needs_review=1 narrows the list to deals with at least one needs_review
// transaction (each with a needs_review_count) — the data source for the deal
// picker (PAR-140). Without it, behavior is unchanged.
export async function GET(request?: Request) {
  const session = await requireAdminSession()
  if (session instanceof NextResponse) return session
  if (!isOntologyQaAllowed(session.email)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const supabase = getSupabaseStaging()

  if (request && new URL(request.url).searchParams.get('needs_review') === '1') {
    try {
      const deals = await fetchDealsWithNeedsReview(supabase)
      return NextResponse.json({ deals, fetched_at: new Date().toISOString() })
    } catch (e) {
      return NextResponse.json({ error: e instanceof Error ? e.message : 'Query failed' }, { status: 500 })
    }
  }

  const { data, error } = await supabase
    .from('pds_deals')
    .select(ONTOLOGY_QA_DEAL_COLUMNS)
    .order('created_at', { ascending: false })
    .limit(100)
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json({ deals: data ?? [], fetched_at: new Date().toISOString() })
}
