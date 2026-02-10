'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Upload, FileText, CheckCircle, Clock, AlertCircle, Play, ArrowLeft, Trash2, Eye } from 'lucide-react'
import JudgmentCards from './JudgmentCards'
import AskParityChat from './AskParityChat'
import { fetchApi } from '@/lib/api'
const ingest = (payload: Record<string, any>) => {
  fetch('http://127.0.0.1:7242/ingest/c06d0fd1-c297-47eb-9e68-2482808d33d7', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => {})
}

interface Deal {
  id: string
  company_name: string
  sector: string
  geography: string
  deal_type: string
  stage: string
  revenue_usd?: number
  status: 'draft' | 'judging' | 'judged'
  created_at: string
  updated_at: string
}

interface Evidence {
  id: string
  deal_id: string
  file_name: string
  file_type: string
  evidence_type: string
  upload_date: string
  extracted_data?: any
}

interface Judgment {
  investment_readiness: string
  thesis_alignment: string
  kill_signals: { type: string; reason?: string; detail?: string }
  confidence_level: string
  dimension_scores: {
    financial: number
    governance: number
    market: number
    team: number
    product: number
    data_confidence: number
  }
  explanations: {
    investment_readiness: string
    thesis_alignment: string
    kill_signals: string
    confidence_level: string
  }
  missing_evidence?: Array<{
    type: string
    action: string
    impact: string
  }>
  created_at: string
}

// The component with proper export
export default function DealDetail({ dealId }: { dealId: string }) {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [judging, setJudging] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [deal, setDeal] = useState<Deal | null>(null)
  const [evidence, setEvidence] = useState<Evidence[]>([])
  const [judgment, setJudgment] = useState<Judgment | null>(null)
  const [evidenceUrl, setEvidenceUrl] = useState('')
  const [urlUploading, setUrlUploading] = useState(false)
  const [summaryEditingId, setSummaryEditingId] = useState<string | null>(null)
  const [summaryDraft, setSummaryDraft] = useState<string>('')

  useEffect(() => {
    fetchDealData()
  }, [dealId])

  const safeJson = async (res: Response) => {
    try {
      return await res.json()
    } catch (err) {
      const text = await res.text().catch(() => '')
      throw new Error(`Failed to parse response (${res.status}) ${text}`)
    }
  }

  const normalizeDeal = (d: any): Deal => ({
    id: d?.id ?? '',
    company_name: d?.company_name ?? 'Unknown',
    sector: d?.sector ?? 'unknown',
    geography: d?.geography ?? 'unknown',
    deal_type: d?.deal_type ?? 'unknown',
    stage: d?.stage ?? 'unknown',
    revenue_usd: typeof d?.revenue_usd === 'number' ? d.revenue_usd : undefined,
    status: d?.status ?? 'draft',
    created_at: d?.created_at ?? '',
    updated_at: d?.updated_at ?? d?.created_at ?? ''
  })

  const normalizeEvidence = (list: any[]): Evidence[] =>
    (list || []).map((ev) => ({
      id: ev?.id ?? '',
      deal_id: ev?.deal_id ?? '',
      file_name: ev?.file_name ?? ev?.original_name ?? 'unknown',
      file_type: ev?.file_type ?? '',
      evidence_type: ev?.evidence_type ?? 'document',
      upload_date: ev?.upload_date ?? ev?.uploaded_at ?? ev?.created_at ?? '',
      extracted_data: ev?.extracted_data,
      // keep compatibility with possible subtype fields
      // evidence_subtype is not used in render; ignore if absent
    }))

  const normalizeJudgment = (j: any): Judgment => ({
    investment_readiness: j?.investment_readiness ?? 'NOT_READY',
    thesis_alignment: j?.thesis_alignment ?? 'MISALIGNED',
    kill_signals: j?.kill_signals ?? { type: 'NONE', reason: '', detail: '' },
    confidence_level: j?.confidence_level ?? 'LOW',
    dimension_scores: {
      financial: j?.dimension_scores?.financial ?? 0,
      governance: j?.dimension_scores?.governance ?? 0,
      market: j?.dimension_scores?.market ?? 0,
      team: j?.dimension_scores?.team ?? 0,
      product: j?.dimension_scores?.product ?? 0,
      data_confidence: j?.dimension_scores?.data_confidence ?? 0,
    },
    explanations: {
      investment_readiness: j?.explanations?.investment_readiness ?? 'No explanation provided.',
      thesis_alignment: j?.explanations?.thesis_alignment ?? 'No explanation provided.',
      kill_signals: j?.explanations?.kill_signals ?? 'No kill signal explanation provided.',
      confidence_level: j?.explanations?.confidence_level ?? 'No confidence explanation provided.',
    },
    missing_evidence: j?.missing_evidence ?? j?.suggested_missing ?? [],
    created_at: j?.created_at ?? ''
  })

  const fetchDealData = async () => {
    setLoading(true)
    setError('')
    
    try {
      ingest({ location: 'components/DealDetail.tsx:fetchDealData', message: 'start', data: { dealId }, runId: 'deal-detail-debug', timestamp: Date.now() })

      const dealResponse = await fetchApi(`/api/deals/${dealId}`)
      console.log('[DealDetail] deal fetch status', dealResponse.status)
      if (!dealResponse.ok) {
        const text = await dealResponse.text().catch(() => '')
        ingest({ location: 'components/DealDetail.tsx:fetchDealData', message: 'deal_fetch_failed', data: { dealId, status: dealResponse.status, body: text }, runId: 'deal-detail-debug', timestamp: Date.now() })
        throw new Error('Failed to load deal')
      }
      const dealData = await safeJson(dealResponse)
      const rawDeal = dealData.deal || dealData
      setDeal(normalizeDeal(rawDeal))
      ingest({ location: 'components/DealDetail.tsx:fetchDealData', message: 'deal_loaded', data: { dealId, deal: dealData?.deal || dealData }, runId: 'deal-detail-debug', timestamp: Date.now() })
      console.log('[DealDetail] deal data', dealData)

      const evidenceResponse = await fetchApi(`/api/deals/${dealId}/evidence`)
      console.log('[DealDetail] evidence fetch status', evidenceResponse.status)
      if (evidenceResponse.ok) {
        const evidenceData = await safeJson(evidenceResponse)
        setEvidence(normalizeEvidence(evidenceData.evidence || evidenceData || []))
        ingest({ location: 'components/DealDetail.tsx:fetchDealData', message: 'evidence_loaded', data: { dealId, count: (evidenceData?.evidence || evidenceData || []).length || 0 }, runId: 'deal-detail-debug', timestamp: Date.now() })
        console.log('[DealDetail] evidence data', evidenceData)
      } else {
        const text = await evidenceResponse.text().catch(() => '')
        ingest({ location: 'components/DealDetail.tsx:fetchDealData', message: 'evidence_fetch_failed', data: { dealId, status: evidenceResponse.status, body: text }, runId: 'deal-detail-debug', timestamp: Date.now() })
      }

      const judgmentResponse = await fetchApi(`/api/deals/${dealId}/judgment`)
      console.log('[DealDetail] judgment fetch status', judgmentResponse.status)
      if (judgmentResponse.ok) {
        const judgmentData = await safeJson(judgmentResponse)
        const rawJudgment = judgmentData.judgment || judgmentData
        setJudgment(rawJudgment ? normalizeJudgment(rawJudgment) : null)
        ingest({ location: 'components/DealDetail.tsx:fetchDealData', message: 'judgment_loaded', data: { dealId, hasJudgment: !!rawJudgment }, runId: 'deal-detail-debug', timestamp: Date.now() })
        console.log('[DealDetail] judgment data', judgmentData)
      } else {
        const text = await judgmentResponse.text().catch(() => '')
        ingest({ location: 'components/DealDetail.tsx:fetchDealData', message: 'judgment_fetch_failed', data: { dealId, status: judgmentResponse.status, body: text }, runId: 'deal-detail-debug', timestamp: Date.now() })
      }
    } catch (err: any) {
      setError(err.message)
      console.error('[DealDetail] fetch error', err)
      ingest({ location: 'components/DealDetail.tsx:fetchDealData', message: 'error', data: { dealId, error: err?.message || String(err) }, runId: 'deal-detail-debug', timestamp: Date.now() })
    } finally {
      setLoading(false)
    }
  }

  const safeDate = (value?: string) => {
    if (!value) return 'N/A'
    const d = new Date(value)
    return isNaN(d.getTime()) ? 'N/A' : d.toLocaleDateString()
  }

  const safeDateTime = (value?: string) => {
    if (!value) return 'N/A'
    const d = new Date(value)
    return isNaN(d.getTime()) ? 'N/A' : d.toLocaleString()
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploading(true)
    setError('')
    setSuccess('')

    try {
      for (const file of Array.from(files)) {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('deal_id', dealId)

        const response = await fetchApi(`/api/deals/${dealId}/evidence`, {
          method: 'POST',
          body: formData
        })

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || `Failed to upload ${file.name}`)
        }
      }

      setSuccess(`Successfully uploaded ${files.length} file(s)`)
      e.target.value = ''
      fetchDealData()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleUrlUpload = async () => {
    const url = evidenceUrl.trim()
    if (!url) return

    setUrlUploading(true)
    setError('')
    setSuccess('')

    try {
      const formData = new FormData()
      formData.append('deal_id', dealId)
      formData.append('url', url)

      const response = await fetchApi('/api/v1/evidence/upload', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to ingest URL evidence')
      }

      setSuccess('URL evidence captured successfully')
      setEvidenceUrl('')
      await fetchDealData()
    } catch (err: any) {
      setError(err.message || 'Failed to ingest URL evidence')
    } finally {
      setUrlUploading(false)
    }
  }

  const handleRunJudgment = async () => {
    setJudging(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetchApi(`/api/deals/${dealId}/judge`, {
        method: 'POST'
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to run judgment')
      }

      setSuccess('Judgment completed successfully')
      fetchDealData()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setJudging(false)
    }
  }

  const handleStartEditSummary = (item: Evidence) => {
    const existingSummary =
      item.extracted_data?.meta?.summary ??
      item.extracted_data?.summary ??
      ''
    setSummaryEditingId(item.id)
    setSummaryDraft(existingSummary)
  }

  const handleSaveSummary = async (item: Evidence) => {
    if (!summaryDraft.trim()) {
      setError('Summary cannot be empty.')
      return
    }
    setError('')
    setSuccess('')
    try {
      const res = await fetchApi(
        `/api/deals/${dealId}/evidence/${item.id}/summary`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ summary: summaryDraft.trim() }),
        }
      )
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to save summary')
      }
      const data = await res.json().catch(() => ({}))
      const updated = data.evidence || data

      // Merge updated evidence into local state
      setEvidence((prev) =>
        prev.map((ev) => (ev.id === item.id ? { ...ev, ...updated } : ev))
      )
      setSuccess('Summary saved')
      setSummaryEditingId(null)
      setSummaryDraft('')
    } catch (err: any) {
      setError(err.message || 'Failed to save summary')
    }
  }

  const getStatusBadge = (status: string) => {
    const styles = {
      draft: 'bg-gray-100 text-gray-800',
      judging: 'bg-yellow-100 text-yellow-800',
      judged: 'bg-green-100 text-green-800'
    }
    
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status as keyof typeof styles]}`}>
        {status}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 p-6">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-center py-20">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <p className="text-gray-400">Loading deal...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!deal) {
    return (
      <div className="min-h-screen bg-gray-900 p-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center py-20">
            <p className="text-gray-400">Deal not found</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-900 p-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <button
            onClick={() => router.back()}
            className="text-gray-400 hover:text-white mb-4 flex items-center gap-2"
          >
            <ArrowLeft className="w-5 h-5" />
            Back to Deals
          </button>
          
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">{deal.company_name}</h1>
              <div className="flex items-center gap-4 text-gray-300">
                <span>{deal.sector}</span>
                <span>•</span>
                <span>{deal.geography}</span>
                <span>•</span>
                <span>{deal.stage}</span>
                {getStatusBadge(deal.status)}
              </div>
            </div>
            
            <button
              onClick={() => router.push(`/deals/${deal.id}/edit`)}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition"
            >
              Edit Deal
            </button>
          </div>
        </div>

        {success && (
          <div className="bg-green-500/10 border border-green-500 text-green-500 p-4 rounded mb-6">
            {success}
          </div>
        )}
        
        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded mb-6">
            {error}
          </div>
        )}

        {evidence.some((ev) => ev.extracted_data?.meta?.unreadable) && (
          <div className="bg-yellow-500/10 border border-yellow-500 text-yellow-200 p-4 rounded mb-6 text-sm">
            Some evidence files were not machine-readable. You can re-upload
            cleaner versions or add a brief manual summary so Parity can still
            use them as context.
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-gray-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-white mb-4">Deal Information</h2>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Company Name:</span>
                  <p className="text-white font-medium">{deal.company_name}</p>
                </div>
                <div>
                  <span className="text-gray-400">Sector:</span>
                  <p className="text-white font-medium">{deal.sector}</p>
                </div>
                <div>
                  <span className="text-gray-400">Geography:</span>
                  <p className="text-white font-medium">{deal.geography}</p>
                </div>
                <div>
                  <span className="text-gray-400">Deal Type:</span>
                  <p className="text-white font-medium">{deal.deal_type}</p>
                </div>
                <div>
                  <span className="text-gray-400">Stage:</span>
                  <p className="text-white font-medium">{deal.stage}</p>
                </div>
                <div>
                  <span className="text-gray-400">Revenue:</span>
                  <p className="text-white font-medium">
                    {deal.revenue_usd ? `$${deal.revenue_usd.toLocaleString()}` : 'Not specified'}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-gray-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-white mb-4">Evidence Upload</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block w-full cursor-pointer">
                    <div className="border-2 border-dashed border-gray-600 rounded-lg p-6 text-center hover:border-blue-500 transition">
                      <Upload className="w-12 h-12 text-gray-400 mx-auto mb-2" />
                      <p className="text-gray-300 mb-2">Drop files here or click to upload</p>
                      <p className="text-sm text-gray-500">PDF, CSV, Excel files supported</p>
                    </div>
                    <input
                      type="file"
                      multiple
                      accept=".pdf,.csv,.xlsx,.xls"
                      onChange={handleFileUpload}
                      disabled={uploading}
                      className="hidden"
                    />
                  </label>
                  {uploading && (
                    <div className="mt-2 flex items-center gap-2 text-blue-400">
                      <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"></div>
                      Uploading files...
                    </div>
                  )}
                </div>

                <div className="border-t border-gray-700 pt-4">
                  <p className="text-sm text-gray-400 mb-2">Or capture evidence from a URL</p>
                  <div className="flex gap-2">
                    <input
                      type="url"
                      placeholder="https://example.com/article-or-report"
                      value={evidenceUrl}
                      onChange={(e) => setEvidenceUrl(e.target.value)}
                      className="flex-1 px-3 py-2 rounded bg-gray-900 border border-gray-700 text-white text-sm"
                    />
                    <button
                      type="button"
                      onClick={handleUrlUpload}
                      disabled={urlUploading || !evidenceUrl.trim()}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white rounded text-sm font-medium"
                    >
                      {urlUploading ? 'Adding…' : 'Add URL'}
                    </button>
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    Parity will fetch the page and store a lightweight text extract as evidence.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-gray-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-white mb-4">Evidence ({evidence.length})</h2>
              
              {evidence.length === 0 ? (
                <p className="text-gray-400">No evidence uploaded yet</p>
              ) : (
                <div className="space-y-3">
                  {evidence.map((item) => {
                    const meta = item.extracted_data?.meta || {}
                    const isUnreadable = !!meta.unreadable
                    const hasSummary = typeof meta.summary === 'string' && meta.summary.trim().length > 0
                    return (
                      <div
                        key={item.id}
                        className="space-y-2 p-3 bg-gray-700 rounded border border-gray-700"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <FileText className="w-5 h-5 text-gray-400" />
                            <div>
                              <p className="text-white font-medium">{item.file_name}</p>
                              <p className="text-sm text-gray-400">
                                {item.evidence_type} • {safeDate(item.upload_date)}
                              </p>
                              {isUnreadable && (
                                <p className="mt-1 text-xs text-yellow-300 flex items-center gap-1">
                                  <AlertCircle className="w-3 h-3" />
                                  We couldn&apos;t reliably read this file (likely a scan or image-based PDF).
                                </p>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {isUnreadable && (
                              <button
                                type="button"
                                onClick={() => handleStartEditSummary(item)}
                                className="px-2 py-1 text-xs rounded bg-blue-600 hover:bg-blue-700 text-white"
                              >
                                {hasSummary ? 'Edit Summary' : 'Add Summary'}
                              </button>
                            )}
                            <button className="p-1 text-gray-400 hover:text-white">
                              <Eye className="w-4 h-4" />
                            </button>
                            <button className="p-1 text-gray-400 hover:text-red-400">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>

                        {hasSummary && summaryEditingId !== item.id && (
                          <div className="mt-1 text-sm text-gray-200 bg-gray-800/70 rounded p-2">
                            <p className="font-semibold text-xs text-gray-400 mb-1">
                              Analyst Summary
                            </p>
                            <p>{meta.summary}</p>
                          </div>
                        )}

                        {summaryEditingId === item.id && (
                          <div className="mt-2 space-y-2">
                            <textarea
                              value={summaryDraft}
                              onChange={(e) => setSummaryDraft(e.target.value)}
                              rows={3}
                              className="w-full px-3 py-2 rounded bg-gray-900 border border-gray-600 text-sm text-white"
                              placeholder="Enter a brief summary of what this document tells you (key facts, context, and caveats)."
                            />
                            <div className="flex gap-2 justify-end">
                              <button
                                type="button"
                                onClick={() => {
                                  setSummaryEditingId(null)
                                  setSummaryDraft('')
                                }}
                                className="px-3 py-1 text-xs rounded bg-gray-700 hover:bg-gray-600 text-gray-100"
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                onClick={() => handleSaveSummary(item)}
                                className="px-3 py-1 text-xs rounded bg-blue-600 hover:bg-blue-700 text-white"
                              >
                                Save Summary
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <AskParityChat dealId={dealId} />

            <div className="bg-gray-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-white mb-4">Actions</h2>
              
              <button
                onClick={handleRunJudgment}
                disabled={judging || evidence.length === 0}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white py-3 rounded font-bold transition flex items-center justify-center gap-2"
              >
                {judging ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Running Judgment...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Run Judgment
                  </>
                )}
              </button>
              
              <p className="text-xs text-gray-500 mt-2 text-center">
                {evidence.length === 0 ? 'Upload evidence first' : 'Requires at least one evidence file'}
              </p>
            </div>

            {judgment && (
              <div className="bg-gray-800 rounded-lg p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-bold text-white">Judgment Results</h2>
                  <span className="text-xs text-gray-400">
                    {safeDateTime(judgment.created_at)}
                  </span>
                </div>
                <JudgmentCards judgment={judgment} onRerun={handleRunJudgment} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
