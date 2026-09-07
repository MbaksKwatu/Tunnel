'use client'

import { useEffect } from 'react'

const projectToken = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN
const host = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? 'https://us.i.posthog.com'

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // Dynamic import keeps posthog-js out of the module graph during SSR.
    // posthog-js 1.428.x references `window` at module evaluation time, which
    // crashes Next.js App Router prerendering even inside 'use client' components.
    import('posthog-js').then(({ default: posthog }) => {
      if (posthog.__loaded) return
      if (!projectToken) return
      posthog.init(projectToken, {
        api_host: host,
        defaults: '2026-05-30',
        capture_exceptions: true,
      })
    })
  }, [])
  return <>{children}</>
}
