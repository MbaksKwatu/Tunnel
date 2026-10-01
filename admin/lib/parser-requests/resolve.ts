import type { SupabaseClient } from '@supabase/supabase-js'
import { casStatus, getParserRequest, latestTestRun, logEvent, type ParserRequestRow } from './store'

// The resolve trigger: the single place a parser request becomes `resolved`,
// and the single place the client is told about it. Nothing else writes
// status = 'resolved' (the admin PATCH route refuses it, and the DB CHECK
// constraints refuse it without a declared basis).
//
// Order matters: the DB status write happens first and stands on its own.
// Then three independent effects, each in its own try/catch — a Slack outage
// can't stop the email, and neither can undo the status write.

export type ResolveBasis = 'test_pass' | 'override'

export type EffectResult = { ok: boolean; detail: string; [key: string]: unknown }

export type ResolveOutcome =
  | {
      ok: true
      row: ParserRequestRow
      effects: { email: EffectResult; slack: EffectResult; client_status: EffectResult }
    }
  | { ok: false; httpStatus: number; error: string }

const DEFAULT_FROM = 'Parity <onboarding@resend.dev>'
const DEFAULT_APP_URL = 'https://parityfinance.vercel.app'
const DEFAULT_ADMIN_URL = 'https://parity-admin-three.vercel.app'

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
}

async function settle(fn: () => Promise<EffectResult>): Promise<EffectResult> {
  try {
    return await fn()
  } catch (err) {
    return { ok: false, detail: err instanceof Error ? err.message : String(err) }
  }
}

/** Form value first; else the owning account's chosen contact address; else its login email. */
export async function resolveRecipient(supabase: SupabaseClient, row: ParserRequestRow): Promise<string | null> {
  if (row.contact_email?.trim()) return row.contact_email.trim()
  if (!row.created_by) return null
  const { data: profile } = await supabase
    .from('user_profiles')
    .select('contact_email')
    .eq('user_id', row.created_by)
    .maybeSingle()
  const chosen = (profile as { contact_email?: string | null } | null)?.contact_email?.trim()
  if (chosen) return chosen
  const { data } = await supabase.auth.admin.getUserById(row.created_by)
  return data?.user?.email ?? null
}

async function sendClientEmail(
  supabase: SupabaseClient,
  row: ParserRequestRow,
  fetchImpl: typeof fetch
): Promise<EffectResult> {
  const apiKey = process.env.RESEND_API_KEY
  if (!apiKey) return { ok: false, detail: 'RESEND_API_KEY is not configured on the admin app' }
  const to = await resolveRecipient(supabase, row)
  if (!to) return { ok: false, detail: 'No contact email on record (no form email, no owning account)' }

  const bank = row.bank_name?.trim() || 'bank statement'
  const appUrl = (process.env.PARITY_APP_URL || DEFAULT_APP_URL).replace(/\/$/, '')
  const file = row.original_filename ? ` (<span style="font-family:monospace">${escapeHtml(row.original_filename)}</span>)` : ''
  const res = await fetchImpl('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: process.env.PARSER_REQUEST_EMAIL_FROM || DEFAULT_FROM,
      to: [to],
      subject: `Your ${bank} parser is ready — re-upload your statement`,
      html: `
        <h2 style="font-family:monospace;color:#14B8A6">Your ${escapeHtml(bank)} format is ready</h2>
        <p style="font-family:sans-serif;font-size:14px">
          Good news: Parity can now read the <strong>${escapeHtml(bank)}</strong> statement format you sent us${file}.
          We checked it against the exact file you submitted before sending this.
        </p>
        <p style="font-family:sans-serif;font-size:14px">
          Re-upload your statement in Parity to continue your analysis:
          <a href="${appUrl}/deals">${appUrl}/deals</a>
        </p>
        <hr style="margin:20px 0;border:none;border-top:1px solid #e5e7eb"/>
        <p style="font-family:sans-serif;font-size:12px;color:#9ca3af">Questions? Reply to this email.</p>
      `,
    }),
  })
  const body = (await res.json().catch(() => ({}))) as { id?: string; message?: string }
  if (!res.ok) return { ok: false, detail: `Resend HTTP ${res.status}: ${body.message ?? 'unknown error'}`, to }
  return { ok: true, detail: `Sent to ${to}`, to, resend_id: body.id ?? null }
}

async function postSlack(row: ParserRequestRow, basis: ResolveBasis, actor: string, fetchImpl: typeof fetch): Promise<EffectResult> {
  const webhook = process.env.SLACK_PARSER_WEBHOOK_URL
  if (!webhook) return { ok: false, detail: 'SLACK_PARSER_WEBHOOK_URL is not configured on the admin app' }
  const adminBase = process.env.ADMIN_DASHBOARD_URL || DEFAULT_ADMIN_URL
  const text = [
    `:white_check_mark: *Parser request resolved:* ${row.bank_name || 'Unnamed bank'}`,
    `• Basis: ${basis === 'test_pass' ? 'passed test against submitted file' : 'admin override'}`,
    `• By: ${actor}`,
    `• File: ${row.original_filename || '—'}`,
    `• Client notified at: ${row.contact_email || 'account email (resolved at send time)'}`,
    `• <${adminBase}/parser-requests|Open the parser-request queue>`,
  ].join('\n')
  const res = await fetchImpl(webhook, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  const body = await res.text().catch(() => '')
  if (!res.ok) return { ok: false, detail: `Slack HTTP ${res.status}: ${body.slice(0, 200)}` }
  return { ok: true, detail: `Slack accepted (${body || res.status})` }
}

/**
 * The client dashboard reads status live from the DB through the backend
 * (GET /v1/parser-requests, no server cache) and refetches on mount/focus,
 * so the client side is correct as long as the DB really says resolved.
 * Read it back rather than assume the write landed.
 */
async function confirmClientStatus(supabase: SupabaseClient, id: string): Promise<EffectResult> {
  const fresh = await getParserRequest(supabase, id)
  if (fresh?.status !== 'resolved') return { ok: false, detail: `Read-back status is ${fresh?.status ?? 'missing'}` }
  if (!fresh.created_by) {
    return { ok: true, detail: 'status=resolved confirmed; row has no owning account, so it shows on no client dashboard' }
  }
  return { ok: true, detail: 'status=resolved confirmed on read-back; client dashboard reads it live' }
}

export async function resolveParserRequest(
  supabase: SupabaseClient,
  id: string,
  opts: { basis: ResolveBasis; reason?: string; actor: string },
  fetchImpl: typeof fetch = fetch
): Promise<ResolveOutcome> {
  const row = await getParserRequest(supabase, id)
  if (!row) return { ok: false, httpStatus: 404, error: 'Parser request not found' }
  if (row.status === 'resolved') return { ok: false, httpStatus: 409, error: 'Already resolved' }

  const reason = opts.reason?.trim() || null
  if (opts.basis === 'override') {
    if (!reason) return { ok: false, httpStatus: 400, error: 'An override requires a written reason' }
  } else {
    if (row.status !== 'testing') {
      return { ok: false, httpStatus: 409, error: 'Run "Test against submitted file" first — only a passing test can resolve' }
    }
    const last = await latestTestRun(supabase, id)
    if (!last?.passed) {
      return { ok: false, httpStatus: 409, error: `Latest test did not pass${last ? `: ${last.reason}` : ' (no test on record)'}` }
    }
  }

  // 1. The status write — first, and independent of everything after it.
  const resolved = await casStatus(supabase, id, row.status, {
    status: 'resolved',
    resolved_at: new Date().toISOString(),
    resolution_basis: opts.basis,
    resolution_note: reason,
  })
  if (!resolved) return { ok: false, httpStatus: 409, error: 'Request changed status while resolving; reload and retry' }
  await logEvent(supabase, {
    request_id: id, kind: 'status_change', from_status: row.status, to_status: 'resolved', actor: opts.actor,
    reason, detail: { basis: opts.basis },
  })

  // 2–4. Three independent effects.
  const email = await settle(() => sendClientEmail(supabase, resolved, fetchImpl))
  const slack = await settle(() => postSlack(resolved, opts.basis, opts.actor, fetchImpl))
  const client_status = await settle(() => confirmClientStatus(supabase, id))
  const effects = { email, slack, client_status }

  await logEvent(supabase, { request_id: id, kind: 'notification', actor: opts.actor, detail: effects })
  return { ok: true, row: resolved, effects }
}
