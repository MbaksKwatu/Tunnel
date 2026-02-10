import { createBrowserClient } from './supabase'
import { getApiToken, setApiToken } from './auth-bridge'

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const fetchApi = async (endpoint: string, options?: RequestInit) => {
  const url = `${API_URL}${endpoint}`
  const supabase = createBrowserClient()
  // Use token from AuthProvider first (same session the UI shows), then getSession()
  let token = getApiToken()
  if (!token && supabase) {
    try {
      const { data } = await supabase.auth.getSession()
      token = data.session?.access_token ?? null
      if (token) setApiToken(token)
    } catch {
      // continue without auth
    }
  }
  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
    ...(token && { Authorization: `Bearer ${token}` })
  }
  if (options?.body instanceof FormData) {
    delete defaultHeaders['Content-Type']
  }
  const res = await fetch(url, { ...options, headers: defaultHeaders })
  if (res.status === 401 && supabase && token) {
    try {
      const { data } = await supabase.auth.refreshSession()
      if (data.session?.access_token) {
        setApiToken(data.session.access_token)
        return fetch(url, {
          ...options,
          headers: { ...defaultHeaders, Authorization: `Bearer ${data.session.access_token}` }
        })
      }
    } catch {
      // return original response
    }
  }
  return res
}

export async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
  return fetchApi(endpoint, options)
}
