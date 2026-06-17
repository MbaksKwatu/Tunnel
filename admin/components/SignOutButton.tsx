'use client'

import { useRouter } from 'next/navigation'
import { supabaseBrowser } from '@/lib/supabase-browser'

export function SignOutButton() {
  const router = useRouter()

  async function handleSignOut() {
    await supabaseBrowser.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  return (
    <button
      onClick={handleSignOut}
      style={{
        display: 'block',
        width: '100%',
        padding: '10px 20px',
        background: 'none',
        border: 'none',
        textAlign: 'left',
        fontFamily: "'IBM Plex Sans', sans-serif",
        fontWeight: 400,
        fontSize: 13,
        color: 'rgba(255,255,255,0.35)',
        cursor: 'pointer',
        transition: 'color 0.15s',
      }}
      onMouseOver={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.65)' }}
      onMouseOut={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.35)' }}
    >
      Sign out
    </button>
  )
}
