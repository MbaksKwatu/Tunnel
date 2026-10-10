import type { Metadata } from 'next'
import './globals.css'
import './layout.css'
import { Sidebar } from '@/components/Sidebar'
import { PostHogProvider } from '@/components/PostHogProvider'
import { getOntologyQaVisibility } from '@/lib/get-ontology-qa-visibility'

export const metadata: Metadata = {
  title: 'Parity Admin',
  description: 'Parity SME internal admin dashboard',
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const showOntologyQa = await getOntologyQaVisibility()

  return (
    <html lang="en" style={{ height: '100%' }}>
      <body style={{ height: '100%', display: 'flex' }}>
        <PostHogProvider>
          <Sidebar showOntologyQa={showOntologyQa} />
          <main style={{
            flex: 1,
            minHeight: '100vh',
            background: 'var(--bg)',
            overflow: 'auto',
          }}>
            {children}
          </main>
        </PostHogProvider>
      </body>
    </html>
  )
}
