'use client'

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
}

interface Props {
  judgment: Judgment
  onRerun?: () => void
}

export default function JudgmentCards({ judgment, onRerun }: Props) {
  const getReadinessColor = (readiness: string) => {
    switch (readiness) {
      case 'READY': return 'bg-green-500/20 border-green-500 text-green-500'
      case 'CONDITIONALLY_READY': return 'bg-yellow-500/20 border-yellow-500 text-yellow-500'
      case 'NOT_READY': return 'bg-red-500/20 border-red-500 text-red-500'
      default: return 'bg-gray-500/20 border-gray-500 text-gray-400'
    }
  }

  const getAlignmentColor = (alignment: string) => {
    switch (alignment) {
      case 'ALIGNED': return 'bg-green-500/20 border-green-500 text-green-500'
      case 'PARTIALLY_ALIGNED': return 'bg-yellow-500/20 border-yellow-500 text-yellow-500'
      case 'MISALIGNED': return 'bg-red-500/20 border-red-500 text-red-500'
      default: return 'bg-gray-500/20 border-gray-500 text-gray-400'
    }
  }

  const getKillSignalColor = (type: string) => {
    switch (type) {
      case 'NONE': return 'bg-green-500/20 border-green-500 text-green-500'
      case 'POTENTIAL_KILL': return 'bg-yellow-500/20 border-yellow-500 text-yellow-500'
      case 'HARD_KILL': return 'bg-red-500/20 border-red-500 text-red-500'
      default: return 'bg-gray-500/20 border-gray-500 text-gray-400'
    }
  }

  const getConfidenceColor = (confidence: string) => {
    switch (confidence) {
      case 'HIGH': return 'bg-green-500/20 border-green-500 text-green-500'
      case 'MEDIUM': return 'bg-yellow-500/20 border-yellow-500 text-yellow-500'
      case 'LOW': return 'bg-red-500/20 border-red-500 text-red-500'
      default: return 'bg-gray-500/20 border-gray-500 text-gray-400'
    }
  }

  const formatLabel = (text: string) => {
    return text.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }

  return (
    <div className="space-y-6">
      {/* Main Judgment Cards - 2x2 Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Investment Readiness */}
        <div className={`border-2 rounded-lg p-6 ${getReadinessColor(judgment.investment_readiness)}`}>
          <div className="flex items-start justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide opacity-75">
              Investment Readiness
            </h3>
            {judgment.investment_readiness === 'READY' && (
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            )}
            {judgment.investment_readiness === 'NOT_READY' && (
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            )}
          </div>
          <div className="text-3xl font-bold mb-3">
            {formatLabel(judgment.investment_readiness)}
          </div>
          <p className="text-sm opacity-90">
            {judgment.explanations.investment_readiness}
          </p>
        </div>

        {/* Thesis Alignment */}
        <div className={`border-2 rounded-lg p-6 ${getAlignmentColor(judgment.thesis_alignment)}`}>
          <div className="flex items-start justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide opacity-75">
              Thesis Alignment
            </h3>
            {judgment.thesis_alignment === 'ALIGNED' && (
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            )}
          </div>
          <div className="text-3xl font-bold mb-3">
            {formatLabel(judgment.thesis_alignment)}
          </div>
          <p className="text-sm opacity-90">
            {judgment.explanations.thesis_alignment}
          </p>
        </div>

        {/* Kill Signals */}
        <div className={`border-2 rounded-lg p-6 ${getKillSignalColor(judgment.kill_signals.type)}`}>
          <div className="flex items-start justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide opacity-75">
              Kill Signals
            </h3>
            {judgment.kill_signals.type === 'HARD_KILL' && (
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            )}
          </div>
          <div className="text-3xl font-bold mb-3">
            {formatLabel(judgment.kill_signals.type)}
          </div>
          <p className="text-sm opacity-90">
            {judgment.explanations.kill_signals}
          </p>
          {judgment.kill_signals.reason && (
            <div className="mt-3 pt-3 border-t border-current/20">
              <p className="text-xs font-semibold opacity-75">Reason:</p>
              <p className="text-sm">{formatLabel(judgment.kill_signals.reason)}</p>
            </div>
          )}
        </div>

        {/* Confidence Level */}
        <div className={`border-2 rounded-lg p-6 ${getConfidenceColor(judgment.confidence_level)}`}>
          <div className="flex items-start justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide opacity-75">
              Confidence Level
            </h3>
          </div>
          <div className="text-3xl font-bold mb-3">
            {formatLabel(judgment.confidence_level)}
          </div>
          <p className="text-sm opacity-90">
            {judgment.explanations.confidence_level}
          </p>
        </div>
      </div>

      {/* Dimension Scores */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-bold text-white mb-4">Dimension Scores</h3>
        <div className="space-y-4">
          {Object.entries(judgment.dimension_scores).map(([dimension, score]) => (
            <div key={dimension}>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium text-gray-300 capitalize">
                  {formatLabel(dimension)}
                </span>
                <span className="text-sm font-bold text-white">
                  {Math.round(score)}/100
                </span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    score >= 75 ? 'bg-green-500' :
                    score >= 50 ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`}
                  style={{ width: `${score}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Missing Evidence Suggestions */}
      {judgment.missing_evidence && judgment.missing_evidence.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500 rounded-lg p-6">
          <h3 className="text-lg font-bold text-yellow-500 mb-4 flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Suggestions to Improve Score
          </h3>
          <div className="space-y-3">
            {judgment.missing_evidence.map((suggestion, idx) => (
              <div key={idx} className="bg-gray-900/50 rounded p-4">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center text-gray-900 font-bold text-sm">
                    {idx + 1}
                  </div>
                  <div className="flex-1">
                    <p className="text-white font-semibold mb-1">{suggestion.action}</p>
                    <p className="text-sm text-gray-400">{suggestion.impact}</p>
                    <span className="text-xs text-yellow-500 capitalize mt-1 inline-block">
                      {suggestion.type} evidence
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Re-run Judgment Button */}
      {onRerun && (
        <button
          onClick={onRerun}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-semibold transition flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Re-run Judgment
        </button>
      )}
    </div>
  )
}
