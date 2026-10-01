// Run with: npx tsx --test lib/excluded-credits.test.ts
// (the app has no frontend test runner wired into CI; this uses node:test via tsx)
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  type ExcludedCreditsResponseFields,
  excludedSharePct,
  formatSharePct,
  monthExclusion,
  roleLabel,
  summarizeExclusion,
  toExcludedCredits,
} from './excluded-credits'

// Real shape returned by prod GET /analytics/monthly-cashflow (Buildex, trimmed to 2 months)
const response: ExcludedCreditsResponseFields = {
  excluded_credits: [
    { month: '2025-01', excluded_credit_cents: 20_000_000, pending_classification_cents: 20_000_000, by_role: { needs_review: 20_000_000 } },
    { month: '2025-03', excluded_credit_cents: 150_000, pending_classification_cents: 100_000, by_role: { needs_review: 100_000, reversal_credit: 50_000 } },
  ],
  excluded_credits_total_cents: 20_150_000,
  pending_classification_total_cents: 20_100_000,
}

test('missing field means "unavailable" (null), never "nothing excluded"', () => {
  assert.equal(toExcludedCredits(undefined), null)
  assert.equal(toExcludedCredits({}), null)
  assert.notEqual(toExcludedCredits({ excluded_credits: [] }), null) // present but empty = genuinely none
})

test('totals come from the API; months are keyed', () => {
  const ec = toExcludedCredits(response)!
  assert.equal(ec.excludedTotalCents, 20_150_000)
  assert.equal(ec.pendingTotalCents, 20_100_000)
  assert.deepEqual(Object.keys(ec.months), ['2025-01', '2025-03'])
})

test('share is floored and never overstated', () => {
  assert.equal(excludedSharePct(1, 2), 33) // 33.33 -> 33
  assert.equal(excludedSharePct(2, 1), 66) // 66.66 -> 66, not 67
  assert.equal(excludedSharePct(0, 0), 0)
  assert.equal(excludedSharePct(5, 0), 100)
  assert.equal(formatSharePct(1, 0), '<1%')
  assert.equal(formatSharePct(0, 0), '0%')
})

test('inflow + excluded == all credits for the summary', () => {
  const ec = toExcludedCredits(response)!
  const rows = [
    { month: '2025-01', inflow_cents: 80_000_000 },
    { month: '2025-02', inflow_cents: 50_000_000 },
    { month: '2025-03', inflow_cents: 10_000_000 },
  ]
  const s = summarizeExclusion(rows, ec)!
  assert.equal(s.excludedCents, 20_150_000)
  assert.equal(s.pendingCents, 20_100_000)
  assert.equal(s.otherCents, 50_000)
  assert.equal(s.inflowCents, 140_000_000)
  assert.equal(s.totalCreditsCents, 160_150_000)
  assert.equal(s.pct, 12) // 20.15M / 160.15M = 12.58% -> 12
})

test('summary only counts months that are actually displayed', () => {
  const ec = toExcludedCredits(response)!
  const s = summarizeExclusion([{ month: '2025-03', inflow_cents: 10_000_000 }], ec)!
  assert.equal(s.excludedCents, 150_000)
})

test('per-month exclusion: null when none, roles sorted largest first', () => {
  const ec = toExcludedCredits(response)!
  assert.equal(monthExclusion('2025-02', 5, ec), null)
  assert.equal(monthExclusion('2025-02', 5, null), null)
  const m = monthExclusion('2025-03', 10_000_000, ec)!
  assert.equal(m.pct, 1) // 150k / 10.15M = 1.47% -> 1
  assert.deepEqual(m.roles, [['needs_review', 100_000], ['reversal_credit', 50_000]])
})

test('role labels', () => {
  assert.equal(roleLabel('needs_review'), 'pending review')
  assert.equal(roleLabel('some_new_role'), 'some new role')
})
