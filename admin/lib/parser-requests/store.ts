import type { SupabaseClient } from '@supabase/supabase-js'
import type { ParserRequestStatus } from './lifecycle'

export type ParserRequestRow = {
  id: string
  bank_name: string | null
  original_filename: string | null
  storage_path: string | null
  status: ParserRequestStatus
  deal_id: string | null
  created_by: string | null
  contact_email: string | null
  resolution_basis: string | null
}

export type ParserRequestEvent = {
  request_id: string
  kind: 'status_change' | 'test_run' | 'notification'
  from_status?: string | null
  to_status?: string | null
  actor: string
  reason?: string | null
  detail?: Record<string, unknown>
}

export async function getParserRequest(supabase: SupabaseClient, id: string): Promise<ParserRequestRow | null> {
  const { data, error } = await supabase.from('pds_parser_requests').select('*').eq('id', id).maybeSingle()
  if (error) throw new Error(error.message)
  return (data as ParserRequestRow | null) ?? null
}

/**
 * Compare-and-set status change: only applies if the row is still in
 * `from`, so two admins (or a double click) can't both move it. Returns the
 * updated row, or null if the row had already moved on.
 */
export async function casStatus(
  supabase: SupabaseClient,
  id: string,
  from: ParserRequestStatus,
  patch: Record<string, unknown> & { status: ParserRequestStatus }
): Promise<ParserRequestRow | null> {
  const { data, error } = await supabase
    .from('pds_parser_requests')
    .update(patch)
    .eq('id', id)
    .eq('status', from)
    .select('*')
  if (error) throw new Error(error.message)
  return ((data as ParserRequestRow[] | null) ?? [])[0] ?? null
}

/** Append to the audit log. Best-effort: a log failure never undoes the action it records. */
export async function logEvent(supabase: SupabaseClient, event: ParserRequestEvent): Promise<void> {
  const { error } = await supabase.from('pds_parser_request_events').insert({ detail: {}, ...event })
  if (error) console.error('[parser-requests] event log write failed:', error.message, event.kind)
}

export async function latestTestRun(
  supabase: SupabaseClient,
  id: string
): Promise<{ passed: boolean; reason: string; created_at: string } | null> {
  const { data, error } = await supabase
    .from('pds_parser_request_events')
    .select('detail, created_at')
    .eq('request_id', id)
    .eq('kind', 'test_run')
    .order('created_at', { ascending: false })
    .limit(1)
  if (error) throw new Error(error.message)
  const row = (data ?? [])[0] as { detail: { passed?: boolean; reason?: string }; created_at: string } | undefined
  if (!row) return null
  return { passed: row.detail?.passed === true, reason: row.detail?.reason ?? '', created_at: row.created_at }
}
