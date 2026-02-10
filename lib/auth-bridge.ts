/**
 * Bridge so API calls use the same session AuthProvider has.
 * Fixes 401 when getSession() isn't ready yet on first request.
 */
let _apiToken: string | null = null

export function setApiToken(token: string | null) {
  _apiToken = token
}

export function getApiToken(): string | null {
  return _apiToken
}
