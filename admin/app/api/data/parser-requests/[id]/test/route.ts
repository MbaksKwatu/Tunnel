import { NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'
import { requireAdminSession } from '@/lib/require-admin-session'
import { testSubmittedFile } from '@/lib/parser-requests/test-submitted-file'

// The harness extracts the file six times (one pass + a 5x determinism
// check), which can take minutes on a long statement.
export const maxDuration = 300

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await requireAdminSession()
  if (session instanceof NextResponse) return session

  const { id } = await params
  const outcome = await testSubmittedFile(getSupabase(), id, session.email)
  if (!outcome.ok) return NextResponse.json({ error: outcome.error }, { status: outcome.httpStatus })
  return NextResponse.json(outcome)
}
