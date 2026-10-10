import { describe, it, expect } from 'vitest'
import { ONTOLOGY_QA_EMAILS, isOntologyQaAllowed } from './ontology-qa-access'

describe('isOntologyQaAllowed', () => {
  it('rejects null, undefined and empty', () => {
    expect(isOntologyQaAllowed(null)).toBe(false)
    expect(isOntologyQaAllowed(undefined)).toBe(false)
    expect(isOntologyQaAllowed('')).toBe(false)
  })

  it('rejects emails that are not allowlisted', () => {
    expect(isOntologyQaAllowed('stranger@example.com')).toBe(false)
  })

  it.each(ONTOLOGY_QA_EMAILS)('accepts %s in any case', (email) => {
    expect(isOntologyQaAllowed(email)).toBe(true)
    expect(isOntologyQaAllowed(email.toUpperCase())).toBe(true)
    expect(isOntologyQaAllowed(email.toLowerCase())).toBe(true)
  })
})
