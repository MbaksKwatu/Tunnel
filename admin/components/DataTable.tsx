'use client'

export interface Column<T> {
  key: string
  label: string
  mono?: boolean
  truncate?: boolean
  render?: (value: unknown, row: T) => React.ReactNode
}

interface DataTableProps<T extends Record<string, unknown>> {
  columns: Column<T>[]
  rows: T[]
  onRowClick?: (row: T) => void
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  onRowClick,
}: DataTableProps<T>) {
  if (rows.length === 0) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        color: 'var(--t2)',
        fontFamily: "'IBM Plex Sans', sans-serif",
        fontSize: 14,
      }}>
        No records found
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontFamily: "'IBM Plex Sans', sans-serif",
        fontSize: 13,
      }}>
        <thead>
          <tr style={{ background: 'var(--bg2)' }}>
            {columns.map((col) => (
              <th key={col.key} style={{
                padding: '10px 16px',
                textAlign: 'left',
                fontFamily: "'IBM Plex Mono', monospace",
                fontWeight: 500,
                fontSize: 11,
                letterSpacing: '0.06em',
                color: 'var(--t2)',
                borderBottom: '1px solid var(--border)',
                whiteSpace: 'nowrap',
              }}>
                {col.label.toUpperCase()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              onClick={() => onRowClick?.(row)}
              style={{
                cursor: onRowClick ? 'pointer' : 'default',
                background: 'var(--paper)',
                transition: 'background 0.1s',
              }}
              onMouseOver={(e) => {
                (e.currentTarget as HTMLTableRowElement).style.background = 'var(--teal-d)'
              }}
              onMouseOut={(e) => {
                (e.currentTarget as HTMLTableRowElement).style.background = 'var(--paper)'
              }}
            >
              {columns.map((col) => {
                const val = row[col.key]
                const rendered = col.render ? col.render(val, row) : String(val ?? '—')
                return (
                  <td key={col.key} style={{
                    padding: '12px 16px',
                    borderBottom: '1px solid var(--border)',
                    fontFamily: col.mono ? "'IBM Plex Mono', monospace" : "'IBM Plex Sans', sans-serif",
                    fontSize: col.mono ? 12 : 13,
                    color: 'var(--t0)',
                    maxWidth: col.truncate ? 200 : undefined,
                    overflow: col.truncate ? 'hidden' : undefined,
                    textOverflow: col.truncate ? 'ellipsis' : undefined,
                    whiteSpace: col.truncate ? 'nowrap' : undefined,
                  }}>
                    {rendered}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
