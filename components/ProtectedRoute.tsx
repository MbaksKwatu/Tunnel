'use client'

import { useEffect } from 'react'
import { useAuth } from './AuthProvider'
import { useRouter } from 'next/navigation'

interface Props {
  children: React.ReactNode
  requireThesis?: boolean
}

export default function ProtectedRoute({ children, requireThesis = false }: Props) {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login')
    }
  }, [user, loading, router])

  // Show loading while checking auth
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-gray-400">Checking authentication...</p>
        </div>
      </div>
    )
  }

  // Redirect if not authenticated
  if (!user) {
    return null
  }

  // Render protected content
  return <>{children}</>
}
