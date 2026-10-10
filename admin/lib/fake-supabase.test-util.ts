// Minimal in-memory stand-in for the Supabase query builder, used by the
// Ontology QA tests. Unlike a bare mock it actually applies .eq/.in/.range, so
// tests can assert what data comes back, not just which methods were called.
type Row = Record<string, unknown>
export type FakeTables = Record<string, Row[]>

export function createFakeSupabase(tables: FakeTables) {
  const selects: { table: string; columns: string }[] = []

  function from(table: string) {
    let rows = [...(tables[table] ?? [])]
    let columns = '*'
    let single = false
    const builder = {
      select(cols: string) {
        columns = cols
        selects.push({ table, columns: cols })
        return builder
      },
      eq(col: string, val: unknown) {
        rows = rows.filter((r) => r[col] === val)
        return builder
      },
      in(col: string, vals: unknown[]) {
        rows = rows.filter((r) => vals.includes(r[col]))
        return builder
      },
      order() {
        return builder
      },
      limit(n: number) {
        rows = rows.slice(0, n)
        return builder
      },
      range(from: number, to: number) {
        rows = rows.slice(from, to + 1)
        return builder
      },
      single() {
        single = true
        return builder
      },
      then(resolve: (v: { data: unknown; error: null }) => unknown) {
        const cols = columns === '*' ? null : columns.split(',').map((c) => c.trim())
        const projected = cols ? rows.map((r) => Object.fromEntries(cols.map((c) => [c, r[c]]))) : rows
        return Promise.resolve({ data: single ? (projected[0] ?? null) : projected, error: null }).then(resolve)
      },
    }
    return builder
  }

  return { client: { from }, selects }
}
