'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { fetchApi } from '@/lib/api'
import ThesisBuilder from './ThesisBuilder'

export default function ThesisSettings() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [thesisData, setThesisData] = useState<any>(null)

  useEffect(() => {
    fetchThesis()
  }, [])

  const fetchThesis = async () => {
    setLoading(true)
    setError('')
    
    try {
      const response = await fetchApi('/api/thesis')
      
      if (!response.ok) {
        throw new Error('Failed to load thesis')
      }
      
      const data = await response.json()
      setThesisData(data.thesis || data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (updatedThesis: any) => {
    setSaving(true)
    setError('')
    setSuccess(false)
    
    try {
      const response = await fetchApi('/api/thesis', {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(updatedThesis)
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to update thesis')
      }
      
      setSuccess(true)
      
      // Hide success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-center py-20">
            <div className="text-center space-y-4">
              <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <p className="text-gray-400">Loading thesis...</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-900 p-6">
      <div className="max-w-4xl mx-auto">
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
          
          <h1 className="text-3xl font-bold text-white mb-2">Investment Thesis</h1>
          <p className="text-gray-400">
            Edit your investment criteria. Changes will affect future deal judgments.
          </p>
        </div>

        {/* Success Message */}
        {success && (
          <div className="bg-green-500/10 border border-green-500 text-green-500 p-4 rounded mb-6 flex items-center gap-3">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Thesis updated successfully!
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded mb-6">
            {error}
          </div>
        )}

        {/* Warning Message */}
        <div className="bg-yellow-500/10 border border-yellow-500 text-yellow-500 p-4 rounded mb-6">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <p className="font-semibold mb-1">Note:</p>
              <p>Changes to your thesis will only affect new judgments. Previously judged deals will keep their original scores.</p>
            </div>
          </div>
        </div>

        {/* Thesis Builder Form */}
        <div className="bg-gray-800 rounded-lg p-6">
          {thesisData ? (
            <ThesisBuilder 
              onSubmit={handleSubmit} 
              initialData={thesisData}
              loading={saving}
            />
          ) : (
            <div className="text-center py-10">
              <p className="text-gray-400 mb-4">No thesis found</p>
              <button
                onClick={() => router.push('/onboarding/thesis')}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded"
              >
                Create Thesis
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
