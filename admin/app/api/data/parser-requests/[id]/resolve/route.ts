import { NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'
import { requireAdminSession } from '@/lib/require-admin-session'
import { resolveParserRequest, type ResolveBasis } from '@/lib/parser-requests/resolve'

// Body: { basis: 'test_pass' } after a passing test, or
//       { basis: 'override', reason: '...' } (reason required, logged).
export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await requireAdminSession()
  if (session instanceof NextResponse) return session

  const { id } = await params
  const body = (await req.json().catch(() => ({}))) as { basis?: string; reason?: string }
  if (body.basis !== 'test_pass' && body.basis !== 'override') {
    return NextResponse.json({ error: "basis must be 'test_pass' or 'override'" }, { status: 400 })
  }

  const outcome = await resolveParserRequest(getSupabase(), id, {
    basis: body.basis as ResolveBasis,
    reason: body.reason,
    actor: session.email,
  })
  if (!outcome.ok) return NextResponse.json({ error: outcome.error }, { status: outcome.httpStatus })
  return NextResponse.json(outcome)
}
