import { getToken } from './auth'

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const fetchApi = async (endpoint: string, options?: RequestInit) => {
  const url = `${API_URL}${endpoint}`
  const token = getToken()
  
  const defaultHeaders = {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
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
