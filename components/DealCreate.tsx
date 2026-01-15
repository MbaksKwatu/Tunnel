'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { autoLogin, getToken } from '@/lib/auth'

export default function DealCreate() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    
    const formData = new FormData(e.currentTarget)
    
    try {
      // Ensure we have a token
      await autoLogin()
      const token = getToken()
      
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/api/deals`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to create deal')
      }
      
      const { deal } = await response.json()
      router.push(`/deals/${deal.id}`)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 p-6">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
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
          
          <h1 className="text-3xl font-bold text-white mb-2">Create New Deal</h1>
          <p className="text-gray-400">
            Add a new company for investment assessment
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded mb-6">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-gray-800 rounded-lg p-6 space-y-6">
          {/* Company Name */}
          <div>
            <label htmlFor="company_name" className="block text-sm font-medium text-gray-300 mb-2">
              Company Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="company_name"
              name="company_name"
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              placeholder="e.g., Acme Logistics"
            />
          </div>

          {/* Sector */}
          <div>
            <label htmlFor="sector" className="block text-sm font-medium text-gray-300 mb-2">
              Sector <span className="text-red-500">*</span>
            </label>
            <select
              id="sector"
              name="sector"
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

          {/* Geography */}
          <div>
            <label htmlFor="geography" className="block text-sm font-medium text-gray-300 mb-2">
              Geography <span className="text-red-500">*</span>
            </label>
            <select
              id="geography"
              name="geography"
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

          {/* Deal Type */}
          <div>
            <label htmlFor="deal_type" className="block text-sm font-medium text-gray-300 mb-2">
              Deal Type <span className="text-red-500">*</span>
            </label>
            <select
              id="deal_type"
              name="deal_type"
              required
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">Select deal type</option>
              <option value="debt">Debt</option>
              <option value="equity">Equity</option>
              <option value="venture_debt">Venture Debt</option>
            </select>
          </div>

          {/* Stage */}
          <div>
            <label htmlFor="stage" className="block text-sm font-medium text-gray-300 mb-2">
              Stage <span className="text-red-500">*</span>
            </label>
            <select
              id="stage"
              name="stage"
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

          {/* Revenue (Optional) */}
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
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              placeholder="e.g., 500000"
            />
            <p className="text-xs text-gray-500 mt-1">
              Enter the company's annual revenue if known
            </p>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white py-3 rounded font-bold transition"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Creating Deal...
              </span>
            ) : (
              'Create Deal'
            )}
          </button>

          <p className="text-sm text-gray-500 text-center">
            After creating, you'll upload evidence and run judgment
          </p>
        </form>
      </div>
    </div>
  )
}
