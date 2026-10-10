import { describe, it, expect, vi, beforeEach } from 'vitest'

const getUserMock = vi.fn()
const getAllMock = vi.fn(() => [])

vi.mock('next/headers', () => ({
  cookies: async () => ({ getAll: getAllMock }),
}))

vi.mock('@supabase/ssr', () => ({
  createServerClient: () => ({
    auth: { getUser: getUserMock },
  }),
}))

describe('getOntologyQaVisibility', () => {
  beforeEach(() => {
    getUserMock.mockReset()
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://example.supabase.co'
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'anon-key'
  })

  it('is false when there is no session', async () => {
    getUserMock.mockResolvedValue({ data: { user: null } })
    const { getOntologyQaVisibility } = await import('./get-ontology-qa-visibility')
    expect(await getOntologyQaVisibility()).toBe(false)
  })

  it('is false for a non-allowlisted session', async () => {
    getUserMock.mockResolvedValue({ data: { user: { email: 'stranger@example.com' } } })
    const { getOntologyQaVisibility } = await import('./get-ontology-qa-visibility')
    expect(await getOntologyQaVisibility()).toBe(false)
  })

  it('is true for an allowlisted session, case-insensitively', async () => {
    getUserMock.mockResolvedValue({ data: { user: { email: 'INFO@paritytunnel.com' } } })
    const { getOntologyQaVisibility } = await import('./get-ontology-qa-visibility')
    expect(await getOntologyQaVisibility()).toBe(true)
  })

  it('degrades to false when the session lookup throws', async () => {
    getUserMock.mockRejectedValue(new Error('boom'))
    const { getOntologyQaVisibility } = await import('./get-ontology-qa-visibility')
    await expect(getOntologyQaVisibility()).resolves.toBe(false)
  })
})
