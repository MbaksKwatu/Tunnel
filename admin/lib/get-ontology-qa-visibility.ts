import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { isOntologyQaAllowed } from '@/lib/ontology-qa-access'

// Resolved on the server in RootLayout so the sidebar link renders on first
// paint, with no client-side session hydration race (PAR-140). Visibility
// only: proxy.ts still enforces access to /ontology-qa and its API routes.
// Runs on every route, including /login before any session exists, so it
// must never throw.
export async function getOntologyQaVisibility(): Promise<boolean> {
  try {
    const cookieStore = await cookies()
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll() {
            return cookieStore.getAll()
          },
          setAll() {},
        },
      }
    )
    const { data: { user } } = await supabase.auth.getUser()
    return isOntologyQaAllowed(user?.email)
  } catch {
    return false
  }
}
