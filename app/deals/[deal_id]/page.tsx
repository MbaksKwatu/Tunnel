import DealDetail from '@/components/DealDetail'

interface Props {
  params: {
    deal_id: string
  }
}

export default function DealPage({ params }: Props) {
  return <DealDetail dealId={params.deal_id} />
}
