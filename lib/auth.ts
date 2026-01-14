// Simple authentication utility for MVP

export const login = async () => {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const response = await fetch(`${apiUrl}/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (!response.ok) {
      throw new Error('Login failed')
    }
    
    const data = await response.json()
    localStorage.setItem('access_token', data.access_token)
    return data.access_token
  } catch (error) {
    console.error('Login error:', error)
    throw error
  }
}

export const getToken = () => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('access_token')
  }
  return null
}

export const logout = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('access_token')
  }
}

export const isAuthenticated = () => {
  return !!getToken()
}

// Auto-login for MVP
export const autoLogin = async () => {
  if (!isAuthenticated()) {
    await login()
  }
}
