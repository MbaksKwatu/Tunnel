import { redirect } from 'next/navigation'

export default async function DealDetailPage({ params }: { params: Promise<{ deal_id: string }> }) {
  const { deal_id } = await params
  redirect(`/v1/deal?deal_id=${deal_id}`)
}
