// Simple authentication utility for MVP
// NOTE: This file is legacy. The app now uses Supabase auth via AuthProvider.
// Keeping these functions for backward compatibility but they're not actively used.

export const login = async () => {
  // Legacy function - app now uses Supabase auth
  // This endpoint doesn't exist on the backend
  console.warn('Legacy login() called - app uses Supabase auth via AuthProvider')
  return null
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
// NOTE: Legacy function - app now uses Supabase auth via AuthProvider
export const autoLogin = async () => {
  // Legacy function - app now uses Supabase auth
  // No-op to prevent errors
  console.warn('Legacy autoLogin() called - app uses Supabase auth via AuthProvider')
}
