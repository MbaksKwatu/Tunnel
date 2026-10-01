import type { SupabaseClient } from '@supabase/supabase-js'
import {
  NO_FILE_MESSAGE,
  TESTABLE_STATUSES,
  evaluateHarness,
  type HarnessResponse,
  type ParserRequestStatus,
} from './lifecycle'
import { casStatus, getParserRequest, logEvent } from './store'

// parity-ingestion is one shared Cloud Run service for staging and prod
// (parity-ingestion/cloudbuild.yaml), so there is a single default URL.
const DEFAULT_INGESTION_URL = 'https://parity-ingestion-121148713552.us-central1.run.app'

export type TestOutcome =
  | { ok: true; passed: boolean; reason: string; status: ParserRequestStatus; result: HarnessResponse }
  | { ok: false; httpStatus: number; error: string }

/**
 * "Test against submitted file": pull the exact file the client submitted
 * (storage_path only — never resolved via document_id, which can point at a
 * deleted pds_documents row), run it through parity-ingestion's live
 * detection chain + run_parser_harness(), and record the verdict.
 *
 * Status: → testing while it runs; a fail sends it back to in_progress; a
 * pass leaves it in testing, ready to be resolved.
 */
export async function testSubmittedFile(
  supabase: SupabaseClient,
  id: string,
  actor: string,
  fetchImpl: typeof fetch = fetch
): Promise<TestOutcome> {
  const row = await getParserRequest(supabase, id)
  if (!row) return { ok: false, httpStatus: 404, error: 'Parser request not found' }
  if (!row.storage_path) return { ok: false, httpStatus: 409, error: NO_FILE_MESSAGE }
  if (!TESTABLE_STATUSES.includes(row.status)) {
    return { ok: false, httpStatus: 409, error: `Cannot test a request that is ${row.status}` }
  }

  if (row.status !== 'testing') {
    const moved = await casStatus(supabase, id, row.status, { status: 'testing' })
    if (!moved) return { ok: false, httpStatus: 409, error: 'Request changed status while starting the test; reload and retry' }
    await logEvent(supabase, { request_id: id, kind: 'status_change', from_status: row.status, to_status: 'testing', actor })
  }

  let result: HarnessResponse
  try {
    const { data: blob, error: dlError } = await supabase.storage.from('parser-requests').download(row.storage_path)
    if (dlError || !blob) throw new Error(`Could not download stored file: ${dlError?.message ?? 'empty'}`)

    const form = new FormData()
    const filename = row.storage_path.split('/').pop() || row.original_filename || 'statement.pdf'
    form.append('file', blob, filename)
    const base = (process.env.PARITY_INGESTION_URL || DEFAULT_INGESTION_URL).replace(/\/$/, '')
    const res = await fetchImpl(`${base}/v1/harness`, { method: 'POST', body: form })
    if (!res.ok) throw new Error(`parity-ingestion /v1/harness returned HTTP ${res.status}: ${(await res.text()).slice(0, 300)}`)
    result = (await res.json()) as HarnessResponse
  } catch (err) {
    result = { detected: false, status: 'TEST_INFRA_ERROR', message: err instanceof Error ? err.message : String(err) }
  }

  const verdict = evaluateHarness(result)
  await logEvent(supabase, {
    request_id: id,
    kind: 'test_run',
    actor,
    detail: { passed: verdict.passed, reason: verdict.reason, storage_path: row.storage_path, result },
  })

  let status: ParserRequestStatus = 'testing'
  if (!verdict.passed) {
    const back = await casStatus(supabase, id, 'testing', { status: 'in_progress' })
    if (back) {
      status = 'in_progress'
      await logEvent(supabase, {
        request_id: id, kind: 'status_change', from_status: 'testing', to_status: 'in_progress', actor,
        reason: `Test failed: ${verdict.reason}`,
      })
    }
  }

  return { ok: true, passed: verdict.passed, reason: verdict.reason, status, result }
}
