import { redirect } from 'next/navigation'

// "New Bank Format" (deal-scoped Format Desk link) was replaced by the
// account-level Bank Parsers page. Kept as a redirect so old links/bookmarks
// don't 404.
export default function LegacyRequestParserPage() {
  redirect('/parsers')
}
