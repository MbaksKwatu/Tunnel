'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { User, Session } from '@supabase/supabase-js'
import { createBrowserClient } from '@/lib/supabase'
import { setApiToken } from '@/lib/auth-bridge'
import { useRouter } from 'next/navigation'

interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<{ error?: any }>
  signUp: (email: string, password: string) => Promise<{ error?: any; data?: any }>
  resetPassword: (email: string) => Promise<{ error?: any }>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  
  // Lazy client creation - only create when actually needed (client-side)
  const getSupabaseClient = () => {
    return createBrowserClient()
  }

  useEffect(() => {
    const supabase = getSupabaseClient()
    if (!supabase) {
      setLoading(false)
      return
    }

    // Get initial session and keep API token in sync so fetchApi always has it
    const getInitialSession = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        setSession(session)
        setUser(session?.user ?? null)
        setApiToken(session?.access_token ?? null)
      } catch (error) {
        console.warn('Failed to get session:', error)
        setApiToken(null)
      } finally {
        setLoading(false)
      }
    }

    getInitialSession()

    // Listen for auth changes and keep API token in sync
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event: string, session: Session | null) => {
        setSession(session)
        setUser(session?.user ?? null)
        setApiToken(session?.access_token ?? null)
        if (event === 'SIGNED_IN') {
          router.push('/v1/deal')
        }
        
        if (event === 'SIGNED_OUT') {
          router.push('/login')
        }
      }
    )

    return () => {
      subscription.unsubscribe()
    }
  }, [router])

  const signIn = async (email: string, password: string) => {
    const supabase = getSupabaseClient()
    if (!supabase) {
      return { error: { message: 'Supabase not configured' } }
    }
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })
    return { error }
  }

  const signUp = async (email: string, password: string) => {
    const supabase = getSupabaseClient()
    if (!supabase) {
      return { error: { message: 'Supabase not configured' } }
    }
    
    // Get the redirect URL - use production URL if available, otherwise use current origin
    const redirectUrl = typeof window !== 'undefined' 
      ? `${window.location.origin}/auth/callback`
      : process.env.NEXT_PUBLIC_SITE_URL 
        ? `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`
        : '/auth/callback'
    
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: redirectUrl,
      }
    })
    
    // Return both error and data so we can check if session exists
    return { error, data }
  }

  const resetPassword = async (email: string) => {
    const supabase = getSupabaseClient()
    if (!supabase) {
      return { error: { message: 'Supabase not configured' } }
    }
    
    // Get the redirect URL for password reset
    const redirectUrl = typeof window !== 'undefined' 
      ? `${window.location.origin}/auth/reset-password`
      : process.env.NEXT_PUBLIC_SITE_URL 
        ? `${process.env.NEXT_PUBLIC_SITE_URL}/auth/reset-password`
        : '/auth/reset-password'
    
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: redirectUrl,
    })
    return { error }
  }

  const signOut = async () => {
    setApiToken(null)
    const supabase = getSupabaseClient()
    if (supabase) {
      await supabase.auth.signOut()
    }
    router.push('/login')
  }

  const value = {
    user,
    session,
    loading,
    signIn,
    signUp,
    resetPassword,
    signOut,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
