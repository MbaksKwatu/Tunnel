// Minimal in-memory stand-in for the slice of the Supabase client the
// parser-request lifecycle uses. Test-only.
import type { SupabaseClient } from '@supabase/supabase-js'

type Row = Record<string, unknown>

export function fakeSupabase(seed: {
  requests?: Row[]
  events?: Row[]
  profiles?: Row[]
  users?: Record<string, string>
  files?: Record<string, Blob>
  failEventInsert?: boolean
}) {
  const tables: Record<string, Row[]> = {
    pds_parser_requests: (seed.requests ?? []).map((r) => ({ ...r })),
    pds_parser_request_events: (seed.events ?? []).map((r) => ({ ...r })),
    user_profiles: (seed.profiles ?? []).map((r) => ({ ...r })),
  }
  let clock = 0

  function query(table: string) {
    const filters: Array<(r: Row) => boolean> = []
    let patch: Row | null = null
    let order: { col: string; asc: boolean } | null = null
    let limit = Infinity

    const rows = () => {
      let out = tables[table].filter((r) => filters.every((f) => f(r)))
      if (order) {
        const { col, asc } = order
        out = [...out].sort((a, b) => (String(a[col]) < String(b[col]) ? -1 : 1) * (asc ? 1 : -1))
      }
      return out.slice(0, limit)
    }

    const q = {
      select: () => q,
      eq: (col: string, val: unknown) => { filters.push((r) => r[col] === val); return q },
      in: (col: string, vals: unknown[]) => { filters.push((r) => vals.includes(r[col])); return q },
      order: (col: string, opts?: { ascending?: boolean }) => { order = { col, asc: opts?.ascending ?? true }; return q },
      limit: (n: number) => { limit = n; return q },
      update: (p: Row) => { patch = p; return q },
      maybeSingle: async () => ({ data: rows()[0] ?? null, error: null }),
      insert: async (row: Row) => {
        if (table === 'pds_parser_request_events' && seed.failEventInsert) return { error: { message: 'log down' } }
        tables[table].push({ created_at: `2026-10-01T00:00:${String(clock++).padStart(2, '0')}Z`, ...row })
        return { error: null }
      },
      then: (resolve: (v: { data: Row[]; error: null }) => void) => {
        const matched = rows()
        if (patch) for (const r of matched) Object.assign(r, patch)
        resolve({ data: matched.map((r) => ({ ...r })), error: null })
      },
    }
    return q
  }

  const client = {
    from: (table: string) => query(table),
    auth: {
      admin: {
        getUserById: async (id: string) => ({ data: { user: seed.users?.[id] ? { email: seed.users[id] } : null }, error: null }),
      },
    },
    storage: {
      from: () => ({
        download: async (path: string) =>
          seed.files?.[path] ? { data: seed.files[path], error: null } : { data: null, error: { message: 'Object not found' } },
      }),
    },
  }
  return { client: client as unknown as SupabaseClient, tables }
}
