import { createBrowserClient } from './supabase'

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const fetchApi = async (endpoint: string, options?: RequestInit) => {
  const url = `${API_URL}${endpoint}`
  const supabase = createBrowserClient()
  const { data: { session } } = await supabase.auth.getSession()
  
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
  
  return fetch(url, mergedOptions)
}

export async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
  return fetchApi(endpoint, options)
}
