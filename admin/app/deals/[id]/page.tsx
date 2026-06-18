'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { StatusBadge } from '@/components/StatusBadge'
import { PageHeader } from '@/components/PageHeader'
import { DataTable, Column } from '@/components/DataTable'

interface Deal { id: string; name: string; company_name: string; currency: string; created_at: string; [key: string]: unknown }
interface PdsDocument { id: string; deal_id: string; file_name: string; status: string; created_at: string; [key: string]: unknown }
interface AnalysisRun { id: string; deal_id: string; status: string; created_at: string; [key: string]: unknown }

function formatDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function DealDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [deal, setDeal] = useState<Deal | null>(null)
  const [documents, setDocuments] = useState<PdsDocument[]>([])
  const [runs, setRuns] = useState<AnalysisRun[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    const res = await fetch(`/api/data/deals/${id}`)
    const data = await res.json()
    setDeal(data.deal)
    setDocuments(data.documents ?? [])
    setRuns(data.runs ?? [])
    setLoading(false)
  }, [id])

  useEffect(() => { load() }, [load])

  const docColumns: Column<PdsDocument>[] = [
    { key: 'file_name', label: 'File Name', truncate: true },
    { key: 'status', label: 'Status', render: (val) => <StatusBadge status={val as string} /> },
    { key: 'created_at', label: 'Uploaded', render: (val) => formatDate(val as string) },
  ]

  const runColumns: Column<AnalysisRun>[] = [
    { key: 'id', label: 'Run ID', mono: true, truncate: true },
    { key: 'status', label: 'Status', render: (val) => <StatusBadge status={val as string} /> },
    { key: 'created_at', label: 'Started', render: (val) => formatDate(val as string) },
  ]

  if (loading) return <div style={{ padding: '40px', color: 'var(--t2)' }}>Loading…</div>
  if (!deal) return <div style={{ padding: '40px', color: 'var(--red)' }}>Deal not found.</div>

  return (
    <div style={{ padding: '40px' }}>
      <button onClick={() => router.back()} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--teal)', fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, marginBottom: 24, padding: 0 }}>
        ← Back to deals
      </button>
      <PageHeader title={deal.name} subtitle={deal.company_name} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 40 }}>
        {[
          { label: 'Currency', value: deal.currency },
          { label: 'Deal ID', value: deal.id, mono: true },
          { label: 'Created', value: formatDate(deal.created_at) },
        ].map((item) => (
          <div key={item.label} style={{ background: 'var(--paper)', border: '1px solid var(--border)', borderRadius: 8, padding: '16px 20px' }}>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, letterSpacing: '0.08em', color: 'var(--t2)', marginBottom: 6 }}>{item.label.toUpperCase()}</div>
            <div style={{ fontFamily: item.mono ? "'IBM Plex Mono', monospace" : "'IBM Plex Sans', sans-serif", fontSize: item.mono ? 11 : 14, color: 'var(--t0)' }}>{item.value ?? '—'}</div>
          </div>
        ))}
      </div>
      <section style={{ marginBottom: 40 }}>
        <h2 style={{ fontFamily: "'IBM Plex Serif', serif", fontWeight: 400, fontSize: 18, color: 'var(--navy)', marginBottom: 16 }}>Documents ({documents.length})</h2>
        <div style={{ background: 'var(--paper)', borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden' }}>
          <DataTable columns={docColumns} rows={documents} />
        </div>
      </section>
      <section>
        <h2 style={{ fontFamily: "'IBM Plex Serif', serif", fontWeight: 400, fontSize: 18, color: 'var(--navy)', marginBottom: 16 }}>Analysis Runs ({runs.length})</h2>
        <div style={{ background: 'var(--paper)', borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden' }}>
          <DataTable columns={runColumns} rows={runs} />
        </div>
      </section>
    </div>
  )
}
