import { getSupabaseAdmin, parseEnv } from '@/lib/supabase-env'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const env = parseEnv(request)
  const supabase = getSupabaseAdmin(env)

  const [autoRes, manualRes] = await Promise.all([
    supabase.from('parser_requests').select('*').order('requested_at', { ascending: false }),
    supabase.from('pds_parser_requests').select('*').order('created_at', { ascending: false }),
  ])
  if (autoRes.error) return NextResponse.json({ error: autoRes.error.message }, { status: 500 })
  if (manualRes.error) return NextResponse.json({ error: manualRes.error.message }, { status: 500 })

  return NextResponse.json({
    auto: autoRes.data ?? [],
    manual: manualRes.data ?? [],
    env,
    fetched_at: new Date().toISOString(),
  })
}

export async function PATCH(request: NextRequest) {
  const env = parseEnv(request)
  const supabase = getSupabaseAdmin(env)
  const { id, status } = await request.json()
  const { error } = await supabase.from('parser_requests').update({ status }).eq('id', id)
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json({ ok: true })
}
