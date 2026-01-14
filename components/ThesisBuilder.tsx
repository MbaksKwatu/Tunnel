'use client'

import { useState, useEffect } from 'react'

interface ThesisData {
  investment_focus: string
  sector_preferences: string[]
  geography_constraints: string[]
  stage_preferences: string[]
  min_revenue_usd: number | null
  kill_conditions: string[]
  governance_requirements: string[]
  financial_thresholds: {
    min_gross_margin?: number
    max_debt_equity_ratio?: number
  }
  data_confidence_tolerance: string
  impact_requirements: string[]
  weights: {
    financial: number
    governance: number
    market: number
    team: number
    product: number
  }
  name: string
  is_default: boolean
}

interface Props {
  onSubmit: (data: ThesisData) => void
  initialData?: ThesisData
  loading?: boolean
}

export default function ThesisBuilder({ onSubmit, initialData, loading = false }: Props) {
  const [formData, setFormData] = useState<ThesisData>(initialData || {
    investment_focus: '',
    sector_preferences: [],
    geography_constraints: [],
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
  })

  // Update weights based on investment focus
  useEffect(() => {
    if (formData.investment_focus === 'debt') {
      setFormData(prev => ({
        ...prev,
        weights: { financial: 40, governance: 15, market: 15, team: 15, product: 15 }
      }))
    } else if (formData.investment_focus === 'equity') {
      setFormData(prev => ({
        ...prev,
        weights: { financial: 20, governance: 10, market: 30, team: 30, product: 10 }
      }))
    } else if (formData.investment_focus === 'venture_debt') {
      setFormData(prev => ({
        ...prev,
        weights: { financial: 25, governance: 10, market: 25, team: 30, product: 10 }
      }))
    }
  }, [formData.investment_focus])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validation
    if (!formData.investment_focus) {
      alert('Please select investment focus')
      return
    }
    if (formData.sector_preferences.length === 0) {
      alert('Please select at least one sector')
      return
    }
    if (formData.geography_constraints.length === 0) {
      alert('Please select at least one geography')
      return
    }
    
    // Check weights sum to 100
    const totalWeight = Object.values(formData.weights).reduce((a, b) => a + b, 0)
    if (Math.abs(totalWeight - 100) > 0.1) {
      alert('Scoring weights must sum to 100%')
      return
    }
    
    onSubmit(formData)
  }

  const handleCheckboxChange = (field: keyof ThesisData, value: string) => {
    setFormData(prev => {
      const currentArray = prev[field] as string[]
      const newArray = currentArray.includes(value)
        ? currentArray.filter(v => v !== value)
        : [...currentArray, value]
      return { ...prev, [field]: newArray }
    })
  }

  const handleWeightChange = (dimension: keyof typeof formData.weights, value: number) => {
    setFormData(prev => ({
      ...prev,
      weights: { ...prev.weights, [dimension]: value }
    }))
  }

  const totalWeight = Object.values(formData.weights).reduce((a, b) => a + b, 0)

  return (
    <form onSubmit={handleSubmit} className="max-w-4xl mx-auto space-y-8">
      {/* Section 1: Investment Focus */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">1. Investment Focus</h3>
        <div className="space-y-2">
          {['debt', 'equity', 'venture_debt'].map(option => (
            <label key={option} className="flex items-center space-x-2">
              <input
                type="radio"
                name="investment_focus"
                value={option}
                checked={formData.investment_focus === option}
                onChange={e => setFormData(prev => ({ ...prev, investment_focus: e.target.value }))}
                className="w-4 h-4"
              />
              <span className="capitalize">{option.replace('_', ' ')}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Section 2: Sector Preferences */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">2. Sector Preferences</h3>
        <div className="grid grid-cols-2 gap-2">
          {['fintech', 'logistics', 'agritech', 'healthcare', 'manufacturing', 'other'].map(sector => (
            <label key={sector} className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.sector_preferences.includes(sector)}
                onChange={() => handleCheckboxChange('sector_preferences', sector)}
                className="w-4 h-4"
              />
              <span className="capitalize">{sector}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Section 3: Geography */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">3. Geography Constraints</h3>
        <div className="grid grid-cols-2 gap-2">
          {['kenya', 'nigeria', 'south_africa', 'ghana', 'other'].map(geo => (
            <label key={geo} className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.geography_constraints.includes(geo)}
                onChange={() => handleCheckboxChange('geography_constraints', geo)}
                className="w-4 h-4"
              />
              <span className="capitalize">{geo.replace('_', ' ')}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Section 4: Stage Preferences */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">4. Stage Preferences</h3>
        <div className="grid grid-cols-2 gap-2">
          {['pre_revenue', 'early_revenue', 'growth', 'mature'].map(stage => (
            <label key={stage} className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.stage_preferences.includes(stage)}
                onChange={() => handleCheckboxChange('stage_preferences', stage)}
                className="w-4 h-4"
              />
              <span className="capitalize">{stage.replace('_', ' ')}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Section 5: Minimum Revenue */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">5. Minimum Revenue Threshold (USD)</h3>
        <input
          type="number"
          placeholder="e.g., 100000"
          value={formData.min_revenue_usd || ''}
          onChange={e => setFormData(prev => ({ ...prev, min_revenue_usd: e.target.value ? Number(e.target.value) : null }))}
          className="w-full p-2 border rounded bg-gray-800 text-white"
        />
      </div>

      {/* Section 6: Kill Conditions */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">6. Kill Conditions (Deal Breakers)</h3>
        <div className="space-y-2">
          {[
            'no_audited_financials',
            'declining_revenue',
            'high_customer_concentration',
            'negative_cash_flow',
            'missing_license',
            'fraud_indicators'
          ].map(condition => (
            <label key={condition} className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.kill_conditions.includes(condition)}
                onChange={() => handleCheckboxChange('kill_conditions', condition)}
                className="w-4 h-4"
              />
              <span>{condition.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Section 7: Governance */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">7. Governance Requirements</h3>
        <div className="space-y-2">
          {[
            'board_required',
            'shareholder_agreement_required',
            'clean_cap_table',
            'no_founder_supermajority'
          ].map(req => (
            <label key={req} className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.governance_requirements.includes(req)}
                onChange={() => handleCheckboxChange('governance_requirements', req)}
                className="w-4 h-4"
              />
              <span>{req.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Section 8: Financial Thresholds */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">8. Financial Thresholds</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block mb-1">Minimum Gross Margin (%)</label>
            <input
              type="number"
              min="0"
              max="100"
              placeholder="e.g., 25"
              value={formData.financial_thresholds.min_gross_margin || ''}
              onChange={e => setFormData(prev => ({
                ...prev,
                financial_thresholds: { ...prev.financial_thresholds, min_gross_margin: e.target.value ? Number(e.target.value) : undefined }
              }))}
              className="w-full p-2 border rounded bg-gray-800 text-white"
            />
          </div>
          <div>
            <label className="block mb-1">Maximum Debt/Equity Ratio</label>
            <input
              type="number"
              min="0"
              max="10"
              step="0.1"
              placeholder="e.g., 2.5"
              value={formData.financial_thresholds.max_debt_equity_ratio || ''}
              onChange={e => setFormData(prev => ({
                ...prev,
                financial_thresholds: { ...prev.financial_thresholds, max_debt_equity_ratio: e.target.value ? Number(e.target.value) : undefined }
              }))}
              className="w-full p-2 border rounded bg-gray-800 text-white"
            />
          </div>
        </div>
      </div>

      {/* Section 9: Data Confidence Tolerance */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">9. Data Confidence Tolerance</h3>
        <div className="space-y-2">
          {[
            { value: 'high', label: 'High bar (need 80%+ evidence, verified sources)' },
            { value: 'medium', label: 'Medium bar (60%+ evidence OK, some unverified acceptable)' },
            { value: 'low', label: 'Low bar (40%+ if high quality data)' }
          ].map(option => (
            <label key={option.value} className="flex items-center space-x-2">
              <input
                type="radio"
                name="data_confidence_tolerance"
                value={option.value}
                checked={formData.data_confidence_tolerance === option.value}
                onChange={e => setFormData(prev => ({ ...prev, data_confidence_tolerance: e.target.value }))}
                className="w-4 h-4"
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Section 10: Impact Requirements */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">10. Impact Requirements (Optional)</h3>
        <div className="space-y-2">
          {[
            'job_creation',
            'female_founder',
            'underserved_market',
            'environmental_impact'
          ].map(impact => (
            <label key={impact} className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.impact_requirements.includes(impact)}
                onChange={() => handleCheckboxChange('impact_requirements', impact)}
                className="w-4 h-4"
              />
              <span>{impact.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Section 11: Scoring Weights */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">11. Scoring Weights</h3>
        <p className="text-sm text-gray-400">Adjust how much each dimension matters (must sum to 100%)</p>
        <div className="space-y-4">
          {Object.entries(formData.weights).map(([dimension, weight]) => (
            <div key={dimension}>
              <div className="flex justify-between mb-1">
                <label className="capitalize">{dimension.replace('_', ' ')}</label>
                <span className="font-mono">{weight}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={weight}
                onChange={e => handleWeightChange(dimension as keyof typeof formData.weights, Number(e.target.value))}
                className="w-full"
              />
            </div>
          ))}
          <div className={`text-right font-bold ${Math.abs(totalWeight - 100) < 0.1 ? 'text-green-500' : 'text-red-500'}`}>
            Total: {totalWeight.toFixed(0)}% {Math.abs(totalWeight - 100) < 0.1 ? '✓' : '(must equal 100%)'}
          </div>
        </div>
      </div>

      {/* Section 12: Thesis Name */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">12. Thesis Name</h3>
        <input
          type="text"
          value={formData.name}
          onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
          className="w-full p-2 border rounded bg-gray-800 text-white"
          placeholder="Default Thesis"
        />
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={loading || Math.abs(totalWeight - 100) > 0.1}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white py-3 rounded font-bold transition"
      >
        {loading ? 'Saving...' : 'Save Thesis'}
      </button>
    </form>
  )
}
