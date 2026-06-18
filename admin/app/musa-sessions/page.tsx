'use client'

import { useEffect, useState, useCallback } from 'react'
import { DataTable, Column } from '@/components/DataTable'
import { StatusBadge } from '@/components/StatusBadge'
import { PageHeader } from '@/components/PageHeader'

interface MusaSession {
  id: string
  session_id: string
  venture_name: string
  venture_country: string
  status: string
  created_at: string
  error_message: string | null
  [key: string]: unknown
}

function formatDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function MusaSessionsPage() {
  const [rows, setRows] = useState<MusaSession[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    const res = await fetch('/api/data/musa-sessions')
    const data = await res.json()
    setRows(data ?? [])
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const columns: Column<MusaSession>[] = [
    {
      key: 'session_id',
      label: 'Session ID',
      mono: true,
      truncate: true,
      render: (val) => (
        <span title={val as string} style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12 }}>
          {(val as string)?.slice(0, 16)}…
        </span>
      ),
    },
    { key: 'venture_name', label: 'Venture' },
    { key: 'venture_country', label: 'Country' },
    {
      key: 'status',
      label: 'Status',
      render: (val) => <StatusBadge status={val as string} />,
    },
    {
      key: 'created_at',
      label: 'Created At',
      render: (val) => formatDate(val as string),
    },
    {
      key: 'error_message',
      label: 'Error',
      render: (val, row) =>
        val ? (
          <span title={row.error_message ?? ''} style={{ color: 'var(--red)', fontSize: 12, cursor: 'help' }}>
            hover to view
          </span>
        ) : (
          <span style={{ color: 'var(--t3)' }}>—</span>
        ),
    },
  ]

  return (
    <div style={{ padding: '40px' }}>
      <PageHeader
        title="Musa Sessions"
        subtitle={loading ? 'Loading…' : `${rows.length} sessions (last 100)`}
      />
      <div style={{ background: 'var(--paper)', borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden' }}>
        <DataTable columns={columns} rows={rows} />
      </div>
    </div>
  )
}
