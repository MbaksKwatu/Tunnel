import type { Metadata } from 'next'
import './globals.css'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Parity Admin',
  description: 'Parity SME internal admin dashboard',
}

const navItems = [
  { href: '/parser-requests', label: 'Parser Requests' },
  { href: '/musa-sessions', label: 'Musa Sessions' },
  { href: '/deals', label: 'Deal Pipeline' },
  { href: '/api-keys', label: 'API Keys' },
]

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" style={{ height: '100%' }}>
      <body style={{ height: '100%', display: 'flex' }}>
        <aside style={{
          width: 220,
          minHeight: '100vh',
          background: 'var(--navy)',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
          padding: '0',
        }}>
          <div style={{
            padding: '24px 20px 20px',
            borderBottom: '1px solid rgba(255,255,255,0.08)',
          }}>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 500,
              fontSize: 13,
              letterSpacing: '0.08em',
              color: 'var(--teal)',
            }}>
              PARITY
            </span>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 400,
              fontSize: 13,
              letterSpacing: '0.08em',
              color: 'rgba(255,255,255,0.5)',
            }}>
              {' '}ADMIN
            </span>
          </div>
          <nav style={{ padding: '12px 0', flex: 1 }}>
            {navItems.map((item) => (
              <Link key={item.href} href={item.href} style={{
                display: 'block',
                padding: '10px 20px',
                fontFamily: "'IBM Plex Sans', sans-serif",
                fontWeight: 400,
                fontSize: 13,
                color: 'rgba(255,255,255,0.65)',
                transition: 'color 0.15s, background 0.15s',
              }}
                onMouseOver={(e) => {
                  const el = e.currentTarget as HTMLAnchorElement
                  el.style.color = '#fff'
                  el.style.background = 'rgba(255,255,255,0.06)'
                }}
                onMouseOut={(e) => {
                  const el = e.currentTarget as HTMLAnchorElement
                  el.style.color = 'rgba(255,255,255,0.65)'
                  el.style.background = 'transparent'
                }}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </aside>
        <main style={{
          flex: 1,
          minHeight: '100vh',
          background: 'var(--bg)',
          overflow: 'auto',
        }}>
          {children}
        </main>
      </body>
    </html>
  )
}
