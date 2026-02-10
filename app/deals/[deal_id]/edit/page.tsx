'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import ProtectedRoute from '@/components/ProtectedRoute'
import { fetchApi } from '@/lib/api'

interface Deal {
  id: string
  company_name: string
  sector: string
  geography: string
  deal_type: string
  stage: string
  revenue_usd?: number
  status?: string
}

interface Props {
  params: {
    deal_id: string
  }
}

function DealEditInner({ dealId }: { dealId: string }) {
  const router = useRouter()
  const [deal, setDeal] = useState<Deal | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    const loadDeal = async () => {
      setLoading(true)
      setError('')
      try {
        const res = await fetchApi(`/api/deals/${dealId}`)
        if (!res.ok) {
          const text = await res.text().catch(() => '')
          throw new Error(text || 'Failed to load deal')
        }
        const data = await res.json()
        const raw = data.deal || data
        setDeal({
          id: raw.id,
          company_name: raw.company_name,
          sector: raw.sector,
          geography: raw.geography,
          deal_type: raw.deal_type,
          stage: raw.stage,
          revenue_usd:
            typeof raw.revenue_usd === 'number'
              ? raw.revenue_usd
              : raw.revenue_usd
              ? Number(raw.revenue_usd)
              : undefined,
          status: raw.status,
        })
      } catch (err: any) {
        setError(err.message || 'Failed to load deal')
      } finally {
        setLoading(false)
      }
    }
    loadDeal()
  }, [dealId])

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')

    const form = e.currentTarget
    const formData = new FormData(form)
    const payload: any = {}
    for (const [key, value] of formData.entries()) {
      const v = (value as string).trim()
      if (!v) continue
      if (key === 'revenue_usd') {
        const num = Number(v)
        if (!Number.isNaN(num)) payload[key] = num
      } else {
        payload[key] = v
      }
    }

    try {
      const res = await fetchApi(`/api/deals/${dealId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || data.message || 'Failed to update deal')
      }
      const data = await res.json()
      const updated = data.deal || data
      setDeal((prev) =>
        prev
          ? {
              ...prev,
              ...updated,
            }
          : updated
      )
      setSuccess('Deal updated successfully.')
      router.push(`/deals/${dealId}`)
    } catch (err: any) {
      setError(err.message || 'Failed to update deal')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 p-6">
        <div className="max-w-2xl mx-auto">
          <p className="text-gray-400">Loading deal…</p>
        </div>
      </div>
    )
  }

  if (!deal) {
    return (
      <div className="min-h-screen bg-gray-900 p-6">
        <div className="max-w-2xl mx-auto">
          <p className="text-gray-400">Deal not found</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-900 p-6">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <button
            onClick={() => router.back()}
            className="text-gray-400 hover:text-white mb-4 flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </button>
          <h1 className="text-3xl font-bold text-white mb-2">Edit Deal</h1>
          <p className="text-gray-400">
            Update company details for investment assessment.
          </p>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded mb-6">
            {error}
          </div>
        )}
        {success && (
          <div className="bg-green-500/10 border border-green-500 text-green-500 p-4 rounded mb-6">
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-gray-800 rounded-lg p-6 space-y-6">
          <div>
            <label htmlFor="company_name" className="block text-sm font-medium text-gray-300 mb-2">
              Company Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="company_name"
              name="company_name"
              defaultValue={deal.company_name}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label htmlFor="sector" className="block text-sm font-medium text-gray-300 mb-2">
              Sector <span className="text-red-500">*</span>
            </label>
            <select
              id="sector"
              name="sector"
              defaultValue={deal.sector}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">Select sector</option>
              <option value="fintech">Fintech</option>
              <option value="logistics">Logistics</option>
              <option value="agritech">Agritech</option>
              <option value="healthcare">Healthcare</option>
              <option value="manufacturing">Manufacturing</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label htmlFor="geography" className="block text-sm font-medium text-gray-300 mb-2">
              Geography <span className="text-red-500">*</span>
            </label>
            <select
              id="geography"
              name="geography"
              defaultValue={deal.geography}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">Select country</option>
              <option value="kenya">Kenya</option>
              <option value="nigeria">Nigeria</option>
              <option value="south_africa">South Africa</option>
              <option value="ghana">Ghana</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label htmlFor="deal_type" className="block text-sm font-medium text-gray-300 mb-2">
              Deal Type <span className="text-red-500">*</span>
            </label>
            <select
              id="deal_type"
              name="deal_type"
              defaultValue={deal.deal_type}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">Select deal type</option>
              <option value="debt">Debt</option>
              <option value="equity">Equity</option>
              <option value="venture_debt">Venture Debt</option>
            </select>
          </div>

          <div>
            <label htmlFor="stage" className="block text-sm font-medium text-gray-300 mb-2">
              Stage <span className="text-red-500">*</span>
            </label>
            <select
              id="stage"
              name="stage"
              defaultValue={deal.stage}
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">Select stage</option>
              <option value="pre_revenue">Pre-Revenue</option>
              <option value="early_revenue">Early Revenue (&lt;$500K)</option>
              <option value="growth">Growth ($500K-$5M)</option>
              <option value="mature">Mature (&gt;$5M)</option>
            </select>
          </div>

          <div>
            <label htmlFor="revenue_usd" className="block text-sm font-medium text-gray-300 mb-2">
              Annual Revenue (USD) <span className="text-gray-500 text-xs">(Optional)</span>
            </label>
            <input
              type="number"
              id="revenue_usd"
              name="revenue_usd"
              min="0"
              step="1000"
              defaultValue={deal.revenue_usd ?? ''}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              placeholder="e.g., 500000"
            />
          </div>

          <button
            type="submit"
            disabled={saving}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white py-3 rounded font-bold transition"
          >
            {saving ? 'Saving changes…' : 'Save Changes'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function EditDealPage({ params }: Props) {
  return (
    <ProtectedRoute>
      <DealEditInner dealId={params.deal_id} />
    </ProtectedRoute>
  )
}

