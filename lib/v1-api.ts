import { fetchApi } from './api'

const BASE = '/v1'

export interface AccrualInput {
  accrual_revenue_cents?: number
  accrual_period_start?: string
  accrual_period_end?: string
}

export interface Deal {
  id: string
  currency: string
  name?: string
  created_by?: string
  accrual_revenue_cents?: number
  accrual_period_start?: string
  accrual_period_end?: string
}

export interface AnalysisRun {
  id: string
  deal_id: string
  non_transfer_abs_total_cents: number
  coverage_pct_bp: number
  reconciliation_status: 'OK' | 'NOT_RUN' | 'FAILED_OVERLAP'
  reconciliation_pct_bp: number | null
  final_confidence_bp: number
  tier: 'Low' | 'Medium' | 'High'
  bank_operational_inflow_cents: number
  [key: string]: unknown
}

export interface Snapshot {
  id: string
  sha256_hash: string
  financial_state_hash: string
  [key: string]: unknown
}

export interface Entity {
  entity_id: string
  deal_id: string
  display_name: string
  [key: string]: unknown
}

export interface TxnEntityMapping {
  txn_id: string
  entity_id: string
  role: string
  [key: string]: unknown
}

export interface ExportResponse {
  analysis_run: AnalysisRun
  snapshot: Snapshot
  entities: Entity[]
  txn_entity_map: TxnEntityMapping[]
}

export async function createDeal(
  currency: string,
  name?: string,
  accrual?: AccrualInput
): Promise<{ deal: Deal }> {
  const form = new FormData()
  form.append('currency', currency)
  if (name) form.append('name', name)
  if (accrual?.accrual_revenue_cents != null)
    form.append('accrual_revenue_cents', String(accrual.accrual_revenue_cents))
  if (accrual?.accrual_period_start)
    form.append('accrual_period_start', accrual.accrual_period_start)
  if (accrual?.accrual_period_end)
    form.append('accrual_period_end', accrual.accrual_period_end)
  const res = await fetchApi(`${BASE}/deals`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function uploadDocument(
  dealId: string,
  file: File
): Promise<{ ingestion: { document_id: string; rows_count: number } }> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetchApi(`${BASE}/deals/${dealId}/documents`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getDocumentStatus(
  documentId: string
): Promise<{ document_id: string; status: string }> {
  const res = await fetchApi(`${BASE}/documents/${documentId}/status`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function exportSnapshot(
  dealId: string
): Promise<ExportResponse> {
  const res = await fetchApi(`${BASE}/deals/${dealId}/export`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getDocumentTransactions(
  documentId: string
): Promise<{ document_id: string; transactions: Array<Record<string, unknown>> }> {
  const res = await fetchApi(`${BASE}/documents/${documentId}/transactions`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function listDocuments(
  dealId: string
): Promise<{ documents: Array<{ id: string; status: string }> }> {
  const res = await fetchApi(`${BASE}/deals/${dealId}/documents`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function addOverride(
  dealId: string,
  entityId: string,
  newValue: string,
  note?: string
): Promise<{ override: Record<string, unknown> }> {
  const form = new FormData()
  form.append('entity_id', entityId)
  form.append('new_value', newValue)
  if (note) form.append('reason', note)
  const res = await fetchApi(`${BASE}/deals/${dealId}/overrides`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function listOverrides(
  dealId: string
): Promise<{ overrides: Array<Record<string, unknown>> }> {
  const res = await fetchApi(`${BASE}/deals/${dealId}/overrides`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
