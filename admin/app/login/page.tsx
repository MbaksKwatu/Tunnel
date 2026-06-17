'use client'

import { useState, FormEvent, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { supabaseBrowser } from '@/lib/supabase-browser'

const ALLOWED_EMAILS = [
  'emdeechege@gmail.com',
  'mbakayaweever@gmail.com',
  'samwelchegeh09@gmail.com',
]

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const isUnauthorized = searchParams.get('error') === 'unauthorized'

  const [step, setStep] = useState<'email' | 'otp'>('email')
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(isUnauthorized ? 'This email is not authorised to access Parity Admin.' : '')

  async function handleEmailSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const normalized = email.trim().toLowerCase()

    if (!ALLOWED_EMAILS.includes(normalized)) {
      setError('This email is not authorised to access Parity Admin.')
      return
    }

    setLoading(true)
    const { error: otpError } = await supabaseBrowser.auth.signInWithOtp({
      email: normalized,
      options: { shouldCreateUser: false },
    })
    setLoading(false)

    if (otpError) {
      setError(otpError.message)
      return
    }

    setEmail(normalized)
    setStep('otp')
  }

  async function handleOtpSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const { error: verifyError } = await supabaseBrowser.auth.verifyOtp({
      email,
      token: otp.trim(),
      type: 'email',
    })
    setLoading(false)

    if (verifyError) {
      setError('Invalid or expired code. Try again.')
      return
    }

    router.push('/parser-requests')
    router.refresh()
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      <div style={{
        background: 'var(--paper)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '40px 48px',
        width: 400,
        boxShadow: '0 2px 16px rgba(0,0,0,0.06)',
      }}>
        <div style={{ marginBottom: 32, textAlign: 'center' }}>
          <div style={{ marginBottom: 8 }}>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 500,
              fontSize: 15,
              letterSpacing: '0.08em',
              color: 'var(--teal)',
            }}>PARITY</span>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 400,
              fontSize: 15,
              letterSpacing: '0.08em',
              color: 'var(--t2)',
            }}> ADMIN</span>
          </div>
          <h1 style={{
            fontFamily: "'IBM Plex Serif', serif",
            fontWeight: 400,
            fontSize: 20,
            color: 'var(--navy)',
            marginTop: 16,
          }}>
            {step === 'email' ? 'Sign in' : 'Check your email'}
          </h1>
          <p style={{
            fontFamily: "'IBM Plex Sans', sans-serif",
            fontSize: 13,
            color: 'var(--t1)',
            marginTop: 8,
          }}>
            {step === 'email'
              ? 'Enter your email to receive a one-time code.'
              : `We sent a 6-digit code to ${email}`}
          </p>
        </div>

        {error && (
          <div style={{
            background: 'var(--red-d)',
            border: '1px solid rgba(220,38,38,0.16)',
            borderRadius: 6,
            padding: '10px 14px',
            marginBottom: 20,
            fontFamily: "'IBM Plex Sans', sans-serif",
            fontSize: 13,
            color: 'var(--red)',
          }}>
            {error}
          </div>
        )}

        {step === 'email' ? (
          <form onSubmit={handleEmailSubmit}>
            <label style={{
              display: 'block',
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 11,
              letterSpacing: '0.06em',
              color: 'var(--t2)',
              marginBottom: 6,
            }}>
              EMAIL ADDRESS
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontFamily: "'IBM Plex Sans', sans-serif",
                fontSize: 14,
                color: 'var(--t0)',
                background: 'var(--white)',
                outline: 'none',
                marginBottom: 20,
              }}
            />
            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '11px',
                background: loading ? 'var(--teal-d)' : 'var(--teal)',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                fontFamily: "'IBM Plex Sans', sans-serif",
                fontWeight: 500,
                fontSize: 14,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'background 0.15s',
              }}
            >
              {loading ? 'Sending…' : 'Send code'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleOtpSubmit}>
            <label style={{
              display: 'block',
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 11,
              letterSpacing: '0.06em',
              color: 'var(--t2)',
              marginBottom: 6,
            }}>
              ONE-TIME CODE
            </label>
            <input
              type="text"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="123456"
              required
              autoFocus
              maxLength={6}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: 20,
                letterSpacing: '0.2em',
                color: 'var(--t0)',
                background: 'var(--white)',
                outline: 'none',
                marginBottom: 20,
                textAlign: 'center',
              }}
            />
            <button
              type="submit"
              disabled={loading || otp.length < 6}
              style={{
                width: '100%',
                padding: '11px',
                background: (loading || otp.length < 6) ? 'var(--teal-d)' : 'var(--teal)',
                color: (loading || otp.length < 6) ? 'var(--teal)' : '#fff',
                border: 'none',
                borderRadius: 6,
                fontFamily: "'IBM Plex Sans', sans-serif",
                fontWeight: 500,
                fontSize: 14,
                cursor: (loading || otp.length < 6) ? 'not-allowed' : 'pointer',
                transition: 'background 0.15s',
              }}
            >
              {loading ? 'Verifying…' : 'Sign in'}
            </button>
            <button
              type="button"
              onClick={() => { setStep('email'); setOtp(''); setError('') }}
              style={{
                width: '100%',
                padding: '10px',
                background: 'none',
                border: 'none',
                color: 'var(--t2)',
                fontFamily: "'IBM Plex Sans', sans-serif",
                fontSize: 13,
                cursor: 'pointer',
                marginTop: 8,
              }}
            >
              ← Use a different email
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
