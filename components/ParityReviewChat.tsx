'use client'

import { useState, useEffect, useRef, useCallback, memo } from 'react'
import { askParityReview } from '@/lib/v1-api'

// ── Lightweight markdown → HTML ────────────────────────────────────────────

function mdToHtml(md: string): string {
  return md
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^## (.+)$/gm, '<h3 style="font-size:13px;font-weight:700;margin:12px 0 4px;color:#A5B4FC">$1</h3>')
    .replace(/^### (.+)$/gm, '<h4 style="font-size:12px;font-weight:700;margin:10px 0 3px;color:#94A3B8">$1</h4>')
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #1E2A3A;margin:8px 0"/>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#E2E8F0">$1</strong>')
    .replace(/^• (.+)$/gm, '<div style="padding-left:12px;margin:2px 0">· $1</div>')
    .replace(/^- (.+)$/gm, '<div style="padding-left:12px;margin:2px 0">· $1</div>')
    .replace(/[📊💡🏦📈📉⚠️✅❌🔍💰📋🏢📌🔎💼📁📂🗂️📄📃📑🔔🔕]/gu, '')
    .replace(/\n{2,}/g, '<br/>')
}

// ── Types ────────────────────────────────────────────────────────────────────

type ChatMessage = { role: 'analyst' | 'parity'; text: string; time: string }

interface Props {
  dealId: string
  corpusReady: boolean
  txnTotal: number
  statementCount: number
}

// ── Suggestion chips ─────────────────────────────────────────────────────────

const SUGGESTION_CHIPS = [
  'What is the average monthly net cashflow?',
  'Which entities represent the highest concentration risk?',
  'Are there any irregular payroll patterns?',
  'What is the peak debt service coverage ratio?',
]

// ── Component ────────────────────────────────────────────────────────────────

function ParityReviewChat({ dealId, corpusReady, txnTotal, statementCount }: Props) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [conversationHistory, setConversationHistory] = useState<Array<{ role: string; content: unknown }>>([])
  const [proactiveTriggered, setProactiveTriggered] = useState(false)
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll on new messages
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [chatHistory])

  // Auto-trigger proactive analysis
  useEffect(() => {
    if (corpusReady && !proactiveTriggered && chatHistory.length === 0) {
      setProactiveTriggered(true)
      doAsk('start')
    }
  }, [corpusReady, proactiveTriggered, chatHistory.length])

  const doAsk = useCallback(async (overrideMessage?: string) => {
    const message = overrideMessage || question.trim()
    if (!message || loading) return
    const now = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    if (!overrideMessage) {
      setChatHistory(prev => [...prev, { role: 'analyst', text: message, time: now }])
      setQuestion('')
    }
    setLoading(true)
    try {
      const result = await askParityReview(dealId, message, conversationHistory)
      const answerTime = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      setChatHistory(prev => [...prev, { role: 'parity', text: result.response, time: answerTime }])
      setConversationHistory(result.conversation_history)
    } catch (e) {
      const errText = e instanceof Error ? e.message : 'Request failed'
      const errTime = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      setChatHistory(prev => [...prev, { role: 'parity', text: errText, time: errTime }])
    } finally {
      setLoading(false)
    }
  }, [question, loading, dealId, conversationHistory])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); doAsk() }
  }

  const copyToClipboard = (text: string, idx: number) => {
    // Strip HTML/markdown for clean paste
    const clean = text
      .replace(/\*\*/g, '')
      .replace(/^## /gm, '')
      .replace(/^### /gm, '')
      .replace(/^---$/gm, '---')
      .replace(/[📊💡🏦📈📉⚠️✅❌🔍💰📋🏢📌🔎💼📁📂🗂️📄📃📑🔔🔕]/gu, '')
      .trim()
    navigator.clipboard.writeText(clean)
    setCopiedIdx(idx)
    setTimeout(() => setCopiedIdx(null), 2000)
  }

  return (
    <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
      <style>{`
        @keyframes parityDot {
          0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
      `}</style>

      {/* Left: Chat area */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: '#CBD5E1', letterSpacing: '0.02em' }}>Parity Review</span>
          <span style={{
            fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', padding: '2px 8px', borderRadius: 3,
            background: corpusReady ? 'rgba(74,222,128,0.12)' : 'rgba(99,102,241,0.12)',
            color: corpusReady ? '#4ADE80' : '#818CF8',
            border: `1px solid ${corpusReady ? 'rgba(74,222,128,0.25)' : 'rgba(99,102,241,0.25)'}`,
          }}>
            {corpusReady ? 'READY' : 'PENDING'}
          </span>
        </div>

        {/* Corpus description card */}
        {!corpusReady && (
          <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: '14px 18px', marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: '#4A5568', lineHeight: 1.6 }}>
              Parity Intelligence is available once analysis completes. Run analysis from the Documents tab to activate.
            </div>
          </div>
        )}
        {corpusReady && chatHistory.length === 0 && !loading && (
          <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: '14px 18px', marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#374151', letterSpacing: '0.08em', marginBottom: 6 }}>CORPUS LOADED</div>
            <div style={{ fontSize: 12, color: '#4A5568', lineHeight: 1.6 }}>
              {txnTotal > 0 ? `${txnTotal} transactions` : 'Transactions'} across {statementCount || 1} statement{statementCount !== 1 ? 's' : ''} indexed. Ask any question about this borrower&apos;s financial history.
            </div>
          </div>
        )}

        {/* Chat history */}
        <div ref={scrollRef} style={{ maxHeight: 500, overflowY: 'auto', marginBottom: 16 }}>
          {chatHistory.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {chatHistory.map((msg, i) => (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: msg.role === 'analyst' ? 'flex-end' : 'flex-start' }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span style={{ fontSize: 9, fontWeight: 700, color: msg.role === 'analyst' ? '#6366F1' : '#4ADE80', letterSpacing: '0.1em', fontFamily: "'IBM Plex Mono', monospace" }}>
                      {msg.role === 'analyst' ? 'ANALYST' : 'PARITY'}
                    </span>
                    <span style={{ fontSize: 9, color: '#2D3748', fontFamily: "'IBM Plex Mono', monospace" }}>{msg.time}</span>
                  </div>
                  <div style={{
                    maxWidth: '85%', position: 'relative',
                    background: msg.role === 'analyst' ? 'rgba(99,102,241,0.1)' : '#0D1220',
                    border: `1px solid ${msg.role === 'analyst' ? 'rgba(99,102,241,0.2)' : '#1E2A3A'}`,
                    borderRadius: msg.role === 'analyst' ? '8px 8px 2px 8px' : '8px 8px 8px 2px',
                    padding: '10px 14px',
                  }}>
                    {msg.role === 'parity' ? (
                      <>
                        <div style={{ fontSize: 13, color: '#CBD5E1', lineHeight: 1.6, userSelect: 'text' }} dangerouslySetInnerHTML={{ __html: mdToHtml(msg.text) }} />
                        <button
                          onClick={(e) => { e.stopPropagation(); copyToClipboard(msg.text, i) }}
                          style={{
                            position: 'absolute', top: 6, right: 6, padding: '3px 8px',
                            background: copiedIdx === i ? 'rgba(74,222,128,0.15)' : 'rgba(99,102,241,0.08)',
                            border: `1px solid ${copiedIdx === i ? 'rgba(74,222,128,0.3)' : '#1E2A3A'}`,
                            borderRadius: 3, fontSize: 9, fontWeight: 600, cursor: 'pointer',
                            color: copiedIdx === i ? '#4ADE80' : '#4A5568',
                            fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.06em',
                          }}
                        >
                          {copiedIdx === i ? 'COPIED' : 'COPY'}
                        </button>
                      </>
                    ) : (
                      <p style={{ fontSize: 13, color: '#A5B4FC', lineHeight: 1.6, whiteSpace: 'pre-line', margin: 0, userSelect: 'text' }}>{msg.text}</p>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 9, fontWeight: 700, color: '#4ADE80', letterSpacing: '0.1em', fontFamily: "'IBM Plex Mono', monospace" }}>PARITY</span>
                  <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: '8px 8px 8px 2px', padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 4 }}>
                    {[0, 1, 2].map(n => (
                      <span key={n} style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ADE80', display: 'inline-block', animation: `parityDot 1.4s ${n * 0.2}s infinite ease-in-out` }} />
                    ))}
                    <span style={{ fontSize: 11, color: '#374151', marginLeft: 8, fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.06em' }}>COMPUTING</span>
                  </div>
                </div>
              )}
            </div>
          )}
          {chatHistory.length === 0 && loading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-start' }}>
              <span style={{ fontSize: 9, fontWeight: 700, color: '#4ADE80', letterSpacing: '0.1em', fontFamily: "'IBM Plex Mono', monospace" }}>PARITY</span>
              <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: '8px 8px 8px 2px', padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 4 }}>
                {[0, 1, 2].map(n => (
                  <span key={n} style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ADE80', display: 'inline-block', animation: `parityDot 1.4s ${n * 0.2}s infinite ease-in-out` }} />
                ))}
                <span style={{ fontSize: 11, color: '#374151', marginLeft: 8, fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.06em' }}>ANALYZING SNAPSHOT</span>
              </div>
            </div>
          )}
        </div>

        {/* Suggestion chips */}
        {corpusReady && chatHistory.length <= 1 && !loading && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
            {SUGGESTION_CHIPS.map((chip) => (
              <button
                key={chip}
                onClick={() => { setQuestion(chip); }}
                style={{ padding: '5px 12px', background: 'transparent', border: '1px solid #1E2A3A', borderRadius: 20, fontSize: 11, color: '#4A5568', cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif", transition: 'all 0.15s' }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#6366F1'; (e.currentTarget as HTMLElement).style.color = '#A5B4FC'; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#1E2A3A'; (e.currentTarget as HTMLElement).style.color = '#4A5568'; }}
              >
                {chip}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 14 }}>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={corpusReady ? "Ask anything about this borrower's financials..." : 'Run analysis first to enable Parity Review...'}
            disabled={!corpusReady || loading}
            rows={2}
            style={{ width: '100%', background: 'transparent', border: 'none', outline: 'none', padding: 0, fontSize: 13, color: '#CBD5E1', resize: 'none', fontFamily: "'IBM Plex Sans', sans-serif", boxSizing: 'border-box', opacity: !corpusReady ? 0.4 : 1 }}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10, gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 10, color: '#2D3748', fontFamily: "'IBM Plex Mono', monospace" }}>ctrl+enter to send</span>
            <button
              onClick={() => void doAsk()}
              disabled={!corpusReady || loading || !question.trim()}
              style={{ padding: '7px 16px', background: '#6366F1', color: '#fff', border: 'none', borderRadius: 5, fontSize: 12, fontWeight: 600, cursor: !corpusReady || loading || !question.trim() ? 'not-allowed' : 'pointer', opacity: !corpusReady || loading || !question.trim() ? 0.4 : 1, fontFamily: "'IBM Plex Sans', sans-serif" }}
            >
              {loading ? 'Computing...' : 'Send'}
            </button>
          </div>
        </div>
      </div>

      {/* Right sidebar is rendered by the parent — we only own the chat column */}
    </div>
  )
}

export default memo(ParityReviewChat)
