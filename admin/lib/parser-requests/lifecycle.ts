// pds_parser_requests lifecycle (migration 046) — the one vocabulary used by
// the DB CHECK constraint, this admin queue, and the client-facing display.
//
//   new → in_progress → testing → resolved
//                ↑_________|  (a failed test returns the row to in_progress)
//
// `resolved` is never reachable through a plain status PATCH: only through
// resolveParserRequest(), after a passing "Test against submitted file" run,
// or as an override with a written reason (both enforced again by the DB).

export const PARSER_REQUEST_STATUSES = ['new', 'in_progress', 'testing', 'resolved'] as const
export type ParserRequestStatus = (typeof PARSER_REQUEST_STATUSES)[number]

export const STATUS_LABELS: Record<ParserRequestStatus, string> = {
  new: 'New',
  in_progress: 'In progress',
  testing: 'Testing',
  resolved: 'Resolved',
}

// Plain admin status moves. Anything into `testing` happens by running a test;
// anything into `resolved` happens through the resolve flow.
const MANUAL_TRANSITIONS: Record<ParserRequestStatus, ParserRequestStatus[]> = {
  new: ['in_progress'],
  in_progress: ['new'],
  testing: ['in_progress'],
  resolved: [],
}

export function isParserRequestStatus(value: unknown): value is ParserRequestStatus {
  return typeof value === 'string' && (PARSER_REQUEST_STATUSES as readonly string[]).includes(value)
}

export function canManuallyTransition(from: ParserRequestStatus, to: ParserRequestStatus): boolean {
  return MANUAL_TRANSITIONS[from].includes(to)
}

/** Statuses a "Test against submitted file" run may start from. */
export const TESTABLE_STATUSES: ParserRequestStatus[] = ['new', 'in_progress', 'testing']

export const NO_FILE_MESSAGE = 'No file on record — cannot auto-verify, contact requester'

/** Shape returned by parity-ingestion POST /v1/harness. */
export type HarnessResponse = {
  detected: boolean
  status: string
  message?: string | null
  extractor_type?: string
  row_count?: number
  extraction_status?: string
  warning_count?: number
  harness?: Record<string, boolean | string>
}

export type TestVerdict = { passed: boolean; reason: string }

/**
 * The gate. A file passes only if the live detection chain recognised it,
 * extracted at least one row, and run_parser_harness() reports
 * balance_reconciliation === true. "skipped" is not a pass.
 */
export function evaluateHarness(res: HarnessResponse): TestVerdict {
  if (!res.detected) {
    return { passed: false, reason: `Detection miss (${res.status}): ${res.message ?? 'no detector matched this file'}` }
  }
  if (!res.row_count || res.row_count <= 0) {
    return { passed: false, reason: `Detected as ${res.extractor_type ?? 'unknown'} but extracted 0 rows` }
  }
  const recon = res.harness?.balance_reconciliation
  if (recon !== true) {
    const detail = res.harness?.balance_reconciliation_error ?? res.harness?._error
    return {
      passed: false,
      reason: `Reconciliation break: balance_reconciliation=${String(recon)}${detail ? ` (${detail})` : ''}`,
    }
  }
  return {
    passed: true,
    reason: `Detected as ${res.extractor_type}; ${res.row_count} rows; balance_reconciliation passed`,
  }
}
