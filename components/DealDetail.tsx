'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Upload, FileText, CheckCircle, Clock, AlertCircle, Play, ArrowLeft, Trash2, Eye } from 'lucide-react'
import JudgmentCards from './JudgmentCards'

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
  id: string
  deal_id: string
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
  score?: number
  recommendation?: 'approve' | 'reject' | 'review'
  confidence?: number
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

  useEffect(() => {
    fetchDealData()
  }, [dealId])

  const fetchDealData = async () => {
    setLoading(true)
    setError('')
    
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const dealResponse = await fetch(`${apiUrl}/api/deals/${dealId}`)
      if (!dealResponse.ok) throw new Error('Failed to load deal')
      const dealData = await dealResponse.json()
      setDeal(dealData.deal || dealData)

      const evidenceResponse = await fetch(`${apiUrl}/api/deals/${dealId}/evidence`)
      if (evidenceResponse.ok) {
        const evidenceData = await evidenceResponse.json()
        setEvidence(evidenceData.evidence || evidenceData || [])
      }

      const judgmentResponse = await fetch(`${apiUrl}/api/deals/${dealId}/judgment`)
      if (judgmentResponse.ok) {
        const judgmentData = await judgmentResponse.json()
        setJudgment(judgmentData.judgment || judgmentData)
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploading(true)
    setError('')
    setSuccess('')

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      for (const file of Array.from(files)) {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('deal_id', dealId)

        const response = await fetch(`${apiUrl}/api/deals/${dealId}/evidence`, {
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

  const handleRunJudgment = async () => {
    setJudging(true)
    setError('')
    setSuccess('')

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/api/deals/${dealId}/judge`, {
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
              
              <div className="mb-4">
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
              </div>

              {uploading && (
                <div className="flex items-center gap-2 text-blue-400">
                  <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin"></div>
                  Uploading files...
                </div>
              )}
            </div>

            <div className="bg-gray-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-white mb-4">Evidence ({evidence.length})</h2>
              
              {evidence.length === 0 ? (
                <p className="text-gray-400">No evidence uploaded yet</p>
              ) : (
                <div className="space-y-3">
                  {evidence.map((item) => (
                    <div key={item.id} className="flex items-center justify-between p-3 bg-gray-700 rounded">
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-gray-400" />
                        <div>
                          <p className="text-white font-medium">{item.file_name}</p>
                          <p className="text-sm text-gray-400">
                            {item.evidence_type} • {new Date(item.upload_date).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button className="p-1 text-gray-400 hover:text-white">
                          <Eye className="w-4 h-4" />
                        </button>
                        <button className="p-1 text-gray-400 hover:text-red-400">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
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
                    {new Date(judgment.created_at).toLocaleString()}
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
