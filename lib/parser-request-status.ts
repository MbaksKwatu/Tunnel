// Client-facing view of pds_parser_requests.status.
//
// The backend vocabulary (backend/migrations/046, CHECK-constrained) is
// new → in_progress → testing → resolved, shared with the admin queue. Clients
// only ever see two labels: the admin-side build/test churn is collapsed into
// "Processing", and only `resolved` is "Ready". Unknown or null statuses fall
// back to Processing so a raw internal value can never reach the UI.
export type ClientParserStatus = 'processing' | 'ready'

export interface ClientParserStatusDisplay {
  key: ClientParserStatus
  label: string
}

export function toClientParserStatus(status: string | null | undefined): ClientParserStatusDisplay {
  if (status === 'resolved') return { key: 'ready', label: 'Ready' }
  return { key: 'processing', label: 'Processing' }
}

// Rows created automatically from a failed in-deal upload have no bank name
// yet (an admin fills it in later). Fall back to the deal, then a generic label.
export function parserRequestLabel(r: { bank_name: string | null; deal_name: string | null }): string {
  if (r.bank_name) return r.bank_name
  return r.deal_name ? `Statement format for ${r.deal_name}` : 'Statement format request'
}
