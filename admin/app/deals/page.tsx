'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { DataTable, Column } from '@/components/DataTable'
import { PageHeader } from '@/components/PageHeader'

interface Deal {
  id: string
  name: string
  company_name: string
  currency: string
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

export default function DealsPage() {
  const [rows, setRows] = useState<Deal[]>([])
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  const load = useCallback(async () => {
    const { data } = await supabase
      .from('pds_deals')
      .select('id, name, company_name, currency, created_at')
      .order('created_at', { ascending: false })
      .limit(100)
    setRows((data as Deal[]) ?? [])
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const columns: Column<Deal>[] = [
    { key: 'name', label: 'Name' },
    { key: 'company_name', label: 'Company' },
    {
      key: 'currency',
      label: 'Currency',
      mono: true,
      render: (val) => <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12 }}>{val as string ?? '—'}</span>,
    },
    {
      key: 'created_at',
      label: 'Created At',
      render: (val) => formatDate(val as string),
    },
  ]

  return (
    <div style={{ padding: '40px 40px' }}>
      <PageHeader
        title="Deal Pipeline"
        subtitle={loading ? 'Loading…' : `${rows.length} deals (last 100)`}
      />
      <div style={{ background: 'var(--paper)', borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden' }}>
        <DataTable
          columns={columns}
          rows={rows}
          onRowClick={(row) => router.push(`/deals/${row.id}`)}
        />
      </div>
    </div>
  )
}
