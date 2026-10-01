import { useQuery } from '@tanstack/react-query'
import { listAccountParserRequests } from '@/lib/v1-api'

// Status is the whole point of this list. The app-wide default is
// staleTime: Infinity + localStorage persistence, which would pin a request at
// "Processing" forever after an admin resolves it — so always refetch on
// mount/focus and poll while a page that shows it is open.
export const accountParserRequestsKey = (userId: string | undefined) => ['account-parser-requests', userId] as const

export function useAccountParserRequests(userId: string | undefined) {
  return useQuery({
    queryKey: accountParserRequestsKey(userId),
    queryFn: listAccountParserRequests,
    enabled: !!userId,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: 'always',
    refetchInterval: 60_000,
  })
}
