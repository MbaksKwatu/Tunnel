import { createClient, SupabaseClient } from '@supabase/supabase-js'

// Single Supabase client for the browser (guards against multiple GoTrue clients, even across HMR)
const globalForSupabase = globalThis as typeof globalThis & { __supabaseBrowserClient?: SupabaseClient }
export const createBrowserClient = (): SupabaseClient | null => {
  if (globalForSupabase.__supabaseBrowserClient) return globalForSupabase.__supabaseBrowserClient
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key) return null
  globalForSupabase.__supabaseBrowserClient = createClient(url, key)
  return globalForSupabase.__supabaseBrowserClient
}

// For server components
export const createServerClient = (): SupabaseClient | null => {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  
  if (!supabaseUrl || !supabaseAnonKey) {
    return null
  }
  return createClient(supabaseUrl, supabaseAnonKey)
}

// Get current session (uses shared client)
export const getSession = async () => {
  const client = createBrowserClient()
  if (!client) return null
  try {
    const { data: { session } } = await client.auth.getSession()
    return session
  } catch {
    return null
  }
}

// Get current user (uses shared client)
export const getUser = async () => {
  const client = createBrowserClient()
  if (!client) return null
  try {
    const { data: { user } } = await client.auth.getUser()
    return user
  } catch {
    return null
  }
}

// Legacy export for backward compatibility
export const createClientComponentClient = createBrowserClient

// Shared instance (same as createBrowserClient() after first call)
export const supabase = createBrowserClient()


