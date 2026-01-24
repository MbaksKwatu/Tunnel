'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { fetchApi } from '@/lib/api'

interface Deal {
  id: string
  company_name: string
  sector: string
  geography: string
  stage: string
  status: string
  created_at: string
}

export default function DealList() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deals, setDeals] = useState<Deal[]>([])
  const [filter, setFilter] = useState<string>('all')

  useEffect(() => {
    loadDeals()
  }, [])

  const loadDeals = async () => {
    setLoading(true)
    setError('')

    try {
      const response = await fetchApi('/api/deals')
      
      if (!response.ok) {
        throw new Error('Failed to load deals')
      }

      const data = await response.json()
      setDeals(data.deals || [])
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'judged': return 'bg-green-500/20 text-green-500'
      case 'judging': return 'bg-yellow-500/20 text-yellow-500'
      case 'draft': return 'bg-gray-500/20 text-gray-400'
      default: return 'bg-gray-500/20 text-gray-400'
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric' 
    })
  }

  const formatLabel = (text: string) => {
    return text.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }

  const filteredDeals = deals.filter(deal => {
    if (filter === 'all') return true
    return deal.status === filter
  })

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-gray-400">Loading deals...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Deals</h1>
            <p className="text-gray-400">
              {filteredDeals.length} {filteredDeals.length === 1 ? 'deal' : 'deals'}
            </p>
          </div>

          <button
            onClick={() => router.push('/deals/new')}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold transition flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Deal
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded mb-6">
            {error}
          </div>
        )}

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-6 border-b border-gray-700">
          {[
            { value: 'all', label: 'All Deals' },
            { value: 'draft', label: 'Draft' },
            { value: 'judged', label: 'Judged' }
          ].map(tab => (
            <button
              key={tab.value}
              onClick={() => setFilter(tab.value)}
              className={`px-4 py-2 font-medium transition border-b-2 ${
                filter === tab.value
                  ? 'border-blue-500 text-blue-500'
                  : 'border-transparent text-gray-400 hover:text-gray-300'
              }`}
            >
              {tab.label}
              <span className="ml-2 text-xs">
                ({tab.value === 'all' ? deals.length : deals.filter(d => d.status === tab.value).length})
              </span>
            </button>
          ))}
        </div>

        {/* Deals Table */}
        {filteredDeals.length > 0 ? (
          <div className="bg-gray-800 rounded-lg overflow-hidden">
            {/* Desktop Table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-900 border-b border-gray-700">
                  <tr>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-400 uppercase tracking-wider">
                      Company
                    </th>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-400 uppercase tracking-wider">
                      Sector
                    </th>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-400 uppercase tracking-wider">
                      Geography
                    </th>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-400 uppercase tracking-wider">
                      Stage
                    </th>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-400 uppercase tracking-wider">
                      Created
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {filteredDeals.map(deal => (
                    <tr
                      key={deal.id}
                      onClick={() => router.push(`/deals/${deal.id}`)}
                      className="hover:bg-gray-700/50 cursor-pointer transition"
                    >
                      <td className="px-6 py-4">
                        <div className="text-white font-medium">{deal.company_name}</div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-gray-300 capitalize">{formatLabel(deal.sector)}</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-gray-300 capitalize">{formatLabel(deal.geography)}</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-gray-300 capitalize">{formatLabel(deal.stage)}</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(deal.status)}`}>
                          {formatLabel(deal.status)}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-gray-400 text-sm">{formatDate(deal.created_at)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile Cards */}
            <div className="md:hidden divide-y divide-gray-700">
              {filteredDeals.map(deal => (
                <div
                  key={deal.id}
                  onClick={() => router.push(`/deals/${deal.id}`)}
                  className="p-4 hover:bg-gray-700/50 cursor-pointer transition"
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-white font-semibold">{deal.company_name}</h3>
                    <span className={`inline-flex px-2 py-1 rounded-full text-xs font-semibold ${getStatusColor(deal.status)}`}>
                      {formatLabel(deal.status)}
                    </span>
                  </div>
                  <div className="space-y-1 text-sm text-gray-400">
                    <div className="flex gap-2">
                      <span className="capitalize">{formatLabel(deal.sector)}</span>
                      <span>•</span>
                      <span className="capitalize">{formatLabel(deal.geography)}</span>
                    </div>
                    <div className="flex gap-2">
                      <span className="capitalize">{formatLabel(deal.stage)}</span>
                      <span>•</span>
                      <span>{formatDate(deal.created_at)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          /* Empty State */
          <div className="bg-gray-800 rounded-lg p-12 text-center">
            <svg className="w-16 h-16 text-gray-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-xl font-semibold text-white mb-2">No deals yet</h3>
            <p className="text-gray-400 mb-6">
              {filter === 'all' 
                ? 'Create your first deal to start assessing investments'
                : `No ${filter} deals found` 
              }
            </p>
            <button
              onClick={() => router.push('/deals/new')}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold transition"
            >
              Create First Deal
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
