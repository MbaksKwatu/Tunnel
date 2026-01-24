import DealCreate from '@/components/DealCreate'
import ProtectedRoute from '@/components/ProtectedRoute'

export default function NewDealPage() {
  return (
    <ProtectedRoute>
      <DealCreate />
    </ProtectedRoute>
  )
}
