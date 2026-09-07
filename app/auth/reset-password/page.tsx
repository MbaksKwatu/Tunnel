'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createBrowserClient } from '@/lib/supabase'

export default function ResetPassword() {
  const router = useRouter()
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    const checkSession = async () => {
      const supabase = createBrowserClient()
      if (!supabase) {
        router.push('/login?error=supabase_not_configured')
        return
      }

      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        router.push('/login?error=invalid_reset_link')
        return
      }
    }

    checkSession()
  }, [router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }

    setLoading(true)

    try {
      const supabase = createBrowserClient()
      if (!supabase) {
        throw new Error('Supabase not configured')
      }

      const { error } = await supabase.auth.updateUser({
        password: password
      })

      if (error) throw error

      setSuccess(true)

      setTimeout(() => {
        router.push('/login?message=password_reset_success')
      }, 2000)
    } catch (err: any) {
      setError(err.message || 'Failed to reset password')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div
        className="min-h-screen flex items-center justify-center p-6"
        style={{ background: 'var(--bg)' }}
      >
        <div
          className="w-full max-w-md rounded-xl p-8 text-center space-y-4"
          style={{ background: 'var(--s1)', border: '1px solid rgba(20,184,166,0.2)' }}
        >
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center mx-auto"
            style={{ background: 'rgba(20,184,166,0.15)', border: '1px solid rgba(20,184,166,0.4)' }}
          >
            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--accent)' }}>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <div className="text-lg font-semibold mb-1" style={{ color: 'var(--t0)' }}>Password updated</div>
            <div className="text-sm" style={{ color: 'var(--t2)' }}>Redirecting to sign in…</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-6"
      style={{ background: 'var(--bg)' }}
    >
      <div
        className="w-full max-w-md rounded-xl p-8 space-y-6"
        style={{ background: 'var(--s1)', border: '1px solid rgba(20,184,166,0.2)' }}
      >
        {/* Logo */}
        <div className="text-center space-y-1">
          <div className="text-2xl font-bold tracking-widest" style={{ color: 'var(--t0)', fontFamily: 'IBM Plex Mono, monospace' }}>
            PARITY
          </div>
          <div className="text-xs tracking-widest uppercase" style={{ color: 'var(--accent)', fontFamily: 'IBM Plex Sans, sans-serif' }}>
            Intelligence Infrastructure
          </div>
        </div>

        <div className="text-center">
          <div className="text-sm font-medium mb-0.5" style={{ color: 'var(--t0)' }}>Set new password</div>
          <div className="text-xs" style={{ color: 'var(--t2)' }}>Choose a password at least 6 characters long</div>
        </div>

        {error && (
          <div className="p-3 rounded-lg text-sm" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.4)', color: 'var(--red)' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="password" className="block text-xs font-medium mb-1.5" style={{ color: 'var(--t1)' }}>
              New password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              placeholder="••••••••"
              className="w-full px-3 py-2.5 rounded-lg text-sm outline-none transition-colors"
              style={{
                background: 'var(--s2)',
                border: '1px solid rgba(20,184,166,0.25)',
                color: 'var(--t0)',
              }}
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-xs font-medium mb-1.5" style={{ color: 'var(--t1)' }}>
              Confirm password
            </label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={6}
              placeholder="••••••••"
              className="w-full px-3 py-2.5 rounded-lg text-sm outline-none transition-colors"
              style={{
                background: 'var(--s2)',
                border: '1px solid rgba(20,184,166,0.25)',
                color: 'var(--t0)',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg font-semibold text-sm transition-opacity"
            style={{ background: 'var(--accent)', color: '#fff', opacity: loading ? 0.7 : 1 }}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Updating password…
              </span>
            ) : (
              'Update Password'
            )}
          </button>
        </form>

        <div className="text-center">
          <button
            type="button"
            onClick={() => router.push('/login')}
            className="text-xs"
            style={{ color: 'var(--t2)' }}
          >
            Back to sign in
          </button>
        </div>
      </div>
    </div>
  )
}
