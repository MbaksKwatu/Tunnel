import { fetchApi, API_URL } from './api'
import { createBrowserClient } from './supabase'
import { getApiToken, setApiToken } from './auth-bridge'

const BASE = '/v1'

/**
 * POST multipart to /v1 without a default JSON Content-Type.
 * fetch() must set multipart boundary automatically — never pass Content-Type here.
 */
async function fetchApiFormData(
  endpoint: string,
  init: RequestInit & { body: FormData }
): Promise<Response> {
  if (!endpoint.startsWith('/v1')) {
    throw new Error(
      `Legacy API call blocked: "${endpoint}". All API calls must use /v1/* routes.`
    )
  }
  const url = `${API_URL}${endpoint}`
  const supabase = createBrowserClient()
  let token = getApiToken()
  if (!token && supabase) {
    try {
      const { data } = await supabase.auth.getSession()
      token = data.session?.access_token ?? null
      if (token) setApiToken(token)
    } catch {
      /* continue without auth */
    }
  }
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(url, { ...init, headers })
  if (res.status === 401 && supabase && token) {
    try {
      const { data } = await supabase.auth.refreshSession()
      if (data.session?.access_token) {
        setApiToken(data.session.access_token)
        headers.Authorization = `Bearer ${data.session.access_token}`
        return fetch(url, { ...init, headers })
      }
    } catch {
      /* return original response */
    }
  }
  return res
}

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
  /** Distinct batch uploads used (1–4); usually derived client-side from documents if not on deal row */
  batch_upload_count?: number
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
  const res = await fetchApiFormData(`${BASE}/deals`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function uploadDocument(
  dealId: string,
  file: File
): Promise<{
  ingestion: { document_id: string; rows_count: number };
  detectedCurrency?: string;
}> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetchApiFormData(`${BASE}/deals/${dealId}/documents`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export interface DocumentStatusResponse {
  document_id: string
  status: string
  error?: string
  error_type?: string
  error_message?: string
  stage?: string
  next_action?: string
  traceback?: string
  currency_detected?: string
  analytics?: {
    monthly_cashflow?: Array<Record<string, unknown>>
    credit_scoring_inputs?: Record<string, unknown>
    monthly_entity_breakdown?: Array<Record<string, unknown>>
    [key: string]: unknown
  }
}

export async function getDocumentStatus(
  documentId: string
): Promise<DocumentStatusResponse> {
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

export interface DocumentListItem {
  id: string
  status: string
  batch_number?: number | null
  is_batch_upload?: boolean | null
  [key: string]: unknown
}

export async function listDocuments(
  dealId: string
): Promise<{ documents: DocumentListItem[] }> {
  const res = await fetchApi(`${BASE}/deals/${dealId}/documents`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export interface BatchUploadResponse {
  document_id: string
  batch_number: number
  batches_remaining: number
  files_merged: number
  source_files: string[]
  status: string
  message: string
  ingestion: { document_id: string; status: string; rows_count: number }
}

export async function uploadDocumentsBatch(
  dealId: string,
  files: File[]
): Promise<BatchUploadResponse> {
  const form = new FormData()
  for (const f of files) {
    form.append('files', f)
  }
  const res = await fetchApiFormData(`${BASE}/deals/${dealId}/documents/batch`, {
    method: 'POST',
    body: form,
  })
  const text = await res.text()
  if (!res.ok) {
    let msg = text?.slice(0, 500) || `Upload failed (${res.status})`
    try {
      const j = JSON.parse(text) as { detail?: string | { error_message?: string } }
      const d = j.detail
      if (typeof d === 'string') msg = d
      else if (d && typeof d === 'object' && 'error_message' in d && d.error_message)
        msg = String(d.error_message)
    } catch {
      /* keep msg */
    }
    throw new Error(msg)
  }
  try {
    return JSON.parse(text) as BatchUploadResponse
  } catch {
    throw new Error('Invalid response from batch upload')
  }
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
  const res = await fetchApiFormData(`${BASE}/deals/${dealId}/overrides`, {
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

export async function askParity(
  dealId: string,
  question: string
): Promise<{ answer: string; intent: string | null }> {
  const res = await fetchApi(`${BASE}/deals/${dealId}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
