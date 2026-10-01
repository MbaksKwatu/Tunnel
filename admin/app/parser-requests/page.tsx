'use client'

import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { DataTable, Column } from '@/components/DataTable'
import { StatusBadge } from '@/components/StatusBadge'
import { PageHeader } from '@/components/PageHeader'
import { EnvBadge } from '@/components/EnvBadge'
import { ENV_HEADER } from '@/lib/env-header'
import { toEAT, timeSince, refreshedLabel, downloadCSV } from './utils'
import {
  NO_FILE_MESSAGE,
  PARSER_REQUEST_STATUSES,
  STATUS_LABELS,
  TESTABLE_STATUSES,
  type ParserRequestStatus,
} from '@/lib/parser-requests/lifecycle'

type LastTest = { passed: boolean; reason: string; created_at: string } | null

// Raw shape from `parser_requests` ("auto" / Musa table)
interface AutoRequest {
  id: string
  partner: string
  market: string
  bank_name: string
  document_url: string | null
  session_id?: string | null
  deal_id?: string | null
  deal_name?: string | null
  error_message: string | null
  // Musa's own pipeline states (pending / expired / resolved) — read-only here.
  status: string
  requested_at: string
  updated_at?: string
  [key: string]: unknown
}

// Raw shape from `pds_parser_requests` ("manual" table)
interface ManualRequest {
  id: string
  deal_id?: string | null
  deal_name?: string | null
  document_id?: string | null
  original_filename: string | null
  bank_name: string | null
  country: string | null
  account_type?: string | null
  notes?: string | null
  error_type?: string | null
  error_message: string | null
  created_at: string
  status: ParserRequestStatus
  storage_path?: string | null
  signed_url?: string | null
  contact_email?: string | null
  last_test?: LastTest
  [key: string]: unknown
}

// Normalized row shape used for rendering, filtering, and CSV export
interface Row {
  id: string
  source: 'Auto · Musa' | 'Manual'
  partner: string
  market: string
  bank_display: string
  deal_display: string
  error_message: string | null
  status: string
  date: string
  isAuto: boolean
  hasFile: boolean
  signedUrl: string | null
  contactEmail: string | null
  lastTest: LastTest
  [key: string]: unknown
}

type ApiResponse =
  | AutoRequest[]
  | { auto: AutoRequest[]; manual: ManualRequest[]; env?: string; fetched_at?: string }

function normalize(data: ApiResponse): Row[] {
  let auto: AutoRequest[] = []
  let manual: ManualRequest[] = []

  if (Array.isArray(data)) {
    auto = data
  } else if (data && typeof data === 'object') {
    auto = Array.isArray(data.auto) ? data.auto : []
    manual = Array.isArray(data.manual) ? data.manual : []
  }

  // deal_name comes pre-resolved from /api/data/parser-requests (joined
  // server-side against pds_deals so this page never needs the service-role
  // key). Falls back to the raw deal_id (still useful for lookup) and then
  // "—" for rows with no deal at all.
  const autoRows: Row[] = auto.map((r) => ({
    id: r.id,
    source: 'Auto · Musa',
    partner: r.partner ?? '—',
    market: r.market ?? '—',
    bank_display: r.bank_name ?? '—',
    deal_display: r.deal_name || r.deal_id || '—',
    error_message: r.error_message ?? null,
    status: r.status,
    date: r.requested_at,
    isAuto: true,
    hasFile: false,
    signedUrl: null,
    contactEmail: null,
    lastTest: null,
  }))

  const manualRows: Row[] = manual.map((r) => ({
    id: r.id,
    source: 'Manual',
    partner: 'Manual',
    market: r.country ?? '—',
    bank_display: r.bank_name ?? r.original_filename ?? '—',
    deal_display: r.deal_name || r.deal_id || '—',
    error_message: r.error_message ?? null,
    status: r.status,
    date: r.created_at,
    isAuto: false,
    hasFile: Boolean(r.storage_path),
    signedUrl: r.signed_url ?? null,
    contactEmail: r.contact_email ?? null,
    lastTest: r.last_test ?? null,
  }))

  return [...autoRows, ...manualRows].sort((a, b) => {
    const ta = a.date ? new Date(a.date).getTime() : 0
    const tb = b.date ? new Date(b.date).getTime() : 0
    return tb - ta
  })
}

const PARTNER_FILTERS = ['All', 'Musa', 'GBFund', 'Manual'] as const
// Status filters apply to client (pds_parser_requests) rows — the only rows
// with an actionable lifecycle. Musa rows stay visible under "All".
const STATUS_FILTERS = ['All', ...PARSER_REQUEST_STATUSES] as const

function actionStyle(color: string, disabled = false): React.CSSProperties {
  return {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 4,
    border: `1px solid ${color}`,
    background: 'transparent',
    color,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    whiteSpace: 'nowrap',
  }
}

type Notice = { tone: 'ok' | 'warn' | 'alert'; title: string; lines: string[] }

function chipStyle(active: boolean): React.CSSProperties {
  return {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 11,
    letterSpacing: '0.04em',
    padding: '4px 10px',
    borderRadius: 4,
    border: '1px solid var(--teal)',
    background: active ? 'var(--teal)' : 'transparent',
    color: active ? '#fff' : 'var(--teal)',
    cursor: 'pointer',
  }
}

function severityColor(severity: 'ok' | 'warn' | 'alert'): string {
  if (severity === 'alert') return 'var(--red)'
  if (severity === 'warn') return 'var(--amber)'
  return 'var(--green)'
}

export default function ParserRequestsPage() {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState<string | null>(null)
  const [partnerFilter, setPartnerFilter] = useState<typeof PARTNER_FILTERS[number]>('All')
  const [statusFilter, setStatusFilter] = useState<typeof STATUS_FILTERS[number]>('All')
  const [notice, setNotice] = useState<Notice | null>(null)
  const [lastFetched, setLastFetched] = useState<string>(() => new Date().toISOString())
  const [env, setEnv] = useState<string | null>(null)
  const [, setTick] = useState(0)
  const refreshIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const tickIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    const res = await fetch('/api/data/parser-requests')
    const data: ApiResponse = await res.json()
    setRows(normalize(data))
    setEnv(res.headers.get(ENV_HEADER))
    setLoading(false)
    setLastFetched(new Date().toISOString())
  }, [])

  useEffect(() => {
    load()
    refreshIntervalRef.current = setInterval(load, 60000)
    tickIntervalRef.current = setInterval(() => setTick((t) => t + 1), 1000)
    return () => {
      if (refreshIntervalRef.current) clearInterval(refreshIntervalRef.current)
      if (tickIntervalRef.current) clearInterval(tickIntervalRef.current)
    }
  }, [load])

  async function act(row: Row, label: string, run: () => Promise<Response>, describe: (body: Record<string, unknown>) => Notice) {
    setUpdating(row.id)
    try {
      const res = await run()
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        setNotice({ tone: 'alert', title: `${label} — ${row.bank_display}`, lines: [String(body.error ?? `HTTP ${res.status}`)] })
      } else {
        setNotice(describe(body))
      }
    } catch (err) {
      setNotice({ tone: 'alert', title: `${label} — ${row.bank_display}`, lines: [err instanceof Error ? err.message : String(err)] })
    } finally {
      setUpdating(null)
      load()
    }
  }

  function moveStatus(row: Row, to: ParserRequestStatus) {
    return act(row, `Move to ${STATUS_LABELS[to]}`, () => fetch('/api/data/parser-requests', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: row.id, status: to }),
    }), () => ({ tone: 'ok', title: `${row.bank_display}: ${STATUS_LABELS[row.status as ParserRequestStatus]} → ${STATUS_LABELS[to]}`, lines: [] }))
  }

  function runTest(row: Row) {
    setNotice({ tone: 'warn', title: `Testing ${row.bank_display} against the submitted file…`, lines: ['Runs detection + run_parser_harness(); a long statement can take a few minutes.'] })
    return act(row, 'Test against submitted file', () => fetch(`/api/data/parser-requests/${row.id}/test`, { method: 'POST' }), (body) => ({
      tone: body.passed ? 'ok' : 'alert',
      title: `${row.bank_display}: test ${body.passed ? 'PASSED' : 'FAILED'}`,
      lines: [String(body.reason ?? ''), body.passed ? 'Ready to mark resolved.' : 'Moved back to In progress.'],
    }))
  }

  function describeResolve(row: Row) {
    return (body: Record<string, unknown>): Notice => {
      const effects = (body.effects ?? {}) as Record<string, { ok: boolean; detail: string }>
      const lines = Object.entries(effects).map(([k, v]) => `${v.ok ? '✓' : '✗'} ${k}: ${v.detail}`)
      const allOk = Object.values(effects).every((v) => v.ok)
      return { tone: allOk ? 'ok' : 'warn', title: `${row.bank_display}: resolved`, lines }
    }
  }

  function resolveAfterPass(row: Row) {
    if (!window.confirm(`Mark ${row.bank_display} resolved? This emails the client and posts to Slack.`)) return
    return act(row, 'Mark resolved', () => fetch(`/api/data/parser-requests/${row.id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ basis: 'test_pass' }),
    }), describeResolve(row))
  }

  function overrideResolve(row: Row) {
    const reason = window.prompt(`Override: resolve ${row.bank_display} WITHOUT a passing test.\nThis emails the client. Reason (required, logged):`)
    if (!reason?.trim()) return
    return act(row, 'Override resolve', () => fetch(`/api/data/parser-requests/${row.id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ basis: 'override', reason }),
    }), describeResolve(row))
  }

  const filteredRows = useMemo(() => {
    return rows.filter((r) => {
      if (partnerFilter !== 'All') {
        if (partnerFilter === 'Manual') {
          if (r.isAuto) return false
        } else {
          if (!r.isAuto || r.partner?.toLowerCase() !== partnerFilter.toLowerCase()) return false
        }
      }
      if (statusFilter !== 'All') {
        if (r.isAuto || r.status !== statusFilter) return false
      }
      return true
    })
  }, [rows, partnerFilter, statusFilter])

  const summary = useMemo(() => {
    const client = rows.filter((r) => !r.isAuto)
    const counts = PARSER_REQUEST_STATUSES.map((s) => `${client.filter((r) => r.status === s).length} ${STATUS_LABELS[s].toLowerCase()}`)
    return `Client requests: ${counts.join(' · ')}`
  }, [rows])

  function handleDownloadCSV() {
    const csvRows = filteredRows.map((r) => ({
      id: r.id,
      source: r.source,
      partner: r.partner,
      deal: r.deal_display,
      market: r.market,
      bank_display: r.bank_display,
      error_message: r.error_message ?? '',
      status: r.status ?? '',
      date: r.date,
      time_pending_label: timeSince(r.date).label,
    }))
    downloadCSV(csvRows, `parser-requests-${new Date().toISOString().slice(0, 10)}.csv`)
  }

  const columns: Column<Row>[] = [
    {
      key: 'source',
      label: 'Source',
      render: (_, row) => (
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          padding: '2px 8px',
          borderRadius: 4,
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 11,
          fontWeight: 500,
          letterSpacing: '0.04em',
          border: '1px solid',
          background: row.isAuto ? 'var(--teal-d)' : 'var(--bg2)',
          color: row.isAuto ? 'var(--teal)' : 'var(--t1)',
          borderColor: row.isAuto ? 'rgba(13,148,136,0.20)' : 'var(--border)',
        }}>
          {row.source}
        </span>
      ),
    },
    { key: 'partner', label: 'Partner/Bank', render: (_, row) => row.isAuto ? row.partner : row.bank_display },
    { key: 'deal_display', label: 'Deal' },
    { key: 'market', label: 'Market/Country' },
    {
      key: 'status',
      label: 'Status',
      render: (_, row) => {
        if (row.isAuto) {
          return <span title="Musa pipeline state — managed by its own 24h SLA sweep"><StatusBadge status={row.status} /></span>
        }
        const st = row.status as ParserRequestStatus
        const busy = updating === row.id
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }} onClick={(e) => e.stopPropagation()}>
            <StatusBadge status={STATUS_LABELS[st] ?? st} />
            {st !== 'resolved' && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {st === 'new' && (
                  <button disabled={busy} onClick={() => moveStatus(row, 'in_progress')} style={actionStyle('var(--teal)', busy)}>Start</button>
                )}
                {TESTABLE_STATUSES.includes(st) && (
                  <button
                    disabled={busy || !row.hasFile}
                    onClick={() => runTest(row)}
                    title={row.hasFile ? 'Run the stored file through detection + run_parser_harness()' : NO_FILE_MESSAGE}
                    style={actionStyle('var(--teal)', busy || !row.hasFile)}
                  >
                    Test against submitted file
                  </button>
                )}
                {st === 'testing' && row.lastTest?.passed && (
                  <button disabled={busy} onClick={() => resolveAfterPass(row)} style={actionStyle('var(--green)', busy)}>Mark resolved</button>
                )}
                {st === 'testing' && (
                  <button disabled={busy} onClick={() => moveStatus(row, 'in_progress')} style={actionStyle('var(--t2)', busy)}>Back to in progress</button>
                )}
                <button disabled={busy} onClick={() => overrideResolve(row)} style={actionStyle('var(--amber)', busy)} title="Resolve without a passing test — reason required">Override…</button>
              </div>
            )}
            {!row.hasFile && st !== 'resolved' && (
              <span style={{ fontSize: 11, color: 'var(--amber)' }}>{NO_FILE_MESSAGE}</span>
            )}
          </div>
        )
      },
    },
    {
      key: 'last_test',
      label: 'Last Test',
      render: (_, row) => {
        if (row.isAuto) return <span style={{ color: 'var(--t3)' }}>—</span>
        if (!row.lastTest) return <span style={{ color: 'var(--t3)', fontSize: 12 }}>{row.hasFile ? 'not run' : 'no file'}</span>
        return (
          <span style={{ fontSize: 12, color: row.lastTest.passed ? 'var(--green)' : 'var(--red)' }} title={toEAT(row.lastTest.created_at)}>
            {row.lastTest.passed ? '✓ pass' : '✗ fail'} — {row.lastTest.reason}
          </span>
        )
      },
    },
    {
      key: 'file',
      label: 'File / Contact',
      render: (_, row) => row.isAuto ? <span style={{ color: 'var(--t3)' }}>—</span> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, fontSize: 12 }}>
          {row.signedUrl
            ? <a href={row.signedUrl} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} style={{ color: 'var(--teal)' }}>download</a>
            : <span style={{ color: 'var(--t3)' }}>no file</span>}
          <span style={{ color: row.contactEmail ? 'var(--t1)' : 'var(--t3)' }}>{row.contactEmail ?? 'no contact email'}</span>
        </div>
      ),
    },
    {
      key: 'time_pending',
      label: 'Time Pending',
      render: (_, row) => {
        const { label, severity } = timeSince(row.date)
        return <span style={{ color: severityColor(severity), fontFamily: "'IBM Plex Mono', monospace", fontSize: 12 }}>{label}</span>
      },
    },
    {
      key: 'date',
      label: 'Requested At',
      render: (val) => toEAT(val as string),
    },
    {
      key: 'error_message',
      label: 'Error',
      truncate: true,
      render: (val) => val
        ? <span style={{ color: 'var(--red)', fontSize: 12 }}>{val as string}</span>
        : <span style={{ color: 'var(--t3)' }}>—</span>,
    },
  ]

  return (
    <div style={{ padding: '40px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <PageHeader
          title="Parser Requests"
          subtitle={loading ? 'Loading…' : summary}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
          {env === 'prod' && <EnvBadge env="prod" />}
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: 'var(--t2)' }}>
            {refreshedLabel(lastFetched)}
          </span>
          <button
            onClick={() => load()}
            title="Refresh"
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 12,
              padding: '6px 10px',
              borderRadius: 4,
              border: '1px solid var(--border)',
              background: 'var(--paper)',
              color: 'var(--t1)',
              cursor: 'pointer',
            }}
          >
            ↻
          </button>
          <button
            onClick={handleDownloadCSV}
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 12,
              padding: '6px 10px',
              borderRadius: 4,
              border: '1px solid var(--teal)',
              background: 'transparent',
              color: 'var(--teal)',
              cursor: 'pointer',
            }}
          >
            Download CSV
          </button>
        </div>
      </div>

      {notice && (
        <div style={{
          marginBottom: 16, padding: '10px 14px', borderRadius: 6, border: '1px solid var(--border)',
          borderLeft: `3px solid ${severityColor(notice.tone)}`, background: 'var(--paper)', fontSize: 13,
          display: 'flex', justifyContent: 'space-between', gap: 12,
        }}>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--t0)' }}>{notice.title}</div>
            {notice.lines.filter(Boolean).map((l, i) => (
              <div key={i} style={{ color: 'var(--t1)', fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, marginTop: 4 }}>{l}</div>
            ))}
          </div>
          <button onClick={() => setNotice(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--t2)' }}>×</button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {PARTNER_FILTERS.map((f) => (
            <button key={f} onClick={() => setPartnerFilter(f)} style={chipStyle(partnerFilter === f)}>
              {f}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {STATUS_FILTERS.map((f) => (
            <button key={f} onClick={() => setStatusFilter(f)} style={chipStyle(statusFilter === f)}>
              {f === 'All' ? 'All' : STATUS_LABELS[f]}
            </button>
          ))}
        </div>
      </div>

      <div style={{ background: 'var(--paper)', borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden' }}>
        <DataTable columns={columns} rows={filteredRows} />
      </div>
    </div>
  )
}
