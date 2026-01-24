import DealDetail from '@/components/DealDetail'
import ProtectedRoute from '@/components/ProtectedRoute'

interface Props {
  params: {
    deal_id: string
  }
}

export default function DealPage({ params }: Props) {
  return (
    <ProtectedRoute>
      <DealDetail dealId={params.deal_id} />
    </ProtectedRoute>
  )
}
