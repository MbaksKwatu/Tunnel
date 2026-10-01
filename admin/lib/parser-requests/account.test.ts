import { describe, it, expect } from 'vitest'
import {
  mechanismFor, partnerDisplay, clientAccount, accountLabel, matchesPartnerFilter, UNATTRIBUTED,
} from './account'

describe('mechanism vs account are separate', () => {
  it('maps the table of origin to a mechanism, independent of account', () => {
    expect(mechanismFor(true)).toBe('Auto')
    expect(mechanismFor(false)).toBe('Submitted')
  })
  it('never guesses an account: null stays null and is labelled honestly', () => {
    expect(clientAccount(null)).toBeNull()
    expect(clientAccount('  ')).toBeNull()
    expect(accountLabel(clientAccount(undefined))).toBe(UNATTRIBUTED)
    expect(accountLabel('GBFund')).toBe('GBFund')
  })
  it('normalises Musa-side partner ids for display only', () => {
    expect(partnerDisplay('musa')).toBe('Musa')
    expect(partnerDisplay('gbfund')).toBe('GBFund')
    expect(partnerDisplay('acme')).toBe('acme')
    expect(partnerDisplay(null)).toBeNull()
  })
})

describe('partner filter chips', () => {
  const musaAuto = { isAuto: true, account: 'Musa' }
  const gbAuto = { isAuto: true, account: 'GBFund' }
  const gbSubmitted = { isAuto: false, account: 'GBFund' } // the SBM request
  const unattributed = { isAuto: false, account: null }

  it('GBFund now includes a pds_parser_requests (Submitted) row', () => {
    expect(matchesPartnerFilter(gbSubmitted, 'GBFund')).toBe(true)
    expect(matchesPartnerFilter(gbAuto, 'GBFund')).toBe(true)
  })
  it('Musa and GBFund do not cross-match; unattributed matches neither', () => {
    expect(matchesPartnerFilter(musaAuto, 'GBFund')).toBe(false)
    expect(matchesPartnerFilter(gbSubmitted, 'Musa')).toBe(false)
    expect(matchesPartnerFilter(unattributed, 'GBFund')).toBe(false)
  })
  it('Submitted is the mechanism filter; All matches everything', () => {
    expect(matchesPartnerFilter(gbSubmitted, 'Submitted')).toBe(true)
    expect(matchesPartnerFilter(unattributed, 'Submitted')).toBe(true)
    expect(matchesPartnerFilter(musaAuto, 'Submitted')).toBe(false)
    for (const r of [musaAuto, gbAuto, gbSubmitted, unattributed]) expect(matchesPartnerFilter(r, 'All')).toBe(true)
  })
})
