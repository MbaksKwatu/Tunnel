'use client'

import { useEffect, useState, useCallback } from 'react'
import { DataTable, Column } from '@/components/DataTable'
import { StatusBadge } from '@/components/StatusBadge'
import { PageHeader } from '@/components/PageHeader'

interface ApiKey {
  id: string
  partner_name: string
  active: boolean
  created_at: string
  [key: string]: unknown
}

function formatDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function ApiKeysPage() {
  const [rows, setRows] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    const res = await fetch('/api/data/api-keys')
    const data = await res.json()
    setRows(data ?? [])
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const columns: Column<ApiKey>[] = [
    { key: 'partner_name', label: 'Partner' },
    {
      key: 'active',
      label: 'Status',
      render: (val) => <StatusBadge status={val ? 'active' : 'inactive'} />,
    },
    {
      key: 'created_at',
      label: 'Created At',
      render: (val) => formatDate(val as string),
    },
  ]

  return (
    <div style={{ padding: '40px' }}>
      <PageHeader
        title="API Keys"
        subtitle={loading ? 'Loading…' : `${rows.length} keys — hashes not shown`}
      />
      <div style={{ background: 'var(--paper)', borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden' }}>
        <DataTable columns={columns} rows={rows} />
      </div>
    </div>
  )
}
