'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/components/AuthProvider'
import { fetchApi } from '@/lib/api'

export default function DealCreate() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [showEvidence, setShowEvidence] = useState(false)
  const [evidenceOption, setEvidenceOption] = useState<'none' | 'file' | 'db' | 'link'>('none')
  const [fileType, setFileType] = useState<'csv' | 'excel' | 'pdf' | 'image' | 'other'>('csv')
  const [file, setFile] = useState<File | null>(null)
  const [modalMessage, setModalMessage] = useState<string | null>(null)
  const { user } = useAuth()

  const allowedFileTypes: Record<'csv' | 'excel' | 'pdf', string> = {
    csv: '.csv',
    excel: '.xlsx,.xls',
    pdf: '.pdf',
  }

  const handleComingSoon = (message: string) => {
    setModalMessage(message)
  }

  const validateEvidenceSelection = () => {
    if (!showEvidence || evidenceOption === 'none') return true
    if (evidenceOption === 'db' || evidenceOption === 'link') {
      handleComingSoon('This option is coming soon. Please use file upload or skip for now.')
      return false
    }
    if (evidenceOption === 'file') {
      if (fileType === 'image' || fileType === 'other') {
        handleComingSoon('Image and Other uploads are coming soon.')
        return false
      }
      if (!file) {
        setError('Please select a file to upload, or uncheck "Upload deal details now".')
        return false
      }
      return true
    }
    return true
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setSuccessMessage('')
    
    if (!user) {
      setError('Please sign in to create a deal')
      setLoading(false)
      return
    }

    if (!validateEvidenceSelection()) {
      setLoading(false)
      return
    }
    
    const formData = new FormData(e.currentTarget)
    
    try {
      const response = await fetchApi('/api/deals', {
        method: 'POST',
        body: formData
      })
      
      if (!response.ok) {
        let errorMessage = 'Failed to create deal'
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorData.message || errorMessage
        } catch {
          errorMessage = `${response.status}: ${response.statusText}`
        }
        console.error('Deal creation failed:', errorMessage)
        throw new Error(errorMessage)
      }
      
      const result = await response.json()
      console.log('Deal creation response:', result)
      
      if (!result.deal || !result.deal.id) {
        throw new Error('Invalid response: deal ID missing')
      }

      if (showEvidence && evidenceOption === 'file' && file && (fileType === 'csv' || fileType === 'excel' || fileType === 'pdf')) {
        try {
          const evidenceForm = new FormData()
          evidenceForm.append('deal_id', result.deal.id)
          evidenceForm.append('file', file)
          const uploadRes = await fetchApi(`/api/deals/${result.deal.id}/evidence`, {
            method: 'POST',
            body: evidenceForm
          })
          if (!uploadRes.ok) {
            let msg = 'Failed to upload evidence'
            try {
              const data = await uploadRes.json()
              msg = data.detail || data.message || msg
            } catch {
              msg = `${uploadRes.status}: ${uploadRes.statusText}`
            }
            setModalMessage(msg)
          } else {
            setSuccessMessage('Deal created and evidence uploaded successfully.')
          }
        } catch (uploadErr: any) {
          setModalMessage(uploadErr?.message || 'Failed to upload evidence.')
        }
      }
      
      router.push(`/deals/${result.deal.id}`)
    } catch (err: any) {
      console.error('Error creating deal:', err)
      setError(err.message || 'Failed to create deal. Please check console for details.')
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

        {/* Error / Success */}
        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded mb-6">
            {error}
          </div>
        )}
        {successMessage && (
          <div className="bg-green-500/10 border border-green-500 text-green-500 p-4 rounded mb-6">
            {successMessage}
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

          {/* Optional Evidence Section */}
          <div className="border border-gray-700 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm text-gray-200">
                <input
                  type="checkbox"
                  checked={showEvidence}
                  onChange={(e) => {
                    setShowEvidence(e.target.checked)
                    if (!e.target.checked) {
                      setEvidenceOption('none')
                      setFile(null)
                    }
                  }}
                  className="text-blue-500 focus:ring-blue-500 rounded"
                />
                Upload deal details now (optional)
              </label>
              <span className="text-xs text-gray-500">You can skip and add later</span>
            </div>

            {showEvidence && (
              <div className="space-y-3">
                <div className="text-sm text-gray-300">Choose how to add details:</div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <button
                    type="button"
                    onClick={() => setEvidenceOption('file')}
                    className={`w-full border rounded px-3 py-2 text-left ${evidenceOption === 'file' ? 'border-blue-500 text-white' : 'border-gray-700 text-gray-300'}`}
                  >
                    File upload
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEvidenceOption('db')
                      handleComingSoon('Connect to DB is coming soon.')
                    }}
                    className={`w-full border rounded px-3 py-2 text-left ${evidenceOption === 'db' ? 'border-blue-500 text-white' : 'border-gray-700 text-gray-300'}`}
                  >
                    Connect to DB
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEvidenceOption('link')
                      handleComingSoon('Add link is coming soon.')
                    }}
                    className={`w-full border rounded px-3 py-2 text-left ${evidenceOption === 'link' ? 'border-blue-500 text-white' : 'border-gray-700 text-gray-300'}`}
                  >
                    Add link
                  </button>
                </div>

                {evidenceOption === 'file' && (
                  <div className="space-y-3">
                    <div className="text-sm text-gray-300">Select file type:</div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {(['csv', 'excel', 'pdf', 'image', 'other'] as const).map((type) => (
                        <button
                          key={type}
                          type="button"
                          onClick={() => {
                            setFileType(type)
                            if (type === 'image' || type === 'other') {
                              handleComingSoon('Image and Other uploads are coming soon.')
                            }
                          }}
                          className={`w-full border rounded px-3 py-2 text-left capitalize ${
                            fileType === type ? 'border-blue-500 text-white' : 'border-gray-700 text-gray-300'
                          }`}
                        >
                          {type === 'excel' ? 'Excel' : type.toUpperCase()}
                        </button>
                      ))}
                    </div>

                    {(fileType === 'csv' || fileType === 'excel' || fileType === 'pdf') && (
                      <div className="space-y-2">
                        <label className="block text-sm text-gray-300">
                          Choose {fileType.toUpperCase()} file
                        </label>
                        <input
                          type="file"
                          accept={allowedFileTypes[fileType]}
                          onChange={(e) => {
                            const selected = e.target.files?.[0]
                            setFile(selected || null)
                          }}
                          className="w-full text-sm text-gray-300"
                        />
                        <p className="text-xs text-gray-500">Supported: CSV, XLSX/XLS, PDF</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
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
            After creating, you can always upload evidence and run judgment from the deal page
          </p>
        </form>
      </div>

      {/* Modal */}
      {modalMessage && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 max-w-md w-full mx-4 space-y-4">
            <h3 className="text-lg font-bold text-white">Notice</h3>
            <p className="text-sm text-gray-200">{modalMessage}</p>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setModalMessage(null)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded"
              >
                OK
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
