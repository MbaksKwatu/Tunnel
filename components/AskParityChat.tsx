'use client'

import { useState, useEffect, useRef } from 'react'
import { fetchApi } from '@/lib/api'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  id?: string
  created_at?: string
}

export default function AskParityChat({ dealId }: { dealId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadConversation()
  }, [dealId])

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages, loading])

  const loadConversation = async () => {
    setError('')
    try {
      const res = await fetchApi(`/api/deals/${dealId}/conversation`)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to load conversation')
      }
      const data = await res.json()
      setMessages((data.messages || []).map((m: { role: string; content: string; created_at?: string }) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content || '',
        created_at: m.created_at
      })))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load conversation')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setLoading(true)
    setError('')

    const userMsg: ChatMessage = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])

    try {
      const res = await fetchApi(`/api/deals/${dealId}/ask`, {
        method: 'POST',
        body: JSON.stringify({ message: text })
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Ask Parity is unavailable')
      }

      const data = await res.json()
      const assistantContent = (data.response || '').trim()
      setMessages((prev) => [...prev, { role: 'assistant', content: assistantContent }])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setMessages((prev) => prev.slice(0, -1))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 flex flex-col h-[400px]">
      <h2 className="text-xl font-semibold text-white mb-4">Ask Parity</h2>

      <div
        ref={listRef}
        className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0"
      >
        {messages.length === 0 && !loading && (
          <p className="text-gray-500 text-sm">Ask about this deal, evidence, judgment, or open questions.</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-4 py-2 text-sm ${
                m.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-100'
              }`}
            >
              <p className="whitespace-pre-wrap">{m.content}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-700 rounded-lg px-4 py-2 text-sm text-gray-400">
              Parity is thinking…
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 bg-red-500/10 border border-red-500 text-red-400 text-sm px-3 py-2 rounded">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your question..."
          disabled={loading}
          className="flex-1 bg-gray-700 text-white rounded-lg px-4 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg text-sm font-medium transition"
        >
          Send
        </button>
      </form>
    </div>
  )
}
