import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { evaluateHarness, canManuallyTransition } from './lifecycle'
import { testSubmittedFile } from './test-submitted-file'
import { resolveParserRequest } from './resolve'
import { fakeSupabase } from './fake-supabase.test-util'

const PASS = {
  detected: true, status: 'DETECTED', extractor_type: 'sbm_pdf', row_count: 412,
  harness: { balance_reconciliation: true, determinism_5x: true, row_coverage: true },
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('evaluateHarness — the resolve gate', () => {
  it('passes only on detection + rows + balance_reconciliation === true', () => {
    expect(evaluateHarness(PASS).passed).toBe(true)
  })
  it('fails a detection miss with the router status', () => {
    const v = evaluateHarness({ detected: false, status: 'UNSUPPORTED_FORMAT', message: 'Bank format not recognised.' })
    expect(v).toEqual({ passed: false, reason: 'Detection miss (UNSUPPORTED_FORMAT): Bank format not recognised.' })
  })
  it('treats "skipped" reconciliation as a fail, not a pass', () => {
    const v = evaluateHarness({ ...PASS, harness: { balance_reconciliation: 'skipped' } })
    expect(v.passed).toBe(false)
    expect(v.reason).toContain('Reconciliation break')
  })
  it('fails zero extracted rows', () => {
    expect(evaluateHarness({ ...PASS, row_count: 0 }).passed).toBe(false)
  })
})

describe('canManuallyTransition', () => {
  it('never allows a plain move into testing or resolved', () => {
    for (const from of ['new', 'in_progress', 'testing'] as const) {
      expect(canManuallyTransition(from, 'resolved')).toBe(false)
      expect(canManuallyTransition(from, 'testing')).toBe(false)
    }
  })
})

describe('testSubmittedFile', () => {
  const file = new Blob(['%PDF-1.4 fake'], { type: 'application/pdf' })

  it('refuses rows with no storage_path, with the no-file message, and never calls ingestion', async () => {
    const { client } = fakeSupabase({ requests: [{ id: 'r1', status: 'in_progress', storage_path: null, document_id: 'deleted-doc' }] })
    const fetchMock = vi.fn()
    const out = await testSubmittedFile(client, 'r1', 'admin@x', fetchMock)
    expect(out).toEqual({ ok: false, httpStatus: 409, error: 'No file on record — cannot auto-verify, contact requester' })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('pass: posts the stored file to /v1/harness, logs the run, leaves status testing', async () => {
    const { client, tables } = fakeSupabase({
      requests: [{ id: 'r1', status: 'in_progress', storage_path: 'abc/sbm.pdf' }],
      files: { 'abc/sbm.pdf': file },
    })
    const fetchMock = vi.fn(async () => jsonResponse(PASS))
    const out = await testSubmittedFile(client, 'r1', 'admin@x', fetchMock as never)
    expect(out).toMatchObject({ ok: true, passed: true, status: 'testing' })
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toMatch(/\/v1\/harness$/)
    expect((init.body as FormData).get('file')).toBeInstanceOf(Blob)
    expect(tables.pds_parser_requests[0].status).toBe('testing')
    const run = tables.pds_parser_request_events.find((e) => e.kind === 'test_run')!
    expect((run.detail as { passed: boolean }).passed).toBe(true)
  })

  it('fail: routes the row back to in_progress with the real reason', async () => {
    const { client, tables } = fakeSupabase({
      requests: [{ id: 'r1', status: 'testing', storage_path: 'abc/x.pdf' }],
      files: { 'abc/x.pdf': file },
    })
    const fetchMock = vi.fn(async () => jsonResponse({ detected: false, status: 'UNSUPPORTED_FORMAT', message: 'Bank format not recognised.' }))
    const out = await testSubmittedFile(client, 'r1', 'admin@x', fetchMock as never)
    expect(out).toMatchObject({ ok: true, passed: false, status: 'in_progress' })
    expect(tables.pds_parser_requests[0].status).toBe('in_progress')
  })

  it('an ingestion outage is a reported fail, not a crash and not a pass', async () => {
    const { client } = fakeSupabase({
      requests: [{ id: 'r1', status: 'in_progress', storage_path: 'abc/x.pdf' }],
      files: { 'abc/x.pdf': file },
    })
    const out = await testSubmittedFile(client, 'r1', 'admin@x', vi.fn(async () => new Response('down', { status: 503 })) as never)
    expect(out).toMatchObject({ ok: true, passed: false })
    if (out.ok) expect(out.reason).toContain('TEST_INFRA_ERROR')
  })
})

describe('resolveParserRequest — the resolve trigger', () => {
  const env = { ...process.env }
  beforeEach(() => {
    process.env.RESEND_API_KEY = 're_test'
    process.env.SLACK_PARSER_WEBHOOK_URL = 'https://hooks.slack.test/x'
  })
  afterEach(() => { process.env = { ...env } })

  function passedRow(extra: Record<string, unknown> = {}) {
    return fakeSupabase({
      requests: [{ id: 'r1', status: 'testing', bank_name: 'SBM Bank', contact_email: 'client@acme.test', created_by: 'u1', ...extra }],
      events: [{ request_id: 'r1', kind: 'test_run', detail: { passed: true, reason: 'ok' }, created_at: '2026-10-01T00:00:00Z' }],
    })
  }

  function routedFetch(slackStatus = 200, resendStatus = 200) {
    return vi.fn(async (url: string, _init?: RequestInit) =>
      url.includes('resend.com')
        ? jsonResponse(resendStatus === 200 ? { id: 'email_123' } : { message: 'boom' }, resendStatus)
        : new Response(slackStatus === 200 ? 'ok' : 'no_service', { status: slackStatus })
    )
  }

  it('refuses test_pass without a passing test on record', async () => {
    const { client, tables } = fakeSupabase({ requests: [{ id: 'r1', status: 'testing' }] })
    const out = await resolveParserRequest(client, 'r1', { basis: 'test_pass', actor: 'a' }, vi.fn() as never)
    expect(out).toMatchObject({ ok: false, httpStatus: 409 })
    expect(tables.pds_parser_requests[0].status).toBe('testing')
  })

  it('refuses test_pass when the latest test failed, even if an earlier one passed', async () => {
    const { client } = fakeSupabase({
      requests: [{ id: 'r1', status: 'testing' }],
      events: [
        { request_id: 'r1', kind: 'test_run', detail: { passed: true }, created_at: '2026-10-01T00:00:00Z' },
        { request_id: 'r1', kind: 'test_run', detail: { passed: false, reason: 'recon' }, created_at: '2026-10-01T01:00:00Z' },
      ],
    })
    const out = await resolveParserRequest(client, 'r1', { basis: 'test_pass', actor: 'a' }, vi.fn() as never)
    expect(out).toMatchObject({ ok: false, httpStatus: 409 })
  })

  it('refuses an override with no reason', async () => {
    const { client } = fakeSupabase({ requests: [{ id: 'r1', status: 'in_progress' }] })
    const out = await resolveParserRequest(client, 'r1', { basis: 'override', reason: '  ', actor: 'a' }, vi.fn() as never)
    expect(out).toMatchObject({ ok: false, httpStatus: 400 })
  })

  it('writes status, then emails the client and posts to Slack, logging all three effects', async () => {
    const { client, tables } = passedRow()
    const fetchMock = routedFetch()
    const out = await resolveParserRequest(client, 'r1', { basis: 'test_pass', actor: 'admin@x' }, fetchMock as never)
    expect(out.ok).toBe(true)
    const row = tables.pds_parser_requests[0]
    expect(row).toMatchObject({ status: 'resolved', resolution_basis: 'test_pass' })
    if (!out.ok) return
    expect(out.effects.email).toMatchObject({ ok: true, to: 'client@acme.test', resend_id: 'email_123' })
    expect(out.effects.slack.ok).toBe(true)
    expect(out.effects.client_status.ok).toBe(true)
    const email = JSON.parse((fetchMock.mock.calls.find(([u]) => String(u).includes("resend"))![1]!).body as string)
    expect(email.to).toEqual(['client@acme.test'])
    expect(email.subject).toBe('Your SBM Bank parser is ready — re-upload your statement')
    expect(tables.pds_parser_request_events.some((e) => e.kind === 'notification')).toBe(true)
  })

  it('a Slack failure does not block the email, and neither undoes the status write', async () => {
    const { client, tables } = passedRow()
    const out = await resolveParserRequest(client, 'r1', { basis: 'test_pass', actor: 'a' }, routedFetch(500) as never)
    expect(out.ok && out.effects.slack.ok).toBe(false)
    expect(out.ok && out.effects.email.ok).toBe(true)
    expect(tables.pds_parser_requests[0].status).toBe('resolved')
  })

  it('an email failure (thrown) does not block Slack', async () => {
    const { client, tables } = passedRow()
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes('resend.com')) throw new Error('network down')
      return new Response('ok')
    })
    const out = await resolveParserRequest(client, 'r1', { basis: 'test_pass', actor: 'a' }, fetchMock as never)
    expect(out.ok && out.effects.email).toMatchObject({ ok: false, detail: 'network down' })
    expect(out.ok && out.effects.slack.ok).toBe(true)
    expect(tables.pds_parser_requests[0].status).toBe('resolved')
  })

  it('falls back to user_profiles contact, then login email, when the row has none', async () => {
    const withProfile = fakeSupabase({
      requests: [{ id: 'r1', status: 'in_progress', bank_name: 'KCB', contact_email: null, created_by: 'u1' }],
      profiles: [{ user_id: 'u1', contact_email: 'chosen@acme.test' }],
      users: { u1: 'login@acme.test' },
    })
    const a = await resolveParserRequest(withProfile.client, 'r1', { basis: 'override', reason: 'verified by hand', actor: 'a' }, routedFetch() as never)
    expect(a.ok && a.effects.email.to).toBe('chosen@acme.test')

    const loginOnly = fakeSupabase({
      requests: [{ id: 'r1', status: 'in_progress', bank_name: 'KCB', contact_email: null, created_by: 'u1' }],
      users: { u1: 'login@acme.test' },
    })
    const b = await resolveParserRequest(loginOnly.client, 'r1', { basis: 'override', reason: 'verified by hand', actor: 'a' }, routedFetch() as never)
    expect(b.ok && b.effects.email.to).toBe('login@acme.test')
    expect(loginOnly.tables.pds_parser_requests[0]).toMatchObject({ resolution_basis: 'override', resolution_note: 'verified by hand' })
  })

  it('never notifies twice: a second resolve on an already-resolved row is refused', async () => {
    const { client } = passedRow()
    const fetchMock = routedFetch()
    await resolveParserRequest(client, 'r1', { basis: 'test_pass', actor: 'a' }, fetchMock as never)
    const calls = fetchMock.mock.calls.length
    const again = await resolveParserRequest(client, 'r1', { basis: 'override', reason: 'x', actor: 'a' }, fetchMock as never)
    expect(again).toMatchObject({ ok: false, httpStatus: 409 })
    expect(fetchMock.mock.calls.length).toBe(calls)
  })

  it('missing env config is reported per effect, not thrown', async () => {
    delete process.env.RESEND_API_KEY
    delete process.env.SLACK_PARSER_WEBHOOK_URL
    const { client, tables } = passedRow()
    const out = await resolveParserRequest(client, 'r1', { basis: 'test_pass', actor: 'a' }, vi.fn() as never)
    expect(out.ok && out.effects.email.detail).toContain('RESEND_API_KEY')
    expect(out.ok && out.effects.slack.detail).toContain('SLACK_PARSER_WEBHOOK_URL')
    expect(tables.pds_parser_requests[0].status).toBe('resolved')
  })
})
