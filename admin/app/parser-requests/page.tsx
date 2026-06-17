'use client'

import { useEffect, useState, useCallback } from 'react'
import { DataTable, Column } from '@/components/DataTable'
import { StatusBadge } from '@/components/StatusBadge'
import { PageHeader } from '@/components/PageHeader'

type Status = 'pending' | 'in_progress' | 'done'
const STATUS_CYCLE: Status[] = ['pending', 'in_progress', 'done']

interface ParserRequest {
  id: string
  partner: string
  market: string
  bank_name: string
  error_message: string | null
  status: Status
  requested_at: string
  [key: string]: unknown
}

function nextStatus(current: Status): Status {
  const idx = STATUS_CYCLE.indexOf(current)
  return STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length]
}

function formatDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function ParserRequestsPage() {
  const [rows, setRows] = useState<ParserRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState<string | null>(null)

  const load = useCallback(async () => {
    const res = await fetch('/api/data/parser-requests')
    const data = await res.json()
    setRows(data ?? [])
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  async function cycleStatus(row: ParserRequest) {
    const next = nextStatus(row.status)
    setUpdating(row.id)
    await fetch('/api/data/parser-requests', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: row.id, status: next }),
    })
    setRows((prev) => prev.map((r) => r.id === row.id ? { ...r, status: next } : r))
    setUpdating(null)
  }

  const columns: Column<ParserRequest>[] = [
    { key: 'partner', label: 'Partner' },
    { key: 'market', label: 'Market' },
    { key: 'bank_name', label: 'Bank' },
    {
      key: 'status',
      label: 'Status',
      render: (_, row) => (
        <button
          onClick={(e) => { e.stopPropagation(); cycleStatus(row) }}
          disabled={updating === row.id}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, opacity: updating === row.id ? 0.5 : 1 }}
          title="Click to cycle status"
        >
          <StatusBadge status={row.status} />
        </button>
      ),
    },
    {
      key: 'requested_at',
      label: 'Requested At',
      render: (val) => formatDate(val as string),
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
      <PageHeader
        title="Parser Requests"
        subtitle={loading ? 'Loading…' : `${rows.length} requests`}
      />
      <div style={{ background: 'var(--paper)', borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden' }}>
        <DataTable columns={columns} rows={rows} />
      </div>
    </div>
  )
}
