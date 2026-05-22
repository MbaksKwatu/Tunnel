import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Protected route prefixes
const PROTECTED = ['/deals/']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  const isProtected = PROTECTED.some((prefix) => pathname.startsWith(prefix))
  if (!isProtected) return NextResponse.next()

  // sb-auth-hint is set by AuthProvider on SIGNED_IN and cleared on SIGNED_OUT.
  // This is a UX-level guard; client-side auth checks provide the actual security.
  const hasSession = request.cookies.has('sb-auth-hint')
  if (!hasSession) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('next', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/deals/:path*'],
}
