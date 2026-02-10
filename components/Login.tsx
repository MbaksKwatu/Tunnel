'use client'

import { useState, useEffect } from 'react'
import { useAuth } from './AuthProvider'
import { useRouter } from 'next/navigation'
import { createBrowserClient } from '@/lib/supabase'

const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === 'true'
const demoEmail = process.env.NEXT_PUBLIC_DEMO_EMAIL || ''

export default function Login() {
  const [isSignUp, setIsSignUp] = useState(false)
  const [showForgotPassword, setShowForgotPassword] = useState(false)
  const [email, setEmail] = useState(isDemoMode ? demoEmail : '')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  
  const { signIn, signUp, resetPassword } = useAuth()
  const router = useRouter()

  // Check for error in URL (from auth callback)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const errorParam = params.get('error')
      if (errorParam) {
        setError(decodeURIComponent(errorParam))
        // Clean up URL
        window.history.replaceState({}, '', '/login')
      }
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')

    try {
      if (showForgotPassword) {
        // Handle password reset
        if (!email) {
          setError('Please enter your email address')
          setLoading(false)
          return
        }
        const { error } = await resetPassword(email)
        if (error) throw error
        setMessage('Check your email for a password reset link! The link will expire in 1 hour.')
        setShowForgotPassword(false)
      } else if (isSignUp && !isDemoMode) {
        const result = await signUp(email, password)
        if (result.error) throw result.error
        
        // Check if user needs email confirmation
        // If session exists in result.data, user was auto-confirmed (email confirmation disabled)
        // If no session, user needs to confirm email
        if (result.data?.session) {
          // User is already signed in (email confirmation disabled)
          setMessage('Account created successfully! Redirecting...')
          // AuthProvider will handle redirect via onAuthStateChange
        } else if (result.data?.user && !result.data?.session) {
          // User created but needs email confirmation
          setMessage('Check your email to confirm your account! The confirmation link will expire in 1 hour. Check your spam folder if you don\'t see it.')
        } else {
          // Fallback message
          setMessage('Account created! Check your email to confirm your account.')
        }
      } else {
        const { error } = await signIn(email, password)
        if (error) throw error
        // AuthProvider will handle redirect
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-gray-800 rounded-lg p-8 space-y-6">
        {/* Logo/Title */}
        <div className="text-center">
          <div className="w-16 h-16 bg-blue-600 rounded-lg flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-3xl">P</span>
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {showForgotPassword ? 'Reset Password' : isSignUp && !isDemoMode ? 'Create Account' : 'Welcome Back'}
          </h1>
          <p className="text-gray-400">
            {showForgotPassword
              ? 'Enter your email to receive a password reset link'
              : isDemoMode
                ? `Demo: sign in with ${demoEmail || 'the demo account'}`
                : isSignUp
                  ? 'Sign up to start assessing deals'
                  : 'Sign in to continue to Parity'
            }
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded">
            {error}
          </div>
        )}

        {/* Success Message */}
        {message && (
          <div className="bg-green-500/10 border border-green-500 text-green-500 p-4 rounded">
            {message}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => !isDemoMode && setEmail(e.target.value)}
              required
              readOnly={isDemoMode}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              placeholder="you@example.com"
            />
          </div>

          {!showForgotPassword && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label htmlFor="password" className="block text-sm font-medium text-gray-300">
                  Password
                </label>
                {!isSignUp && (
                  <button
                    type="button"
                    onClick={() => {
                      setShowForgotPassword(true)
                      setError('')
                      setMessage('')
                    }}
                    className="text-xs text-blue-400 hover:text-blue-300 transition"
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                placeholder="••••••••"
              />
              {isSignUp && (
                <p className="text-xs text-gray-500 mt-1">
                  Minimum 6 characters
                </p>
              )}
            </div>
          )}

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
                {showForgotPassword ? 'Sending...' : isSignUp ? 'Creating Account...' : 'Signing In...'}
              </span>
            ) : (
              showForgotPassword ? 'Send Reset Link' : isSignUp ? 'Create Account' : 'Sign In'
            )}
          </button>
        </form>

        {/* Toggle Sign In / Sign Up / Back to Login */}
        <div className="text-center">
          {showForgotPassword ? (
            <button
              type="button"
              onClick={() => {
                setShowForgotPassword(false)
                setError('')
                setMessage('')
              }}
              className="text-sm text-gray-400 hover:text-white transition"
            >
              Back to sign in
            </button>
          ) : !isDemoMode ? (
            <button
              type="button"
              onClick={() => {
                setIsSignUp(!isSignUp)
                setError('')
                setMessage('')
              }}
              className="text-sm text-gray-400 hover:text-white transition"
            >
              {isSignUp ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
