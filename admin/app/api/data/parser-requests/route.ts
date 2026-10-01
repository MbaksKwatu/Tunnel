import { getSupabase, SUPABASE_ENV } from '@/lib/supabase'
import { requireAdminSession } from '@/lib/require-admin-session'
import { signParserRequestPaths } from '@/lib/parser-requests-signed-urls'
import { envHeaders } from '@/lib/env-header'
import { NextRequest, NextResponse } from 'next/server'
import { canManuallyTransition, isParserRequestStatus } from '@/lib/parser-requests/lifecycle'
import { casStatus, getParserRequest, logEvent } from '@/lib/parser-requests/store'

// `parser_requests` ("auto" — Musa's automated pipeline only,
// backend/v1/integrations/musa_file_processor.py; read-only here) and
// `pds_parser_requests` (every client request: the form, upload
// auto-detection, and GBFund's API route since migration 046 — the only
// table this queue acts on) are two separate tables. The admin queue reads
// both, or every form-submitted request is invisible here (PAR-45).
export async function GET() {
  const session = await requireAdminSession()
  if (session instanceof NextResponse) return session

  const supabase = getSupabase()

  const [autoResult, manualResult] = await Promise.all([
    supabase
      .from('parser_requests')
      .select('*')
      .order('requested_at', { ascending: false }),
    supabase
      .from('pds_parser_requests')
      .select('*')
      .order('created_at', { ascending: false }),
  ])

  if (autoResult.error) {
    return NextResponse.json({ error: autoResult.error.message }, { status: 500 })
  }
  if (manualResult.error) {
    return NextResponse.json({ error: manualResult.error.message }, { status: 500 })
  }

  // `storage_path` (both tables) points into Parity's own `parser-requests`
  // Storage bucket — PAR-145: sign it fresh on every read instead of ever
  // persisting a URL, so the link is never older than this response. Rows
  // with no storage_path (nothing was ever uploaded) get signed_url: null.
  const [auto, manual] = await Promise.all([
    signParserRequestPaths(supabase, autoResult.data ?? []),
    signParserRequestPaths(supabase, manualResult.data ?? []),
  ])

  // PAR-242: "which deal/org requested it" — both tables only carry deal_id,
  // not a name, so the list previously showed an opaque UUID at best (manual
  // rows) or nothing (auto rows have no deal-name field at all). Resolve
  // deal_id -> company_name/name in one batched query rather than persisting
  // a duplicate copy of the name on either source table.
  const dealIds = Array.from(
    new Set(
      [...auto, ...manual]
        .map((r) => (r as { deal_id?: string | null }).deal_id)
        .filter((id): id is string => Boolean(id))
    )
  )
  let dealNameById: Record<string, string> = {}
  if (dealIds.length > 0) {
    const { data: deals } = await supabase
      .from('pds_deals')
      .select('id, company_name, name')
      .in('id', dealIds)
    dealNameById = Object.fromEntries(
      (deals ?? []).map((d) => [d.id, d.company_name || d.name || null])
    )
  }
  const withDealName = <T extends { deal_id?: string | null }>(rows: T[]) =>
    rows.map((r) => ({ ...r, deal_name: r.deal_id ? dealNameById[r.deal_id] ?? null : null }))

  // Latest "Test against submitted file" verdict per manual row, so the queue
  // can show it and enable "Mark resolved" only after a genuine pass.
  const manualIds = manual.map((r) => (r as { id: string }).id)
  const lastTestById: Record<string, { passed: boolean; reason: string; created_at: string }> = {}
  if (manualIds.length > 0) {
    const { data: tests } = await supabase
      .from('pds_parser_request_events')
      .select('request_id, detail, created_at')
      .eq('kind', 'test_run')
      .in('request_id', manualIds)
      .order('created_at', { ascending: false })
    for (const t of (tests ?? []) as Array<{ request_id: string; detail: { passed?: boolean; reason?: string }; created_at: string }>) {
      if (!lastTestById[t.request_id]) {
        lastTestById[t.request_id] = { passed: t.detail?.passed === true, reason: t.detail?.reason ?? '', created_at: t.created_at }
      }
    }
  }
  const manualWithTests = withDealName(manual).map((r) => ({
    ...r,
    last_test: lastTestById[(r as { id: string }).id] ?? null,
  }))

  return NextResponse.json(
    { auto: withDealName(auto), manual: manualWithTests },
    { headers: envHeaders(SUPABASE_ENV) }
  )
}

// Plain status moves on pds_parser_requests only (migration 046). The Musa
// `parser_requests` table is that pipeline's own state machine (24h SLA
// sweep) and is read-only here. `testing` is entered by running a test and
// `resolved` only through POST /[id]/resolve — never through this PATCH.
export async function PATCH(request: NextRequest) {
  const session = await requireAdminSession()
  if (session instanceof NextResponse) return session

  const { id, status } = await request.json()
  if (typeof id !== 'string' || !isParserRequestStatus(status)) {
    return NextResponse.json({ error: 'id and a valid status are required' }, { status: 400 })
  }

  const supabase = getSupabase()
  const row = await getParserRequest(supabase, id)
  if (!row) return NextResponse.json({ error: 'Parser request not found' }, { status: 404 })
  if (!canManuallyTransition(row.status, status)) {
    return NextResponse.json(
      { error: `Cannot move ${row.status} → ${status} directly${status === 'resolved' ? ' (use Test → Mark resolved, or override with a reason)' : ''}` },
      { status: 409 }
    )
  }

  const updated = await casStatus(supabase, id, row.status, { status })
  if (!updated) return NextResponse.json({ error: 'Request changed status meanwhile; reload' }, { status: 409 })
  await logEvent(supabase, { request_id: id, kind: 'status_change', from_status: row.status, to_status: status, actor: session.email })
  return NextResponse.json({ ok: true, row: updated })
}
