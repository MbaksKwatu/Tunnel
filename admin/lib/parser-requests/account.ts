// Source mechanism vs. account for the admin Parser Requests queue.
//
// The queue used to render one overloaded tag ("Auto · Musa" / "Manual") that
// was really which TABLE a row came from. These two concerns are separate:
//   mechanism — how the request arose: 'Auto' (Musa's pipeline, parser_requests)
//               or 'Submitted' (pds_parser_requests: form, upload auto-detect,
//               partner API route);
//   account   — which client it belongs to. Stored, never guessed: for client
//               rows it is pds_parser_requests.account_name (NULL = unattributed).

export type Mechanism = 'Auto' | 'Submitted'

export const UNATTRIBUTED = 'Unattributed'

const PARTNER_DISPLAY: Record<string, string> = { musa: 'Musa', gbfund: 'GBFund' }

export function mechanismFor(isAuto: boolean): Mechanism {
  return isAuto ? 'Auto' : 'Submitted'
}

// Display name for a parser_requests.partner value ('musa' -> 'Musa').
export function partnerDisplay(partner: string | null | undefined): string | null {
  const p = partner?.trim()
  if (!p) return null
  return PARTNER_DISPLAY[p.toLowerCase()] ?? p
}

// Stored account name for a client-table row; null stays null (not guessed).
export function clientAccount(accountName: string | null | undefined): string | null {
  return accountName?.trim() || null
}

export function accountLabel(account: string | null): string {
  return account ?? UNATTRIBUTED
}

export const PARTNER_FILTERS = ['All', 'Musa', 'GBFund', 'Submitted'] as const
export type PartnerFilter = (typeof PARTNER_FILTERS)[number]

// 'Submitted' filters on mechanism; the account chips (Musa, GBFund) filter on
// the account across BOTH tables — previously GBFund could only match
// parser_requests rows, so a GBFund request in pds_parser_requests never
// showed under it.
export function matchesPartnerFilter(
  row: { isAuto: boolean; account: string | null },
  filter: PartnerFilter,
): boolean {
  if (filter === 'All') return true
  if (filter === 'Submitted') return !row.isAuto
  return row.account?.toLowerCase() === filter.toLowerCase()
}
