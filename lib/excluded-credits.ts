/**
 * Excluded-credits disclosure for the Analysis tab (PAR-86, 2026-10-01).
 *
 * GET /v1/deals/{id}/analytics/monthly-cashflow counts a credit as inflow only
 * when its role is in the backend's inflow allow-list; every other credit
 * (needs_review, transfer, reversal_credit, unclassified) is reported
 * separately under `excluded_credits` (PR #255). This module turns that
 * response into display numbers. It is deliberately pure — no React, no
 * fetching — and does NOT recompute or alter any figure the backend computed;
 * it only sums and compares the integers the API already returned.
 *
 * All amounts are integer cents. Percentages are floored integers, matching the
 * backend's deterministic-arithmetic rule (no rounding up, so a share is never
 * overstated).
 */

export interface ExcludedCreditsMonth {
  month: string
  excluded_credit_cents: number
  pending_classification_cents: number
  by_role: Record<string, number>
}

export interface ExcludedCredits {
  /** keyed by "YYYY-MM"; months with no excluded credits are absent */
  months: Record<string, ExcludedCreditsMonth>
  excludedTotalCents: number
  pendingTotalCents: number
}

export interface ExcludedCreditsResponseFields {
  excluded_credits?: ExcludedCreditsMonth[]
  excluded_credits_total_cents?: number
  pending_classification_total_cents?: number
}

/**
 * Null when the response does not carry the field at all (older backend, or a
 * response from a cached/other source). Callers must treat null as "disclosure
 * unavailable" and say so — never as "nothing was excluded".
 */
export function toExcludedCredits(res: ExcludedCreditsResponseFields | null | undefined): ExcludedCredits | null {
  if (!res || !Array.isArray(res.excluded_credits)) return null
  const months: Record<string, ExcludedCreditsMonth> = {}
  for (const m of res.excluded_credits) months[m.month] = m
  const sum = (f: (m: ExcludedCreditsMonth) => number) => res.excluded_credits!.reduce((s, m) => s + f(m), 0)
  return {
    months,
    excludedTotalCents: res.excluded_credits_total_cents ?? sum((m) => m.excluded_credit_cents),
    pendingTotalCents: res.pending_classification_total_cents ?? sum((m) => m.pending_classification_cents),
  }
}

/** floor(excluded / (inflow + excluded) * 100); 0 when there are no credits at all. */
export function excludedSharePct(excludedCents: number, inflowCents: number): number {
  const total = excludedCents + inflowCents
  return total > 0 ? Math.floor((excludedCents * 100) / total) : 0
}

/** "<1%" instead of a misleading "0%" when something is excluded but under 1%. */
export function formatSharePct(excludedCents: number, pct: number): string {
  if (excludedCents > 0 && pct === 0) return '<1%'
  return `${pct}%`
}

export interface MonthExclusion {
  excludedCents: number
  pendingCents: number
  pct: number
  /** e.g. [["needs_review", 850000000], ["transfer", 70000]] largest first */
  roles: Array<[string, number]>
}

export function monthExclusion(month: string, inflowCents: number, ec: ExcludedCredits | null): MonthExclusion | null {
  const m = ec?.months[month]
  if (!m || m.excluded_credit_cents <= 0) return null
  return {
    excludedCents: m.excluded_credit_cents,
    pendingCents: m.pending_classification_cents,
    pct: excludedSharePct(m.excluded_credit_cents, inflowCents),
    roles: Object.entries(m.by_role).sort((a, b) => b[1] - a[1]),
  }
}

export interface ExclusionSummary {
  excludedCents: number
  pendingCents: number
  /** classified into a non-inflow role (transfer, reversal_credit, ...) */
  otherCents: number
  inflowCents: number
  totalCreditsCents: number
  pct: number
}

/** Aggregate over the months actually shown in the cashflow table. */
export function summarizeExclusion(
  rows: Array<{ month: string; inflow_cents: number }>,
  ec: ExcludedCredits | null,
): ExclusionSummary | null {
  if (!ec) return null
  const shown = new Set(rows.map((r) => r.month))
  let excluded = 0
  let pending = 0
  for (const [month, m] of Object.entries(ec.months)) {
    if (!shown.has(month)) continue
    excluded += m.excluded_credit_cents
    pending += m.pending_classification_cents
  }
  const inflow = rows.reduce((s, r) => s + r.inflow_cents, 0)
  return {
    excludedCents: excluded,
    pendingCents: pending,
    otherCents: excluded - pending,
    inflowCents: inflow,
    totalCreditsCents: inflow + excluded,
    pct: excludedSharePct(excluded, inflow),
  }
}

const ROLE_LABELS: Record<string, string> = {
  needs_review: 'pending review',
  unclassified: 'unclassified',
  transfer: 'transfer',
  internal_transfer: 'internal transfer',
  reversal_credit: 'reversal',
}

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role.replace(/_/g, ' ')
}
