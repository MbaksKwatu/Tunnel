import { createBrowserClient } from './supabase'

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const fetchApi = async (endpoint: string, options?: RequestInit) => {
  const url = `${API_URL}${endpoint}`
  const supabase = createBrowserClient()
  
  let session = null
  if (supabase) {
    try {
      const { data, error } = await supabase.auth.getSession()
      if (error) {
        console.warn('Failed to get session:', error)
      } else {
        session = data.session
      }
    } catch (error) {
      // Supabase not available (e.g., during build) - continue without auth
      console.warn('Failed to get session:', error)
    }
  }
  
  if (!session) {
    // If no session, try to refresh
    if (supabase) {
      try {
        const { data, error } = await supabase.auth.refreshSession()
        if (!error && data.session) {
          session = data.session
        }
      } catch (error) {
        console.warn('Failed to refresh session:', error)
      }
    }
  }
  
  const defaultHeaders = {
    'Content-Type': 'application/json',
    ...(session && { 'Authorization': `Bearer ${session.access_token}` })
  }
  
  const mergedOptions = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options?.headers
    }
  }
  
  const response = await fetch(url, mergedOptions)
  
  // If 401, try refreshing session once
  if (response.status === 401 && supabase && !session) {
    try {
      const { data, error } = await supabase.auth.refreshSession()
      if (!error && data.session) {
        // Retry with new session
        const retryHeaders = {
          ...defaultHeaders,
          'Authorization': `Bearer ${data.session.access_token}`
        }
        const retryOptions = {
          ...options,
          headers: {
            ...retryHeaders,
            ...options?.headers
          }
        }
        return fetch(url, retryOptions)
      }
    } catch (error) {
      console.warn('Failed to refresh session on 401:', error)
    }
  }
  
  return response
}

export async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
  return fetchApi(endpoint, options)
}
