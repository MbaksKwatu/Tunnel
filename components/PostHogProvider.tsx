'use client'

import { useEffect } from 'react'
import posthog from 'posthog-js'

const projectToken = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN
const host = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? 'https://us.i.posthog.com'

function configurePostHog() {
  if (posthog.__loaded) return

  if (!projectToken) {
    if (process.env.NODE_ENV !== 'production') {
      console.warn('[PostHog] NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN not set — tracking disabled')
    }
    return
  }

  posthog.init(projectToken, {
    api_host: host,
    defaults: '2026-05-30',
    capture_exceptions: true,
  })
}

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    configurePostHog()
  }, [])
  return <>{children}</>
}
