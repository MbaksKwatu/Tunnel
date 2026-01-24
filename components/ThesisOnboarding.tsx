'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { fetchApi } from '@/lib/api'
import ThesisBuilder from './ThesisBuilder'

export default function ThesisOnboarding() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [step, setStep] = useState<'intro' | 'builder' | 'success'>('intro')

  const handleSubmit = async (thesisData: any) => {
    setLoading(true)
    setError('')
    
    try {
      const response = await fetchApi('/api/thesis', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(thesisData)
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to save thesis')
      }
      
      setStep('success')
      
      // Redirect to dashboard after 2 seconds
      setTimeout(() => {
        router.push('/deals')
      }, 2000)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSkip = () => {
    // Create default thesis and continue
    const defaultThesis = {
      investment_focus: 'debt',
      sector_preferences: ['fintech'],
      geography_constraints: ['kenya'],
      stage_preferences: [],
      min_revenue_usd: null,
      kill_conditions: [],
      governance_requirements: [],
      financial_thresholds: {},
      data_confidence_tolerance: 'medium',
      impact_requirements: [],
      weights: { financial: 40, governance: 15, market: 15, team: 15, product: 15 },
      name: 'Default Thesis',
      is_default: true
    }
    
    handleSubmit(defaultThesis)
  }

  if (step === 'intro') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900 p-6">
        <div className="max-w-2xl w-full bg-gray-800 rounded-lg p-8 space-y-6">
          <div className="text-center space-y-4">
            <h1 className="text-4xl font-bold text-white">Welcome to Parity</h1>
            <p className="text-xl text-gray-300">
              AI-powered investment judgment for emerging markets
            </p>
          </div>

          <div className="space-y-4 text-gray-300">
            <p className="text-lg">
              Before you start assessing deals, let's set up your <strong>Investment Thesis</strong>.
            </p>
            
            <p>
              Your thesis tells Parity what kind of investments you're looking for:
            </p>
            
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li>What sectors and geographies you focus on</li>
              <li>What stage companies you invest in</li>
              <li>Your deal-breaker conditions</li>
              <li>How you weight different evaluation dimensions</li>
            </ul>
            
            <p className="text-sm text-gray-400">
              This is a one-time setup that takes 5-10 minutes. You can edit it later in Settings.
            </p>
          </div>

          <div className="flex gap-4 pt-4">
            <button
              onClick={() => setStep('builder')}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-3 rounded font-bold transition"
            >
              Set Up My Thesis
            </button>
            <button
              onClick={handleSkip}
              className="px-6 bg-gray-700 hover:bg-gray-600 text-white py-3 rounded transition"
            >
              Skip (Use Defaults)
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (step === 'builder') {
    return (
      <div className="min-h-screen bg-gray-900 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">Set Up Your Investment Thesis</h1>
            <p className="text-gray-400">
              Configure your investment criteria. This will guide how Parity judges deals.
            </p>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded mb-6">
              {error}
            </div>
          )}

          <div className="bg-gray-800 rounded-lg p-6">
            <ThesisBuilder onSubmit={handleSubmit} loading={loading} />
          </div>

          <div className="mt-6 text-center">
            <button
              onClick={() => setStep('intro')}
              className="text-gray-400 hover:text-white transition"
            >
              ← Back
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (step === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900 p-6">
        <div className="max-w-md w-full bg-gray-800 rounded-lg p-8 text-center space-y-6">
          <div className="w-16 h-16 bg-green-500 rounded-full flex items-center justify-center mx-auto">
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          
          <div>
            <h2 className="text-2xl font-bold text-white mb-2">Thesis Saved!</h2>
            <p className="text-gray-300">
              Your investment criteria are configured. Ready to assess deals.
            </p>
          </div>
          
          <div className="text-sm text-gray-400">
            Redirecting to dashboard...
          </div>
        </div>
      </div>
    )
  }

  return null
}
