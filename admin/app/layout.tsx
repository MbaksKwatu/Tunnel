import type { Metadata } from 'next'
import './globals.css'
import './layout.css'
import { Providers } from './providers'
import { Sidebar } from '@/components/Sidebar'

export const metadata: Metadata = {
  title: 'Parity Admin',
  description: 'Parity SME internal admin dashboard',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" style={{ height: '100%' }}>
      <body style={{ height: '100%', display: 'flex' }}>
        <Providers>
          <Sidebar />
          <main style={{
            flex: 1,
            minHeight: '100vh',
            background: 'var(--bg)',
            overflow: 'auto',
          }}>
            {children}
          </main>
        </Providers>
      </body>
    </html>
  )
}
