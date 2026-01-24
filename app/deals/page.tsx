import DealList from '@/components/DealList'
import ProtectedRoute from '@/components/ProtectedRoute'

export default function DealsPage() {
  return (
    <ProtectedRoute>
      <DealList />
    </ProtectedRoute>
  )
}
