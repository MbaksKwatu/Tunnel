'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createBrowserClient } from '@/lib/supabase'

export default function AuthCallback() {
  const router = useRouter()

  useEffect(() => {
    const handleAuthCallback = async () => {
      const supabase = createBrowserClient()
      if (!supabase) {
        router.push('/login?error=supabase_not_configured')
        return
      }

      try {
        // Handle the auth callback
        const { data, error } = await supabase.auth.getSession()
        
        if (error) {
          console.error('Auth callback error:', error)
          router.push(`/login?error=${encodeURIComponent(error.message)}`)
          return
        }

        if (data.session) {
          router.push('/v1/deal')
        } else {
          // No session, redirect to login
          router.push('/login?error=no_session')
        }
      } catch (err: any) {
        console.error('Auth callback exception:', err)
        router.push(`/login?error=${encodeURIComponent(err.message || 'Unknown error')}`)
      }
    }

    handleAuthCallback()
  }, [router])

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <div className="text-center">
        <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-white text-lg">Verifying your account...</p>
      </div>
    </div>
  )
}
