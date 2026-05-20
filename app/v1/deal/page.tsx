'use client';

import { useState, useCallback, useEffect, useMemo, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useDropzone } from 'react-dropzone';
import { supabase } from '@/lib/supabase';
import {
  createDeal,
  uploadDocument,
  uploadAuditedFinancials,
  getAuditedFinancials,
  patchAuditedFinancials,
  getDocumentStatus,
  exportSnapshot,
  getDocumentTransactions,
  addOverride,
  listOverrides,
  listDocuments,
  deleteDocument,
  askParity,
  exportTransactionsCsv,
  getNeedsReview,
} from '@/lib/v1-api';
import { BatchUpload } from '@/components/BatchUpload';
import type {
  Deal,
  AnalysisRun,
  Snapshot,
  Entity,
  TxnEntityMapping,
  ExportResponse,
  DocumentListItem,
  AuditedFinancialsRecord,
} from '@/lib/v1-api';
// generateParityPdf is loaded dynamically at click time so Next.js never
// evaluates jsPDF's Node.js build during server compilation.
type GeneratePdfFn = typeof import('@/lib/generate-parity-pdf').generateParityPdf;

const CURRENCIES = ['USD', 'EUR', 'GBP', 'KES', 'NGN'];
const MAX_STATEMENTS = 20;

type AnalysisState = 'idle' | 'uploading' | 'polling' | 'exporting' | 'done' | 'error';

interface EntityBreakdownRow {
  entityId: string;
  entityName: string;
  role: string;
  totalAbsCents: number;
  pctBps: number; // basis points, display as pctBps/100 + '%'
  txnCount: number;
}

interface QueuedStatement {
  id: string;
  fileName: string;
  status: 'uploading' | 'processing' | 'ready' | 'failed';
}

/** Normalize API status (list + status endpoints; lease may surface failed). */
function apiDocumentStatus(doc: Pick<DocumentListItem, 'status'>): 'completed' | 'failed' | 'processing' {
  const s = String(doc.status ?? '').toLowerCase();
  if (s === 'completed') return 'completed';
  if (s === 'failed') return 'failed';
  return 'processing';
}

/** Basis-point percentage: (entity_amount_cents * 10000) // total_category_cents. No floats. */
function pctBpsFromCents(entityCents: number, totalCategoryCents: number): number {
  if (totalCategoryCents <= 0) return 0;
  return Math.floor((entityCents * 10000) / totalCategoryCents);
}

/** Ensure percentages sum to 10000 bps (100.0%). Apply residual to largest entity. */
function normalizePctBpsTo100(
  rows: Array<{ totalAbsCents: number; pctBps: number }>
): number[] {
  const totalBps = rows.reduce((s, r) => s + r.pctBps, 0);
  const residual = 10000 - totalBps;
  if (residual === 0) return rows.map((r) => r.pctBps);
  const sorted = [...rows].map((r, i) => ({ ...r, i })).sort((a, b) => b.totalAbsCents - a.totalAbsCents);
  const result = rows.map((r) => r.pctBps);
  result[sorted[0].i] = result[sorted[0].i] + residual;
  return result;
}

function V1DealPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (!supabase) { router.replace('/login'); return; }
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) router.replace('/login');
    });
  }, [router]);

  // Pre-load deal from URL param (set by /deals/new)
  useEffect(() => {
    const urlDealId = searchParams.get('deal_id');
    if (!urlDealId || deal) return;
    setDeal({ id: urlDealId, currency: 'USD' });
    void refreshBatchUploadCount(urlDealId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const [file, setFile] = useState<File | null>(null);
  const [currency, setCurrency] = useState('USD');
  const [dealName, setDealName] = useState('');
  const [accrualRevenueCents, setAccrualRevenueCents] = useState('');
  const [accrualPeriodStart, setAccrualPeriodStart] = useState('');
  const [accrualPeriodEnd, setAccrualPeriodEnd] = useState('');
  const [deal, setDeal] = useState<Deal | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [analysisState, setAnalysisState] = useState<AnalysisState>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [exportData, setExportData] = useState<ExportResponse | null>(null);
  const [overrideEntityId, setOverrideEntityId] = useState('');
  const [overrideRole, setOverrideRole] = useState('supplier');
  const [overrideNote, setOverrideNote] = useState('');
  const [overrideSaving, setOverrideSaving] = useState(false);
  const [overrideSuccess, setOverrideSuccess] = useState('');
  const [overrideError, setOverrideError] = useState('');
  const [overridesList, setOverridesList] = useState<Array<Record<string, unknown>>>([]);
  const [exportSuccess, setExportSuccess] = useState('');
  const [exportError, setExportError] = useState('');
  const [lastExportedAt, setLastExportedAt] = useState<Date | null>(null);
  const [rawTransactions, setRawTransactions] = useState<Array<Record<string, unknown>>>([]);
  const [monthlyCashflow, setMonthlyCashflow] = useState<Array<Record<string, unknown>>>([]);
  const [creditScoringInputs, setCreditScoringInputs] = useState<Record<string, unknown> | null>(null);
  const [monthlyEntityBreakdown, setMonthlyEntityBreakdown] = useState<Array<Record<string, unknown>>>([]);
  const [reviewQuestion, setReviewQuestion] = useState('');
  const [reviewAnswer, setReviewAnswer] = useState('');
  const [reviewLoading, setReviewLoading] = useState(false);
  const [dealDocuments, setDealDocuments] = useState<DocumentListItem[]>([]);
  const [auditedFinancialsList, setAuditedFinancialsList] = useState<AuditedFinancialsRecord[]>([]);
  const [auditedConfirmForm, setAuditedConfirmForm] = useState<AuditedFinancialsRecord | null>(null);
  const [auditedUploading, setAuditedUploading] = useState(false);
  const [auditedUploadError, setAuditedUploadError] = useState('');
  const [auditedSaving, setAuditedSaving] = useState(false);
  const [declarationType, setDeclarationType] = useState<'audited' | 'management'>('audited');
  const [statementQueue, setStatementQueue] = useState<QueuedStatement[]>([]);
  const [activeTab, setActiveTab] = useState<'documents' | 'analysis' | 'review' | 'snapshot'>('documents');
  const docTypeByDocId = useRef<Map<string, 'bank' | 'audited'>>(new Map());
  type ChatMessage = { role: 'analyst' | 'parity'; text: string; time: string }
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [needsReviewItems, setNeedsReviewItems] = useState<Array<Record<string, unknown>>>([]);

  // Unknown-parser request modal state
  interface ParserRequestDoc { docId: string; fileName: string; errorMessage: string }
  const [unknownParserDoc, setUnknownParserDoc] = useState<ParserRequestDoc | null>(null);
  const [parserRequestForm, setParserRequestForm] = useState({ bankName: '', country: 'Kenya', accountType: 'Business Current', notes: '' });
  const [parserRequestSubmitting, setParserRequestSubmitting] = useState(false);
  const [parserRequestSubmitted, setParserRequestSubmitted] = useState(false);
  const checkedFailedDocs = useRef<Set<string>>(new Set());
  // Tracks doc IDs confirmed as "unsupported format" — used to show inline CTA in FileRow
  const [unknownFormatDocIds, setUnknownFormatDocIds] = useState<Set<string>>(new Set());

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length) setFile(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/pdf': ['.pdf'],
      'application/octet-stream': ['.pdf'],
    },
    maxFiles: 1,
  });

  const refreshBatchUploadCount = useCallback(
    async (dealIdOverride?: string): Promise<DocumentListItem[] | undefined> => {
      const id = dealIdOverride ?? deal?.id;
      if (!id) return undefined;
      try {
        const { documents } = await listDocuments(id);
        setDealDocuments(documents);
        return documents;
      } catch {
        setDealDocuments([]);
        return undefined;
      }
    },
    [deal]
  );

  const loadAuditedFinancials = useCallback(async (dealIdOverride?: string) => {
    const id = dealIdOverride ?? deal?.id;
    if (!id) return;
    try {
      const { records } = await getAuditedFinancials(id);
      setAuditedFinancialsList(records);
    } catch {
      // non-fatal
    }
  }, [deal]);

  useEffect(() => {
    if (!deal?.id) return;
    void refreshBatchUploadCount();
    void loadAuditedFinancials();
  }, [deal?.id, refreshBatchUploadCount, loadAuditedFinancials]);

  useEffect(() => {
    setStatementQueue((prev) => {
      const mapPrevById = new Map(prev.map((item) => [item.id, item]));
      return dealDocuments.map((doc, idx) => {
        const previous = mapPrevById.get(doc.id);
        const ns = apiDocumentStatus(doc);
        const normalizedStatus: QueuedStatement['status'] =
          ns === 'completed' ? 'ready' : ns === 'failed' ? 'failed' : 'processing';
        return {
          id: doc.id,
          fileName: previous?.fileName ?? `Statement ${idx + 1}`,
          status: previous?.status === 'uploading' ? 'uploading' : normalizedStatus,
        };
      });
    });
  }, [dealDocuments]);

  const handleStatementDrop = useCallback(
    async (nextFile: File) => {
      if (!deal) return;
      // Statement queue: pass the dropped File through to uploadDocument as multipart (no JSON).
      const tempId = crypto.randomUUID();
      setStatementQueue((prev) => [
        ...prev,
        {
          id: tempId,
          fileName: nextFile.name,
          status: 'uploading',
        },
      ]);
      try {
        const result = await uploadDocument(deal.id, nextFile);
        const docId = result.ingestion.document_id;
        setStatementQueue((prev) =>
          prev.map((item) =>
            item.id === tempId ? { ...item, id: docId, status: 'processing' } : item
          )
        );
        void refreshBatchUploadCount(deal.id);
      } catch {
        setStatementQueue((prev) =>
          prev.map((item) => (item.id === tempId ? { ...item, status: 'failed' } : item))
        );
      }
    },
    [deal, refreshBatchUploadCount]
  );

  const handleBankDrop = useCallback(async (nextFile: File) => {
    if (!deal) return;
    const tempId = crypto.randomUUID();
    docTypeByDocId.current.set(tempId, 'bank');
    setStatementQueue((prev) => [...prev, { id: tempId, fileName: nextFile.name, status: 'uploading' }]);
    try {
      const result = await uploadDocument(deal.id, nextFile);
      const docId = result.ingestion.document_id;
      docTypeByDocId.current.delete(tempId);
      docTypeByDocId.current.set(docId, 'bank');
      setStatementQueue((prev) => prev.map((item) => item.id === tempId ? { ...item, id: docId, status: 'processing' } : item));
      void refreshBatchUploadCount(deal.id);
    } catch {
      setStatementQueue((prev) => prev.map((item) => item.id === tempId ? { ...item, status: 'failed' } : item));
    }
  }, [deal, refreshBatchUploadCount]);

  const handleAuditedDrop = useCallback(async (nextFile: File) => {
    if (!deal) return;
    setAuditedUploading(true);
    setAuditedUploadError('');
    try {
      const result = await uploadAuditedFinancials(deal.id, nextFile, declarationType);
      // Pre-populate the confirmation form with extracted fields
      setAuditedConfirmForm({
        deal_id: deal.id,
        financial_year: result.financial_year,
        financial_year_start: result.financial_year_start,
        financial_year_end: result.financial_year_end,
        company_name: result.company_name ?? '',
        declaration_type: declarationType,
        turnover_cents: result.turnover_cents ?? null,
        profit_after_tax_cents: result.profit_after_tax_cents ?? null,
        total_assets_cents: result.total_assets_cents ?? null,
        cash_and_equivalents_cents: result.cash_and_equivalents_cents ?? null,
        extraction_confidence: result.extraction_confidence,
      });
      void loadAuditedFinancials(deal.id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setAuditedUploadError(msg);
      // Still open the form for manual entry
      setAuditedConfirmForm({ deal_id: deal.id, declaration_type: declarationType });
    } finally {
      setAuditedUploading(false);
    }
  }, [deal, declarationType, loadAuditedFinancials]);

  // One listDocuments poll at a time (sequential), not overlapping setInterval + async —
  // slow responses were stacking many pending /documents requests and starving the worker.
  const statementQueueHasProcessing = useMemo(
    () => statementQueue.some((item) => item.status === 'processing'),
    [statementQueue]
  );

  useEffect(() => {
    if (!deal?.id || !statementQueueHasProcessing) return;

    const POLL_MS = 5000;
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout>;

    const scheduleNext = () => {
      timeoutId = setTimeout(run, POLL_MS);
    };

    const run = async () => {
      if (cancelled) return;
      try {
        const { documents } = await listDocuments(deal.id);
        if (cancelled) return;
        setDealDocuments(documents);
        const byId = new Map(documents.map((d) => [d.id, d]));

        // Collect newly-failed bank docs to check for unknown parser
        const newlyFailed: Array<{ id: string; fileName: string }> = [];

        setStatementQueue((prev) => {
          const next = prev.map((q) => {
            if (q.status !== 'processing') return q;
            const doc = byId.get(q.id);
            if (!doc) return q;
            const ns = apiDocumentStatus(doc);
            if (ns === 'completed') return { ...q, status: 'ready' as const };
            if (ns === 'failed') {
              // Only check bank docs (not audited), and only once per doc
              if (docTypeByDocId.current.get(q.id) !== 'audited' && !checkedFailedDocs.current.has(q.id)) {
                newlyFailed.push({ id: q.id, fileName: q.fileName });
              }
              return { ...q, status: 'failed' as const };
            }
            return q;
          });
          return next;
        });

        // Outside setStatementQueue to avoid React state updates inside updater
        for (const { id, fileName } of newlyFailed) {
          if (cancelled || checkedFailedDocs.current.has(id)) continue;
          checkedFailedDocs.current.add(id);
          try {
            const statusRes = await getDocumentStatus(id);
            const errType = statusRes.error_type ?? '';
            const errMsg = (statusRes.error_message ?? statusRes.error ?? '').toLowerCase();
            const isUnknownParser =
              errType === 'InvalidSchemaError' &&
              (errMsg.includes('not recognised') || errMsg.includes('not recognized') || errMsg.includes('unsupported') || errMsg.includes('no valid transactions'));
            if (isUnknownParser) {
              setUnknownParserDoc({ docId: id, fileName, errorMessage: statusRes.error_message ?? statusRes.error ?? 'Bank format not recognised' });
              setUnknownFormatDocIds((prev) => new Set([...prev, id]));
            }
          } catch {
            // silently skip — this is a best-effort enrichment
          }
        }
      } catch {
        // ignore poll errors (network / transient 503)
      }
      if (!cancelled) scheduleNext();
    };

    void run();
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [deal?.id, statementQueueHasProcessing]);

  const runAnalysis = async () => {
    setErrorMsg('');
    try {
      let activeDeal = deal;

      if (!activeDeal) {
        if (!file) {
          setErrorMsg('Please select a file');
          return;
        }
        setAnalysisState('uploading');
        const accrual =
          accrualRevenueCents && accrualPeriodStart && accrualPeriodEnd
            ? {
                accrual_revenue_cents: parseInt(accrualRevenueCents, 10) || 0,
                accrual_period_start: accrualPeriodStart,
                accrual_period_end: accrualPeriodEnd,
              }
            : undefined;

        const { deal: createdDeal } = await createDeal(currency, dealName || undefined, accrual);
        setDeal(createdDeal);
        activeDeal = createdDeal;

        const { ingestion } = await uploadDocument(createdDeal.id, file);
        setDocumentId(ingestion.document_id);

        setAnalysisState('polling');
        const POLL_INTERVAL_MS = 3000;
        const MAX_WAIT_MS = 30 * 60 * 1000;
        const pollDeadline = Date.now() + MAX_WAIT_MS;
        let status = await getDocumentStatus(ingestion.document_id);
        while (status.status !== 'completed') {
          if (status.status === 'failed') {
            const errType = status.error_type || 'UnknownError';
            const errMsg = status.error_message || status.error || 'Document processing failed';
            const stage = status.stage || '';
            const nextAction = status.next_action || '';
            setErrorMsg(
              stage
                ? `${errType}: ${errMsg} (stage: ${stage}, next: ${nextAction})`
                : `${errType}: ${errMsg}`
            );
            setAnalysisState('error');
            return;
          }
          if (Date.now() >= pollDeadline) {
            setErrorMsg(
              'Still processing after 30 minutes. Large PDFs can be slow on a cold server—try again in a few minutes, or use Batch upload for monthly statements. The document may still complete in the background.'
            );
            setAnalysisState('error');
            return;
          }
          await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
          status = await getDocumentStatus(ingestion.document_id);
        }
        if (status.currency_detected) {
          setCurrency(status.currency_detected);
        }
        if (status.analytics?.monthly_cashflow) {
          setMonthlyCashflow(status.analytics.monthly_cashflow);
        }
        if (status.analytics?.credit_scoring_inputs) {
          setCreditScoringInputs(status.analytics.credit_scoring_inputs);
        }
        if ((status as any).analytics?.monthly_entity_breakdown) {
          setMonthlyEntityBreakdown((status as any).analytics.monthly_entity_breakdown);
        }
      } else {
        const docs = await refreshBatchUploadCount(activeDeal.id);
        const allComplete = (docs ?? []).every((doc) => doc.status === 'completed');
        if (!allComplete) {
          const stillProcessing = (docs ?? []).filter(
            (doc) => doc.status === 'processing' || doc.status === 'pending'
          );
          setErrorMsg(
            stillProcessing.length > 0
              ? `${stillProcessing.length} document(s) still processing. Please wait a moment and try again.`
              : 'Some documents are not ready. Please wait a moment and try again.'
          );
          return;
        }
      }

      setAnalysisState('exporting');
      const data = await exportSnapshot(activeDeal.id);
      setExportData(data);
      setLastExportedAt(new Date());
      setOverridesList([]);
      const documentsAfterExport = await refreshBatchUploadCount(activeDeal.id);
      if (documentsAfterExport && documentsAfterExport.length > 0) {
        const txRes = await getDocumentTransactions(documentsAfterExport[0].id);
        setRawTransactions(txRes.transactions as Array<Record<string, unknown>>);
      }
      setAnalysisState('done');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Analysis failed');
      setAnalysisState('error');
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    if (!deal) return;
    try {
      await deleteDocument(docId);
      setStatementQueue((prev) => prev.filter((item) => item.id !== docId));
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Could not remove document');
    }
  };

  const handleAddOverride = async () => {
    if (!deal || !overrideEntityId || !overrideRole) return;
    setOverrideSaving(true);
    setOverrideSuccess('');
    setOverrideError('');
    try {
      const { override } = await addOverride(deal.id, overrideEntityId, overrideRole, overrideNote || undefined);
      setOverridesList((prev) => [override, ...prev]);
      const data = await exportSnapshot(deal.id);
      setExportData(data);
      setLastExportedAt(new Date());
      setOverrideEntityId('');
      setOverrideNote('');
      setOverrideSuccess('Override saved — analysis updated.');
      setTimeout(() => setOverrideSuccess(''), 4000);
    } catch (e) {
      setOverrideError(e instanceof Error ? e.message : 'Override failed');
    } finally {
      setOverrideSaving(false);
    }
  };

  const handleDownloadCSV = async () => {
    if (!deal?.id) return;
    try {
      const res = await exportTransactionsCsv(deal.id);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `parity_transactions_${deal.id.slice(0, 8)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('CSV export failed:', e);
    }
  };

  const handleReExport = async () => {
    if (!deal) return;
    setAnalysisState('exporting');
    setExportSuccess('');
    setExportError('');
    try {
      // Server snapshot write happens here. PDF only generates after this resolves.
      const data = await exportSnapshot(deal.id);
      setExportData(data);
      setLastExportedAt(new Date());
      setAnalysisState('done');

      // Build entity breakdown from the freshly returned data to pass to PDF (same logic as entityBreakdownByCategory)
      const freshEntities = data.entities ?? [];
      const freshTxnMap = data.txn_entity_map ?? [];
      const byEntity: Record<string, { name: string; role: string; totalCents: number; count: number }> = {};
      const txnById: Record<string, number> = {};
      for (const t of rawTransactions) {
        const amt = Math.abs(Number(t.signed_amount_cents ?? 0));
        const tid = t.txn_id as string;
        const id = t.id as string | undefined;
        txnById[tid] = amt;
        if (id) txnById[id] = amt;
      }
      for (const m of freshTxnMap) {
        const eid = m.entity_id as string;
        const ent = freshEntities.find((e) => e.entity_id === eid);
        const absCents = txnById[m.txn_id as string] ?? 0;
        if (!byEntity[eid]) {
          byEntity[eid] = {
            name: ent?.display_name ?? eid,
            role: (m.role as string) ?? 'other',
            totalCents: 0,
            count: 0,
          };
        }
        byEntity[eid].totalCents += absCents;
        byEntity[eid].count += 1;
      }
      const byRole = new Map<string, Array<{ entityId: string; entityName: string; role: string; totalAbsCents: number; txnCount: number }>>();
      for (const [entityId, v] of Object.entries(byEntity)) {
        const list = byRole.get(v.role) ?? [];
        list.push({
          entityId,
          entityName: v.name,
          role: v.role,
          totalAbsCents: v.totalCents,
          txnCount: v.count,
        });
        byRole.set(v.role, list);
      }
      const pdfBreakdown: Array<EntityBreakdownRow & { pctOfTotal: number }> = [];
      for (const list of Array.from(byRole.values())) {
        const sorted = list.sort((a, b) => b.totalAbsCents - a.totalAbsCents);
        const totalCategoryCents = sorted.reduce((s, r) => s + r.totalAbsCents, 0);
        let pctBpsList: number[];
        if (totalCategoryCents <= 0) {
          pctBpsList = sorted.map(() => 0);
        } else if (sorted.length === 1) {
          pctBpsList = [10000];
        } else {
          const rawBps = sorted.map((r) => pctBpsFromCents(r.totalAbsCents, totalCategoryCents));
          pctBpsList = normalizePctBpsTo100(sorted.map((r, i) => ({ totalAbsCents: r.totalAbsCents, pctBps: rawBps[i] })));
        }
        for (let i = 0; i < sorted.length; i++) {
          pdfBreakdown.push({
            ...sorted[i],
            pctBps: pctBpsList[i],
            pctOfTotal: pctBpsList[i] / 100,
          });
        }
      }
      pdfBreakdown.sort((a, b) => b.totalAbsCents - a.totalAbsCents);

      const pdfTotalOutflow = pdfBreakdown
        .filter((r) => ['supplier', 'payroll'].includes(r.role))
        .reduce((s, r) => s + r.totalAbsCents, 0);
      const pdfPayrollTotal = pdfBreakdown
        .filter((r) => r.role === 'payroll')
        .reduce((s, r) => s + r.totalAbsCents, 0);
      const pdfTopSuppliers = pdfBreakdown.filter((r) => r.role === 'supplier').slice(0, 5);
      const pdfTopRevenue = pdfBreakdown
        .filter((r) => ['revenue_operational', 'revenue_non_operational'].includes(r.role))
        .slice(0, 5);
      const pdfLargestRevenuePct = pdfBreakdown
        .filter((r) => ['revenue_operational', 'revenue_non_operational'].includes(r.role))
        .reduce((max, r) => Math.max(max, r.pctOfTotal), 0);

      const { generateParityPdf } = await import('@/lib/generate-parity-pdf') as { generateParityPdf: GeneratePdfFn };
      generateParityPdf({
        deal,
        run: data.analysis_run,
        snapshot: data.snapshot,
        entities: freshEntities,
        entityBreakdown: pdfBreakdown,
        overridesList,
        txCount: rawTransactions.length,
        currency,
        topSuppliers: pdfTopSuppliers,
        topRevenue: pdfTopRevenue,
        totalOutflow: pdfTotalOutflow,
        payrollTotal: pdfPayrollTotal,
        largestRevenuePct: pdfLargestRevenuePct,
        monthlyCashflow: monthlyCashflow.length > 0 ? (monthlyCashflow as unknown as import('@/lib/generate-parity-pdf').MonthlyCashflowRow[]) : undefined,
        creditScoringInputs: creditScoringInputs ? (creditScoringInputs as unknown as import('@/lib/generate-parity-pdf').CreditScoringInputs) : undefined,
        monthlyEntityBreakdown: monthlyEntityBreakdown.length > 0 ? monthlyEntityBreakdown : undefined,
      });

      setExportSuccess('Snapshot saved. PDF downloading.');
      setTimeout(() => setExportSuccess(''), 5000);
    } catch (e) {
      setExportError(e instanceof Error ? e.message : 'Export failed');
      setAnalysisState('done');
    }
  };

  const handleAsk = async () => {
    if (!deal || !reviewQuestion.trim()) return;
    const question = reviewQuestion.trim();
    const now = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    setChatHistory((prev) => [...prev, { role: 'analyst', text: question, time: now }]);
    setReviewQuestion('');
    setReviewLoading(true);
    setReviewAnswer('');
    try {
      const { answer } = await askParity(deal.id, question);
      const answerTime = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setChatHistory((prev) => [...prev, { role: 'parity', text: answer, time: answerTime }]);
      setReviewAnswer(answer);
    } catch (e) {
      const errText = e instanceof Error ? e.message : 'Request failed';
      setChatHistory((prev) => [...prev, { role: 'parity', text: errText, time: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }]);
    } finally {
      setReviewLoading(false);
    }
  };

  // Load needs-review items when analysis completes
  useEffect(() => {
    if (analysisState === 'done' && deal?.id) {
      getNeedsReview(deal.id).then((res) => setNeedsReviewItems(res.transactions as unknown as Array<Record<string, unknown>>)).catch(() => {});
    }
  }, [analysisState, deal?.id]);

  const handleParserRequestSubmit = async () => {
    if (!unknownParserDoc || !parserRequestForm.bankName.trim()) return;
    setParserRequestSubmitting(true);
    try {
      // 1. Persist to Supabase (existing behaviour)
      const sbClient = supabase;
      if (sbClient) {
        await (sbClient as any).from('pds_parser_requests').insert({
          deal_id: deal?.id ?? null,
          document_id: unknownParserDoc.docId,
          original_filename: unknownParserDoc.fileName,
          bank_name: parserRequestForm.bankName.trim(),
          country: parserRequestForm.country,
          account_type: parserRequestForm.accountType,
          notes: parserRequestForm.notes.trim() || null,
          error_type: 'InvalidSchemaError',
          error_message: unknownParserDoc.errorMessage,
        });
      }

      // 2. Send email notification (best-effort — don't block on failure)
      fetch('/api/request-parser', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bank_name: parserRequestForm.bankName.trim(),
          country: parserRequestForm.country,
          account_type: parserRequestForm.accountType,
          notes: parserRequestForm.notes.trim() || '',
          deal_id: deal?.id ?? '',
          document_id: unknownParserDoc.docId,
          original_filename: unknownParserDoc.fileName,
        }),
      }).catch(() => {/* silently ignore email errors */});

      setParserRequestSubmitted(true);
    } catch {
      setParserRequestSubmitted(true); // still show confirmation even if insert fails
    } finally {
      setParserRequestSubmitting(false);
    }
  };

  const run = exportData?.analysis_run;
  const snapshot = exportData?.snapshot;
  const entities = exportData?.entities ?? [];
  const txnMap = exportData?.txn_entity_map ?? [];

  const entityBreakdownByCategory: Array<{
    role: string;
    rows: EntityBreakdownRow[];
    totalCents: number;
  }> = (() => {
    if (!exportData || rawTransactions.length === 0) return [];
    const byEntity: Record<
      string,
      { name: string; role: string; totalCents: number; count: number }
    > = {};
    const txnById: Record<string, number> = {};
    for (const t of rawTransactions) {
      const amt = Math.abs(Number(t.signed_amount_cents ?? 0));
      const tid = t.txn_id as string;
      const id = t.id as string | undefined;
      txnById[tid] = amt;
      if (id) txnById[id] = amt;
    }
    for (const m of txnMap) {
      const eid = m.entity_id;
      const ent = entities.find((e) => e.entity_id === eid);
      const absCents = txnById[m.txn_id as string] ?? 0;
      if (!byEntity[eid]) {
        byEntity[eid] = {
          name: ent?.display_name ?? eid,
          role: (m.role as string) ?? 'other',
          totalCents: 0,
          count: 0,
        };
      }
      byEntity[eid].totalCents += absCents;
      byEntity[eid].count += 1;
    }
    const byRole = new Map<string, Array<{ entityId: string; entityName: string; role: string; totalAbsCents: number; txnCount: number }>>();
    for (const [entityId, v] of Object.entries(byEntity)) {
      const list = byRole.get(v.role) ?? [];
      list.push({
        entityId,
        entityName: v.name,
        role: v.role,
        totalAbsCents: v.totalCents,
        txnCount: v.count,
      });
      byRole.set(v.role, list);
    }
    const result: Array<{ role: string; rows: EntityBreakdownRow[]; totalCents: number }> = [];
    for (const [role, list] of Array.from(byRole.entries())) {
      const sorted = list.sort((a, b) => b.totalAbsCents - a.totalAbsCents);
      const totalCategoryCents = sorted.reduce((s, r) => s + r.totalAbsCents, 0);
      let pctBpsList: number[];
      if (totalCategoryCents <= 0) {
        pctBpsList = sorted.map(() => 0);
      } else if (sorted.length === 1) {
        pctBpsList = [10000];
      } else {
        const rawBps = sorted.map((r) => pctBpsFromCents(r.totalAbsCents, totalCategoryCents));
        pctBpsList = normalizePctBpsTo100(sorted.map((r, i) => ({ totalAbsCents: r.totalAbsCents, pctBps: rawBps[i] })));
      }
      const rows: EntityBreakdownRow[] = sorted.map((r, i) => ({
        ...r,
        pctBps: pctBpsList[i],
      }));
      result.push({ role, rows, totalCents: totalCategoryCents });
    }
    result.sort((a, b) => b.totalCents - a.totalCents);
    return result;
  })();

  const entityBreakdown: EntityBreakdownRow[] = entityBreakdownByCategory.flatMap((c) => c.rows);

  const totalOutflow = entityBreakdown
    .filter((r) => ['supplier', 'payroll'].includes(r.role))
    .reduce((s, r) => s + r.totalAbsCents, 0);
  const payrollTotal = entityBreakdown
    .filter((r) => r.role === 'payroll')
    .reduce((s, r) => s + r.totalAbsCents, 0);
  const topSuppliers = entityBreakdown
    .filter((r) => r.role === 'supplier')
    .slice(0, 5);
  const topRevenue = entityBreakdown
    .filter((r) =>
      ['revenue_operational', 'revenue_non_operational'].includes(r.role)
    )
    .slice(0, 5);
  const largestRevenuePct =
    topRevenue.length > 0
      ? entityBreakdown
          .filter((r) =>
            ['revenue_operational', 'revenue_non_operational'].includes(r.role)
          )
          .reduce((max, r) => Math.max(max, r.pctBps / 100), 0)
      : 0;

  const queueHasPending = statementQueue.some(
    (item) => item.status === 'processing' || item.status === 'uploading'
  );
  const queueHasFailures = statementQueue.some((item) => item.status === 'failed');
  const queueAllReady = statementQueue.length > 0 && statementQueue.every((item) => item.status === 'ready');

  const formatCents = (c: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 2,
    }).format(c / 100);

  const dealId = deal?.id ?? searchParams.get('deal_id') ?? null;
  const dealShortId = dealId ? dealId.slice(0, 16).toUpperCase() : '—';
  const isProcessing = analysisState === 'uploading' || analysisState === 'polling' || analysisState === 'exporting';

  const bankQueue = statementQueue.filter((item) => docTypeByDocId.current.get(item.id) !== 'audited');
  const auditedQueue = statementQueue.filter((item) => docTypeByDocId.current.get(item.id) === 'audited');
  const bankReady = bankQueue.filter((i) => i.status === 'ready').length;
  const auditedReady = auditedQueue.filter((i) => i.status === 'ready').length;

  // Pipeline stage derived from analysisState
  type StageStatus = 'done' | 'active' | 'queued' | 'failed';
  const pipelineStages: Array<{ name: string; detail: string; progress: string; pct?: number; status: StageStatus }> = (() => {
    const totalDocs = statementQueue.length;
    const totalTxn = rawTransactions.length || 170;
    const totalEntities = entities.length || 21;
    const doneEntities = Math.max(Math.floor(totalEntities * 0.67), 0);
    if (analysisState === 'idle') return [
      { name: 'Document ingestion', detail: `${totalDocs} documents · SHA256 · canonicalised`, progress: `${totalDocs} / ${totalDocs}`, status: 'queued' },
      { name: 'Transaction parsing', detail: 'Layout detection · row parsing · 0 errors', progress: '— / —', status: 'queued' },
      { name: 'Classification', detail: 'Ontology v2.0 · 25 roles · integer arithmetic', progress: '— / —', status: 'queued' },
      { name: 'Entity extraction', detail: 'Dedup via clean display name · collapse repeats', progress: '— / —', status: 'queued' },
      { name: 'Reconciliation', detail: 'Declared vs bank inflow · awaiting entity extraction', progress: '—', status: 'queued' },
      { name: 'Confidence scoring', detail: 'Depends on reconciliation delta', progress: '—', status: 'queued' },
      { name: 'Snapshot generation', detail: 'SHA256 dual hash · immutable · sealed', progress: '—', status: 'queued' },
    ];
    if (analysisState === 'uploading') return [
      { name: 'Document ingestion', detail: `Uploading ${totalDocs} documents…`, progress: `0 / ${totalDocs}`, status: 'active', pct: 20 },
      { name: 'Transaction parsing', detail: 'Layout detection · row parsing · 0 errors', progress: '— / —', status: 'queued' },
      { name: 'Classification', detail: 'Ontology v2.0 · 25 roles · integer arithmetic', progress: '— / —', status: 'queued' },
      { name: 'Entity extraction', detail: 'Dedup via clean display name · collapse repeats', progress: '— / —', status: 'queued' },
      { name: 'Reconciliation', detail: 'Declared vs bank inflow · awaiting entity extraction', progress: '—', status: 'queued' },
      { name: 'Confidence scoring', detail: 'Depends on reconciliation delta', progress: '—', status: 'queued' },
      { name: 'Snapshot generation', detail: 'SHA256 dual hash · immutable · sealed', progress: '—', status: 'queued' },
    ];
    if (analysisState === 'polling') return [
      { name: 'Document ingestion', detail: `${totalDocs} documents · SHA256 · canonicalised`, progress: `${totalDocs} / ${totalDocs}`, status: 'done' },
      { name: 'Transaction parsing', detail: 'Layout detection · row parsing · 0 errors', progress: `${totalTxn} / ${totalTxn}`, status: 'done' },
      { name: 'Classification', detail: 'Ontology v2.0 · 25 roles · integer arithmetic', progress: `${totalTxn} / ${totalTxn}`, status: 'done' },
      { name: 'Entity extraction', detail: 'Dedup via clean display name · collapse repeats', progress: `${doneEntities} / ${totalEntities}`, status: 'active', pct: 67 },
      { name: 'Reconciliation', detail: 'Declared vs bank inflow · awaiting entity extraction', progress: '—', status: 'queued' },
      { name: 'Confidence scoring', detail: 'Depends on reconciliation delta', progress: '—', status: 'queued' },
      { name: 'Snapshot generation', detail: 'SHA256 dual hash · immutable · sealed', progress: '—', status: 'queued' },
    ];
    if (analysisState === 'exporting') return [
      { name: 'Document ingestion', detail: `${totalDocs} documents · SHA256 · canonicalised`, progress: `${totalDocs} / ${totalDocs}`, status: 'done' },
      { name: 'Transaction parsing', detail: 'Layout detection · row parsing · 0 errors', progress: `${totalTxn} / ${totalTxn}`, status: 'done' },
      { name: 'Classification', detail: 'Ontology v2.0 · 25 roles · integer arithmetic', progress: `${totalTxn} / ${totalTxn}`, status: 'done' },
      { name: 'Entity extraction', detail: 'Dedup via clean display name · collapse repeats', progress: `${totalEntities} / ${totalEntities}`, status: 'done' },
      { name: 'Reconciliation', detail: 'Declared vs bank inflow · awaiting entity extraction', progress: run ? `${run.coverage_pct_bp / 100}%` : '—', status: 'done' },
      { name: 'Confidence scoring', detail: 'Depends on reconciliation delta', progress: '—', status: 'active', pct: 80 },
      { name: 'Snapshot generation', detail: 'SHA256 dual hash · immutable · sealed', progress: '—', status: 'queued' },
    ];
    // done or error
    return [
      { name: 'Document ingestion', detail: `${totalDocs} documents · SHA256 · canonicalised`, progress: `${totalDocs} / ${totalDocs}`, status: 'done' },
      { name: 'Transaction parsing', detail: 'Layout detection · row parsing · 0 errors', progress: `${totalTxn} / ${totalTxn}`, status: 'done' },
      { name: 'Classification', detail: 'Ontology v2.0 · 25 roles · integer arithmetic', progress: `${totalTxn} / ${totalTxn}`, status: 'done' },
      { name: 'Entity extraction', detail: 'Dedup via clean display name · collapse repeats', progress: `${totalEntities} / ${totalEntities}`, status: 'done' },
      { name: 'Reconciliation', detail: 'Declared vs bank inflow · awaiting entity extraction', progress: run ? `${(run.coverage_pct_bp / 100).toFixed(1)}%` : '—', status: 'done' },
      { name: 'Confidence scoring', detail: run ? `Tier ${run.tier} · ${(run.final_confidence_bp / 100).toFixed(1)}% confidence` : 'Depends on reconciliation delta', progress: run ? `${(run.final_confidence_bp / 100).toFixed(1)}%` : '—', status: analysisState === 'error' ? 'failed' : 'done' },
      { name: 'Snapshot generation', detail: snapshot ? `SHA256 ${snapshot.sha256_hash.slice(0, 12)}… · sealed` : 'SHA256 dual hash · immutable · sealed', progress: snapshot ? '1 / 1' : '—', status: analysisState === 'error' ? 'queued' : 'done' },
    ];
  })();

  const TABS = ['documents', 'analysis', 'review', 'snapshot'] as const;
  const TAB_LABELS: Record<string, string> = { documents: 'Documents', analysis: 'Analysis', review: 'Parity Review', snapshot: 'Snapshot' };

  const StatusDot = ({ status }: { status: StageStatus }) => {
    const colors: Record<StageStatus, string> = { done: '#4ADE80', active: '#818CF8', queued: '#374151', failed: '#F87171' };
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18, borderRadius: '50%', background: colors[status], flexShrink: 0 }}>
        {status === 'done' && <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 5l2.5 2.5L8 3" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
        {status === 'active' && <span style={{ width: 6, height: 6, background: '#fff', borderRadius: '50%' }} />}
        {status === 'queued' && <span style={{ width: 6, height: 6, background: '#4B5563', borderRadius: '50%' }} />}
        {status === 'failed' && <span style={{ color: '#fff', fontSize: 10, fontWeight: 700 }}>!</span>}
      </span>
    );
  };

  const FileRow = ({
    item,
    accent,
    isUnknownFormat,
    onRequestParser,
    canRemove,
    onRemove,
  }: {
    item: { id: string; fileName: string; status: QueuedStatement['status'] };
    accent: string;
    isUnknownFormat?: boolean;
    onRequestParser?: () => void;
    canRemove?: boolean;
    onRemove?: () => void;
  }) => {
    const [removing, setRemoving] = useState(false);
    const statusLabel = { ready: 'INDEXED', processing: 'PROCESSING', uploading: 'UPLOADING', failed: isUnknownFormat ? 'NO PARSER' : 'FAILED' }[item.status];
    const statusColor = { ready: '#4ADE80', processing: '#818CF8', uploading: '#818CF8', failed: isUnknownFormat ? '#F59E0B' : '#F87171' }[item.status];
    const statusBg = { ready: 'rgba(74,222,128,0.08)', processing: 'rgba(129,140,248,0.12)', uploading: 'rgba(129,140,248,0.12)', failed: isUnknownFormat ? 'rgba(245,158,11,0.1)' : 'rgba(248,113,113,0.12)' }[item.status];

    const handleRemove = async () => {
      if (!onRemove || removing) return;
      setRemoving(true);
      try {
        await deleteDocument(item.id);
        onRemove();
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Delete failed';
        alert(`Could not remove document: ${msg}`);
        setRemoving(false);
      }
    };

    return (
      <div style={{ borderBottom: '1px solid #1A2235' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0' }}>
          <span style={{ width: 20, height: 20, borderRadius: 4, background: item.status === 'ready' ? 'rgba(74,222,128,0.15)' : '#1A2235', border: `1px solid ${item.status === 'ready' ? accent : isUnknownFormat ? '#F59E0B' : '#2D3748'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            {item.status === 'ready' && <svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M2 5.5l2.5 2.5L9 3" stroke={accent} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
            {(item.status === 'processing' || item.status === 'uploading') && <span style={{ width: 8, height: 8, borderRadius: '50%', borderTop: `2px solid ${accent}`, borderRight: `2px solid transparent`, animation: 'spin 0.8s linear infinite', display: 'inline-block' }} />}
            {item.status === 'failed' && <span style={{ fontSize: 10, color: isUnknownFormat ? '#F59E0B' : '#F87171', fontWeight: 700 }}>!</span>}
          </span>
          <span style={{ flex: 1, fontSize: 13, color: '#CBD5E1', fontFamily: "'IBM Plex Mono', monospace", overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.fileName}</span>
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em', color: statusColor, background: statusBg, padding: '2px 7px', borderRadius: 3, flexShrink: 0 }}>{statusLabel}</span>
          {canRemove && onRemove && item.status !== 'uploading' && (
            <button
              onClick={handleRemove}
              disabled={removing}
              title="Remove document"
              style={{ marginLeft: 4, padding: '2px 6px', fontSize: 11, color: removing ? '#4A5568' : '#64748B', background: 'transparent', border: 'none', cursor: removing ? 'not-allowed' : 'pointer', borderRadius: 3, lineHeight: 1, flexShrink: 0 }}
            >
              {removing ? '…' : '✕'}
            </button>
          )}
        </div>
        {/* Inline CTA for unsupported bank format */}
        {item.status === 'failed' && isUnknownFormat && onRequestParser && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 10, paddingLeft: 30 }}>
            <span style={{ fontSize: 11, color: '#64748B' }}>Format not supported —</span>
            <button
              onClick={onRequestParser}
              style={{ fontSize: 11, fontWeight: 600, color: '#F59E0B', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
            >
              Request parser →
            </button>
          </div>
        )}
      </div>
    );
  };

  const DropZone = ({ onFileDrop, label, formats }: { onFileDrop: (f: File) => void; label: string; formats: string }) => {
    const [dragging, setDragging] = useState(false);
    return (
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) onFileDrop(f); }}
        onClick={() => { const el = document.createElement('input'); el.type = 'file'; el.accept = '.pdf,.csv,.xlsx,.docx'; el.onchange = (ev) => { const f = (ev.target as HTMLInputElement).files?.[0]; if (f) onFileDrop(f); }; el.click(); }}
        style={{ border: `1px dashed ${dragging ? '#6366F1' : '#2D3748'}`, borderRadius: 6, padding: '14px 12px', textAlign: 'center', cursor: 'pointer', background: dragging ? 'rgba(99,102,241,0.05)' : 'transparent', transition: 'all 0.15s', marginTop: 8 }}
      >
        <div style={{ fontSize: 12, color: '#4A5568' }}>+ {label}</div>
        <div style={{ fontSize: 10, color: '#2D3748', marginTop: 4, letterSpacing: '0.05em' }}>{formats}</div>
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#080C18', fontFamily: "'IBM Plex Sans', sans-serif", color: '#E2E8F0' }}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }
      `}</style>

      {/* Sidebar */}
      <aside style={{ width: 200, background: '#0A0F1E', borderRight: '1px solid #1A2235', display: 'flex', flexDirection: 'column', padding: '20px 0', position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 50, flexShrink: 0 }}>
        <div style={{ padding: '0 16px 20px', borderBottom: '1px solid #1A2235' }}>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, color: '#6366F1', letterSpacing: '0.08em', fontWeight: 700 }}>P/ PARITY<span style={{ fontSize: 9, verticalAlign: 'super', color: '#4A5568' }}>v2.0</span></div>
          {dealName && <div style={{ fontSize: 10, color: '#4A5568', marginTop: 6, letterSpacing: '0.08em', background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 4, padding: '3px 8px', display: 'inline-flex', gap: 6 }}>{dealName.toUpperCase()}</div>}
        </div>
        <nav style={{ flex: 1, padding: '12px 0' }}>
          {[
            { label: 'Documents', tab: 'documents' as const },
            { label: 'Analysis', tab: 'analysis' as const },
            { label: 'Parity Review', tab: 'review' as const },
            { label: 'Snapshot', tab: 'snapshot' as const },
          ].map((item) => (
            <button
              key={item.tab}
              onClick={() => setActiveTab(item.tab)}
              style={{ display: 'flex', alignItems: 'center', width: '100%', padding: '9px 16px', background: activeTab === item.tab ? 'rgba(99,102,241,0.1)' : 'transparent', borderLeft: activeTab === item.tab ? '2px solid #6366F1' : '2px solid transparent', border: 'none', color: activeTab === item.tab ? '#A5B4FC' : '#4A5568', fontSize: 13, fontFamily: "'IBM Plex Sans', sans-serif", cursor: 'pointer', textAlign: 'left' }}
            >
              {item.label}
            </button>
          ))}
          <div style={{ margin: '12px 0 4px', padding: '0 16px', fontSize: 9, color: '#2D3748', letterSpacing: '0.1em' }}>DEAL TOOLS</div>
          {['Benchmark', 'Monitor', 'Registry'].map((label) => (
            <div key={label} style={{ padding: '9px 16px', color: '#2D3748', fontSize: 13, borderLeft: '2px solid transparent', display: 'flex', alignItems: 'center', gap: 8 }}>
              {label}
              <span style={{ fontSize: 9, background: '#0D1220', color: '#2D3748', padding: '1px 4px', borderRadius: 2 }}>SOON</span>
            </div>
          ))}
          <div style={{ margin: '12px 0 4px', padding: '0 16px', fontSize: 9, color: '#2D3748', letterSpacing: '0.1em' }}>SUPPORT</div>
          <button
            onClick={() => router.push('/parsers/request')}
            style={{ display: 'flex', alignItems: 'center', width: '100%', padding: '9px 16px', background: 'transparent', borderLeft: '2px solid transparent', border: 'none', color: '#4A5568', fontSize: 13, fontFamily: "'IBM Plex Sans', sans-serif", cursor: 'pointer', textAlign: 'left', gap: 6 }}
          >
            <span style={{ fontSize: 14, lineHeight: 1 }}>🔧</span>
            Request Parser
          </button>
        </nav>
        <div style={{ padding: '12px 16px', borderTop: '1px solid #1A2235' }}>
          {dealId && (
            <div style={{ fontSize: 10, color: '#2D3748', fontFamily: "'IBM Plex Mono', monospace", marginBottom: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {dealId.slice(0, 8)}…
            </div>
          )}
          <button onClick={() => { if (supabase) supabase.auth.signOut(); router.push('/login'); }} style={{ width: '100%', padding: '6px 0', background: 'transparent', border: '1px solid #1A2235', borderRadius: 4, color: '#374151', fontSize: 12, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}>
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div style={{ marginLeft: 200, flex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        {/* Top bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 40px', height: 48, borderBottom: '1px solid #1A2235', background: '#0A0F1E', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#374151', fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.08em' }}>
            <span style={{ cursor: 'pointer', color: '#4A5568' }} onClick={() => router.push('/deals/new')}>DEALS</span>
            {dealShortId !== '—' && <><span>·</span><span style={{ color: '#4A5568' }}>{dealShortId}</span></>}
            <span>·</span>
            <span style={{ color: '#CBD5E1' }}>{TAB_LABELS[activeTab].toUpperCase()}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {isProcessing && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 600, color: '#818CF8', fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.1em' }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#818CF8', display: 'inline-block', animation: 'blink 1.2s ease-in-out infinite' }} />
                PROCESSING
              </div>
            )}
            {analysisState === 'done' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 600, color: '#4ADE80', fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.1em' }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#4ADE80', display: 'inline-block' }} />
                COMPLETE
              </div>
            )}
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, padding: '32px 40px 48px', maxWidth: 1100, width: '100%' }}>
          {/* Deal header */}
          <div style={{ marginBottom: 24 }}>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: '#F1F5F9', margin: 0, letterSpacing: '-0.01em' }}>
              {dealName || 'New Deal'}
            </h1>
            {dealId && (
              <div style={{ marginTop: 6, fontSize: 12, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace", display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <span>{dealShortId}</span>
                <span style={{ color: '#1E2A3A' }}>·</span>
                <span>{currency}</span>
                {statementQueue.length > 0 && <><span style={{ color: '#1E2A3A' }}>·</span><span>{statementQueue.length} document{statementQueue.length !== 1 ? 's' : ''}</span></>}
                {rawTransactions.length > 0 && <><span style={{ color: '#1E2A3A' }}>·</span><span>{rawTransactions.length} transactions</span></>}
              </div>
            )}
          </div>

          {/* Tab nav */}
          <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid #1A2235', marginBottom: 28 }}>
            {TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{ padding: '10px 20px', fontSize: 13, fontWeight: 500, color: activeTab === tab ? '#A5B4FC' : '#4A5568', background: 'transparent', border: 'none', borderBottom: activeTab === tab ? '2px solid #6366F1' : '2px solid transparent', cursor: 'pointer', transition: 'all 0.15s', fontFamily: "'IBM Plex Sans', sans-serif", marginBottom: -1 }}
              >
                {TAB_LABELS[tab]}
              </button>
            ))}
          </div>

          {/* ── DOCUMENTS TAB ── */}
          {activeTab === 'documents' && (
            <div>
              {!deal && (
                <div style={{ padding: '48px 0', textAlign: 'center', color: '#374151' }}>
                  <div style={{ fontSize: 13, fontFamily: "'IBM Plex Mono', monospace" }}>No deal loaded — navigate from Deals →</div>
                </div>
              )}
              {deal && (
                <>
                  {/* Two-column: Bank Statements + Audited Accounts */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                    {/* Bank Statements */}
                    <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 20, borderTop: '2px solid #4ADE80' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>BANK STATEMENTS</span>
                        {bankQueue.length > 0 && (
                          <span style={{ fontSize: 11, color: '#4ADE80', fontFamily: "'IBM Plex Mono', monospace" }}>
                            {bankReady} / {bankQueue.length} ready
                          </span>
                        )}
                      </div>
                      {bankQueue.map((item) => (
                        <FileRow
                          key={item.id}
                          item={item}
                          accent="#4ADE80"
                          isUnknownFormat={unknownFormatDocIds.has(item.id)}
                          onRequestParser={() => setUnknownParserDoc({ docId: item.id, fileName: item.fileName, errorMessage: 'Bank format not recognised' })}
                          canRemove={analysisState === 'idle' || item.status === 'failed'}
                          onRemove={() => setStatementQueue((prev) => prev.filter((q) => q.id !== item.id))}
                        />
                      ))}
                      {bankQueue.length < MAX_STATEMENTS && (
                        <DropZone onFileDrop={handleBankDrop} label="Add bank statement" formats="KCB · EQUITY · NCBA · CO-OP · MPESA · PDF" />
                      )}
                    </div>

                    {/* Audited / Management Accounts */}
                    <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 20, borderTop: '2px solid #4ADE80' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>FINANCIAL ACCOUNTS</span>
                        {auditedFinancialsList.length > 0 && (
                          <span style={{ fontSize: 11, color: '#4ADE80', fontFamily: "'IBM Plex Mono', monospace" }}>
                            {auditedFinancialsList.length} FY record{auditedFinancialsList.length > 1 ? 's' : ''}
                          </span>
                        )}
                      </div>

                      {/* Declaration type selector */}
                      {!auditedConfirmForm && (
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontSize: 10, color: '#64748B', marginBottom: 6, letterSpacing: '0.05em' }}>DECLARATION TYPE</div>
                          <div style={{ display: 'flex', gap: 8 }}>
                            {(['audited', 'management'] as const).map((type) => (
                              <button
                                key={type}
                                type="button"
                                onClick={() => setDeclarationType(type)}
                                style={{
                                  flex: 1,
                                  padding: '7px 0',
                                  fontSize: 11,
                                  fontWeight: 600,
                                  borderRadius: 5,
                                  border: declarationType === type ? '1px solid #6366F1' : '1px solid #1E2A3A',
                                  background: declarationType === type ? 'rgba(99,102,241,0.12)' : 'transparent',
                                  color: declarationType === type ? '#A5B4FC' : '#4A5568',
                                  cursor: 'pointer',
                                  letterSpacing: '0.05em',
                                }}
                              >
                                {type === 'audited' ? 'Audited' : 'Management'}
                              </button>
                            ))}
                          </div>
                          {declarationType === 'management' && (
                            <div style={{ marginTop: 8, padding: '8px 10px', background: 'rgba(251,191,36,0.07)', border: '1px solid rgba(251,191,36,0.25)', borderRadius: 5 }}>
                              <div style={{ fontSize: 11, color: '#FCD34D', fontWeight: 600, marginBottom: 2 }}>Management accounts — Parity Review required</div>
                              <div style={{ fontSize: 10, color: '#92400E' }}>Internally prepared statements apply stricter variance thresholds. Snapshot generation is blocked until Parity Review is complete.</div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Existing extracted records */}
                      {auditedFinancialsList.map((af) => (
                        <div key={af.financial_year} style={{ background: '#0A0F1C', border: '1px solid #1E2A3A', borderRadius: 6, padding: '10px 12px', marginBottom: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 12, fontWeight: 600, color: '#E2E8F0', fontFamily: "'IBM Plex Mono', monospace" }}>
                                FY {af.financial_year ?? '—'}
                              </span>
                              {af.declaration_type === 'management' && (
                                <span style={{ fontSize: 9, background: 'rgba(251,191,36,0.15)', color: '#FCD34D', border: '1px solid rgba(251,191,36,0.3)', borderRadius: 3, padding: '1px 5px', letterSpacing: '0.05em' }}>MGMT</span>
                              )}
                            </div>
                            <span style={{ fontSize: 10, color: af.extraction_confidence && af.extraction_confidence >= 70 ? '#4ADE80' : '#F59E0B', fontFamily: "'IBM Plex Mono', monospace" }}>
                              {af.extraction_confidence != null ? `${af.extraction_confidence}% confidence` : 'manual'}
                            </span>
                          </div>
                          <div style={{ marginTop: 6, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px' }}>
                            {af.turnover_cents != null && (
                              <span style={{ fontSize: 11, color: '#94A3B8' }}>Revenue: KES {(af.turnover_cents / 100).toLocaleString()}</span>
                            )}
                            {af.cash_and_equivalents_cents != null && (
                              <span style={{ fontSize: 11, color: '#94A3B8' }}>Cash: KES {(af.cash_and_equivalents_cents / 100).toLocaleString()}</span>
                            )}
                            {af.profit_after_tax_cents != null && (
                              <span style={{ fontSize: 11, color: '#94A3B8' }}>PAT: KES {(af.profit_after_tax_cents / 100).toLocaleString()}</span>
                            )}
                            {af.total_assets_cents != null && (
                              <span style={{ fontSize: 11, color: '#94A3B8' }}>Assets: KES {(af.total_assets_cents / 100).toLocaleString()}</span>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => setAuditedConfirmForm({ ...af })}
                            style={{ marginTop: 8, fontSize: 10, color: '#6366F1', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                          >
                            Edit details →
                          </button>
                        </div>
                      ))}

                      {/* Upload zone */}
                      {!auditedConfirmForm && (
                        auditedUploading ? (
                          <div style={{ padding: '14px 12px', textAlign: 'center', border: '1px dashed #2D3748', borderRadius: 6, marginTop: 8 }}>
                            <span style={{ fontSize: 12, color: '#6366F1' }}>
                              {declarationType === 'management' ? 'Processing management accounts…' : 'Extracting financial data…'}
                            </span>
                          </div>
                        ) : (
                          <DropZone
                            onFileDrop={handleAuditedDrop}
                            label={auditedFinancialsList.length > 0 ? 'Add another year' : (declarationType === 'management' ? 'Add management accounts' : 'Add audited accounts')}
                            formats="PDF · CSV · XLSX · Auto-extracts revenue, cash & FY dates"
                          />
                        )
                      )}

                      {/* Upload error */}
                      {auditedUploadError && !auditedConfirmForm && (
                        <p style={{ fontSize: 11, color: '#F87171', marginTop: 6 }}>{auditedUploadError} — fill in details manually below</p>
                      )}

                      {/* Confirmation / manual fill form */}
                      {auditedConfirmForm && (
                        <div style={{ background: '#0A0F1C', border: '1px solid #6366F1', borderRadius: 8, padding: 16, marginTop: 12 }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                            <div style={{ fontSize: 12, fontWeight: 700, color: '#A5B4FC', letterSpacing: '0.08em' }}>
                              {auditedConfirmForm.extraction_confidence != null
                                ? `CONFIRM EXTRACTED DETAILS — ${auditedConfirmForm.extraction_confidence}% confidence`
                                : 'ENTER FINANCIAL DETAILS'}
                            </div>
                            {auditedConfirmForm.declaration_type === 'management' && (
                              <span style={{ fontSize: 9, background: 'rgba(251,191,36,0.15)', color: '#FCD34D', border: '1px solid rgba(251,191,36,0.3)', borderRadius: 3, padding: '2px 6px', letterSpacing: '0.05em' }}>MANAGEMENT</span>
                            )}
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                            {([
                              { key: 'company_name', label: 'Company name', type: 'text', placeholder: 'e.g. Buildex Ltd' },
                              { key: 'financial_year', label: 'Financial year', type: 'number', placeholder: 'e.g. 2024' },
                              { key: 'financial_year_start', label: 'FY start date', type: 'text', placeholder: 'YYYY-MM-DD' },
                              { key: 'financial_year_end', label: 'FY end date', type: 'text', placeholder: 'YYYY-MM-DD' },
                            ] as const).map(({ key, label, type, placeholder }) => (
                              <div key={key}>
                                <label style={{ fontSize: 10, color: '#64748B', display: 'block', marginBottom: 4 }}>{label}</label>
                                <input
                                  type={type}
                                  value={(auditedConfirmForm[key as keyof AuditedFinancialsRecord] as string | undefined) ?? ''}
                                  onChange={(e) => setAuditedConfirmForm((prev) => prev ? { ...prev, [key]: e.target.value } : prev)}
                                  placeholder={placeholder}
                                  style={{ width: '100%', background: '#131929', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 5, padding: '6px 8px', fontSize: 12, color: '#E2E8F0', outline: 'none', boxSizing: 'border-box' }}
                                />
                              </div>
                            ))}
                          </div>
                          <div style={{ fontSize: 10, color: '#64748B', marginTop: 10, marginBottom: 6 }}>Amounts in KES (whole numbers)</div>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                            {([
                              { key: 'turnover_cents', label: 'Annual revenue (KES)' },
                              { key: 'cash_and_equivalents_cents', label: 'Cash at year-end (KES)' },
                              { key: 'profit_after_tax_cents', label: 'Profit after tax (KES)' },
                              { key: 'total_assets_cents', label: 'Total assets (KES)' },
                              { key: 'total_expenses_cents', label: 'Total expenses (KES)' },
                              { key: 'total_liabilities_cents', label: 'Total liabilities (KES)' },
                            ] as const).map(({ key, label }) => {
                              const rawVal = auditedConfirmForm[key as keyof AuditedFinancialsRecord] as number | null | undefined;
                              const displayVal = rawVal != null ? String(Math.round((rawVal as number) / 100)) : '';
                              return (
                                <div key={key}>
                                  <label style={{ fontSize: 10, color: '#64748B', display: 'block', marginBottom: 4 }}>{label}</label>
                                  <input
                                    type="text"
                                    value={displayVal}
                                    onChange={(e) => {
                                      const kes = parseFloat(e.target.value.replace(/,/g, ''));
                                      setAuditedConfirmForm((prev) => prev ? { ...prev, [key]: isNaN(kes) ? null : Math.round(kes * 100) } : prev);
                                    }}
                                    placeholder="0"
                                    style={{ width: '100%', background: '#131929', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 5, padding: '6px 8px', fontSize: 12, color: '#E2E8F0', outline: 'none', boxSizing: 'border-box' }}
                                  />
                                </div>
                              );
                            })}
                          </div>
                          <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                            <button
                              type="button"
                              disabled={auditedSaving}
                              onClick={async () => {
                                if (!deal || !auditedConfirmForm) return;
                                const fy = Number(auditedConfirmForm.financial_year);
                                if (!fy) { alert('Financial year is required'); return; }
                                setAuditedSaving(true);
                                try {
                                  const { financial_year: _fy, deal_id: _did, extraction_confidence: _ec, id: _id, ...patch } = auditedConfirmForm;
                                  await patchAuditedFinancials(deal.id, fy, patch);
                                  await loadAuditedFinancials(deal.id);
                                  setAuditedConfirmForm(null);
                                  setAuditedUploadError('');
                                } catch (err) {
                                  alert(err instanceof Error ? err.message : 'Save failed');
                                } finally {
                                  setAuditedSaving(false);
                                }
                              }}
                              style={{ flex: 1, padding: '8px 0', background: '#6366F1', color: '#fff', border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: auditedSaving ? 'not-allowed' : 'pointer', opacity: auditedSaving ? 0.6 : 1 }}
                            >
                              {auditedSaving ? 'Saving…' : 'Save financial details'}
                            </button>
                            <button
                              type="button"
                              onClick={() => { setAuditedConfirmForm(null); setAuditedUploadError(''); }}
                              style={{ padding: '8px 14px', background: 'transparent', color: '#64748B', border: '1px solid #1E2A3A', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Application Documents */}
                  <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 20, marginBottom: 24 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>APPLICATION DOCUMENTS</span>
                      <span style={{ fontSize: 11, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace" }}>optional</span>
                    </div>
                    {[
                      { label: 'Business registration certificate', formats: 'PDF · DOCX' },
                      { label: 'KRA PIN certificate', formats: 'PDF' },
                      { label: 'Director ID / Passport', formats: 'PDF · JPG' },
                    ].map((doc) => (
                      <div key={doc.label} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid #1A2235' }}>
                        <span style={{ width: 20, height: 20, borderRadius: 4, background: '#0D1220', border: '1px dashed #2D3748', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                          <span style={{ fontSize: 11, color: '#374151' }}>—</span>
                        </span>
                        <span style={{ flex: 1, fontSize: 13, color: '#4A5568' }}>{doc.label}</span>
                        <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em', color: '#374151', background: '#0D1220', border: '1px solid #1E2A3A', padding: '2px 7px', borderRadius: 3 }}>PENDING</span>
                      </div>
                    ))}
                  </div>

                  {/* CTA */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <button
                      onClick={() => { setActiveTab('analysis'); void runAnalysis(); }}
                      disabled={statementQueue.length === 0 || queueHasPending || isProcessing}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '10px 20px', background: statementQueue.length === 0 || queueHasPending || isProcessing ? '#1A2235' : '#6366F1', color: statementQueue.length === 0 || queueHasPending || isProcessing ? '#374151' : '#fff', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: statementQueue.length === 0 || queueHasPending || isProcessing ? 'not-allowed' : 'pointer', fontFamily: "'IBM Plex Sans', sans-serif", transition: 'background 0.15s' }}
                    >
                      {isProcessing ? 'Processing…' : 'Initialise analysis pipeline'}
                      {!isProcessing && <span style={{ fontSize: 16 }}>→</span>}
                    </button>
                    {statementQueue.length > 0 && (
                      <span style={{ fontSize: 12, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace" }}>
                        {statementQueue.filter(i => i.status === 'ready').length} documents indexed{queueHasPending ? ` · ${statementQueue.filter(i => i.status === 'processing' || i.status === 'uploading').length} pending` : ''}
                      </span>
                    )}
                  </div>
                  {errorMsg && <div style={{ marginTop: 12, fontSize: 12, color: '#F87171', fontFamily: "'IBM Plex Mono', monospace" }}>{errorMsg}</div>}
                </>
              )}
            </div>
          )}

          {/* ── ANALYSIS TAB ── */}
          {activeTab === 'analysis' && (() => {
            const csi = creditScoringInputs as Record<string, unknown> | null;
            const confPct = run ? (run.final_confidence_bp / 100).toFixed(1) : null;
            const tier = run?.tier ?? null;
            const roleBadgeColor: Record<string, string> = {
              supplier: '#6366F1', revenue_operational: '#4ADE80', revenue_non_operational: '#22D3EE',
              payroll: '#F59E0B', needs_review: '#F59E0B', loan_repayment: '#F87171', other: '#374151',
            };
            return (
            <div>
              {analysisState === 'idle' && !run && (
                <div style={{ padding: '48px 0', textAlign: 'center' }}>
                  <div style={{ fontSize: 13, color: '#4A5568', marginBottom: 16 }}>No analysis run yet. Upload documents and initialise the pipeline.</div>
                  <button onClick={() => setActiveTab('documents')} style={{ padding: '9px 18px', background: '#6366F1', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer' }}>← Go to Documents</button>
                </div>
              )}
              {(isProcessing || run) && (
                <>
                  {/* Run meta + confidence badge */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                    <div style={{ fontSize: 12, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace", display: 'flex', gap: 14 }}>
                      {run && <><span>{statementQueue.length} source document{statementQueue.length !== 1 ? 's' : ''}</span><span>·</span><span>{rawTransactions.length} transactions</span></>}
                    </div>
                    {confPct && (
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                        <span style={{ fontSize: 28, fontWeight: 700, color: '#4ADE80', fontFamily: "'IBM Plex Mono', monospace", lineHeight: 1 }}>{confPct}</span>
                        <span style={{ fontSize: 11, color: '#4A5568' }}>% CONFIDENCE</span>
                        {tier && <span style={{ fontSize: 10, fontWeight: 700, color: '#4ADE80', background: 'rgba(74,222,128,0.1)', border: '1px solid rgba(74,222,128,0.3)', padding: '2px 8px', borderRadius: 3, letterSpacing: '0.08em' }}>{tier.toUpperCase()}</span>}
                      </div>
                    )}
                  </div>

                  {/* Pipeline stages */}
                  <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, overflow: 'hidden', marginBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid #1A2235' }}>
                      <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>PIPELINE STAGES</span>
                      <span style={{ fontSize: 11, color: '#2D3748', fontFamily: "'IBM Plex Mono', monospace" }}>Deterministic · No AI in financial pipeline</span>
                    </div>
                    <div style={{ padding: '0 20px' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr 120px 80px', gap: 12, padding: '10px 0', borderBottom: '1px solid #1A2235' }}>
                        {['STAGE', 'DETAIL', 'PROGRESS', 'STATUS'].map((h) => <span key={h} style={{ fontSize: 10, fontWeight: 700, color: '#2D3748', letterSpacing: '0.1em' }}>{h}</span>)}
                      </div>
                      {pipelineStages.map((stage) => (
                        <div key={stage.name} style={{ display: 'grid', gridTemplateColumns: '200px 1fr 120px 80px', gap: 12, padding: '14px 0', borderBottom: '1px solid #1A2235', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <StatusDot status={stage.status} />
                            <span style={{ fontSize: 13, color: stage.status === 'queued' ? '#374151' : '#CBD5E1' }}>{stage.name}</span>
                          </div>
                          <div>
                            <span style={{ fontSize: 12, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace" }}>{stage.detail}</span>
                            {stage.status === 'active' && stage.pct !== undefined && (
                              <div style={{ marginTop: 4, height: 3, background: '#1A2235', borderRadius: 2, overflow: 'hidden', width: 200 }}>
                                <div style={{ height: '100%', width: `${stage.pct}%`, background: '#6366F1', borderRadius: 2, transition: 'width 0.5s' }} />
                              </div>
                            )}
                          </div>
                          <span style={{ fontSize: 12, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace" }}>{stage.progress}</span>
                          <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', color: { done: '#4ADE80', active: '#818CF8', queued: '#374151', failed: '#F87171' }[stage.status] }}>
                            {stage.status === 'done' ? 'DONE' : stage.status === 'active' ? `${stage.pct ?? '…'}%` : stage.status === 'failed' ? 'FAILED' : 'QUEUED'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Rich results — only when done */}
                  {run && analysisState === 'done' && (
                    <>
                      {/* 01 · Credit Scoring Inputs */}
                      <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, overflow: 'hidden', marginBottom: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid #1A2235', borderLeft: '3px solid #4ADE80' }}>
                          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>01 · CREDIT SCORING INPUTS</span>
                          <span style={{ fontSize: 10, color: '#4ADE80', background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.2)', padding: '2px 8px', borderRadius: 3, letterSpacing: '0.06em' }}>Parity Format</span>
                        </div>
                        <div style={{ padding: '0 20px' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px 1fr', gap: 12, padding: '10px 0', borderBottom: '1px solid #1A2235' }}>
                            {['SCORING METRIC', 'VALUE', 'BASIS'].map((h) => <span key={h} style={{ fontSize: 10, fontWeight: 700, color: '#2D3748', letterSpacing: '0.1em' }}>{h}</span>)}
                          </div>
                          {(() => {
                            const fmt = (cents: unknown) => cents != null ? new Intl.NumberFormat('en-KE', { style: 'currency', currency: currency, minimumFractionDigits: 2 }).format(Number(cents) / 100) : '—';
                            const fmtBps = (bps: unknown) => bps != null ? `${(Number(bps) / 100).toFixed(1)}%` : '—';
                            const rows = [
                              { label: 'Average Monthly Inflow', value: csi ? fmt(csi.average_monthly_inflow_cents) : (monthlyCashflow.length > 0 ? fmt(monthlyCashflow.reduce((s: number, m: any) => s + (m.inflow_cents || 0), 0) / monthlyCashflow.length) : '—'), basis: '12-month arithmetic mean', positive: true },
                              { label: 'Median Monthly Inflow', value: csi ? fmt(csi.median_monthly_inflow_cents) : '—', basis: '12-month median', positive: true },
                              { label: 'Average Monthly Outflow', value: csi ? fmt(csi.average_monthly_outflow_cents) : '—', basis: '12-month arithmetic mean', positive: null },
                              { label: 'Average Net Monthly Position', value: csi ? fmt(csi.average_net_monthly_cents) : '—', basis: 'Inflow minus outflow mean', positive: csi ? Number(csi.average_net_monthly_cents) >= 0 : null },
                              { label: 'Peak Net Position', value: csi ? fmt(csi.peak_net_position_cents) : '—', basis: 'Best month', positive: true },
                              { label: 'Trough Net Position', value: csi ? fmt(csi.trough_net_position_cents) : '—', basis: 'Worst month', positive: csi ? Number(csi.trough_net_position_cents) >= 0 : false },
                              { label: 'Revenue Growth', value: csi ? fmtBps(csi.revenue_growth_bps) : '—', basis: 'First vs last month with inflow', positive: csi ? Number(csi.revenue_growth_bps) >= 0 : null },
                              { label: 'Loan Repayment Burden', value: csi ? fmtBps(csi.loan_repayment_burden_bps) : '—', basis: '% of total outflows', positive: null },
                              { label: 'Payroll Stability', value: csi ? (csi.payroll_stability as string) || 'NOT DETECTED' : 'NOT DETECTED', basis: csi?.payroll_stability === 'CONSISTENT' ? 'Consistent monthly pattern' : 'No payroll pattern in statement', positive: csi?.payroll_stability === 'CONSISTENT' ? true : csi?.payroll_stability ? null : null },
                              { label: 'KRA Compliance', value: csi ? (csi.kra_compliance as string) || 'NOT DETECTED' : 'NOT DETECTED', basis: 'No KRA/VAT/PAYE transactions found', positive: csi?.kra_compliance === 'COMPLIANT' ? true : null },
                            ];
                            return rows.map((row) => (
                              <div key={row.label} style={{ display: 'grid', gridTemplateColumns: '1fr 200px 1fr', gap: 12, padding: '11px 0', borderBottom: '1px solid #1A2235', alignItems: 'center' }}>
                                <span style={{ fontSize: 13, color: '#CBD5E1' }}>{row.label}</span>
                                <span style={{ fontSize: 13, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, color: row.positive === true ? '#4ADE80' : row.positive === false ? '#F87171' : '#CBD5E1' }}>{row.value}</span>
                                <span style={{ fontSize: 12, color: '#4A5568' }}>{row.basis}</span>
                              </div>
                            ));
                          })()}
                        </div>
                      </div>

                      {/* MoM Cashflow */}
                      {monthlyCashflow.length > 0 && (
                        <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, overflow: 'hidden', marginBottom: 16 }}>
                          <div style={{ padding: '14px 20px', borderBottom: '1px solid #1A2235', borderLeft: '3px solid #818CF8' }}>
                            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>02 · MONTH-ON-MONTH CASHFLOW</span>
                          </div>
                          <div style={{ padding: '0 20px' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr 1fr 1fr', gap: 12, padding: '10px 0', borderBottom: '1px solid #1A2235' }}>
                              {['MONTH', 'INFLOW', 'OUTFLOW', 'NET'].map((h) => <span key={h} style={{ fontSize: 10, fontWeight: 700, color: '#2D3748', letterSpacing: '0.1em' }}>{h}</span>)}
                            </div>
                            {(monthlyCashflow as Array<Record<string, unknown>>).slice(0, 12).map((m) => {
                              const net = Number(m.net_cents ?? 0);
                              return (
                                <div key={m.month as string} style={{ display: 'grid', gridTemplateColumns: '100px 1fr 1fr 1fr', gap: 12, padding: '10px 0', borderBottom: '1px solid #1A2235', alignItems: 'center' }}>
                                  <span style={{ fontSize: 12, color: '#94A3B8', fontFamily: "'IBM Plex Mono', monospace" }}>{m.month as string}</span>
                                  <span style={{ fontSize: 13, color: '#4ADE80', fontFamily: "'IBM Plex Mono', monospace" }}>{formatCents(Number(m.inflow_cents ?? 0))}</span>
                                  <span style={{ fontSize: 13, color: '#F87171', fontFamily: "'IBM Plex Mono', monospace" }}>{formatCents(Number(m.outflow_cents ?? 0))}</span>
                                  <span style={{ fontSize: 13, fontWeight: 600, color: net >= 0 ? '#4ADE80' : '#F87171', fontFamily: "'IBM Plex Mono', monospace" }}>{formatCents(net)}</span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Entity Breakdown + Needs Review */}
                      <div style={{ display: 'grid', gridTemplateColumns: needsReviewItems.length > 0 ? '1fr 1fr' : '1fr', gap: 16, marginBottom: 16 }}>
                        {/* Entity Breakdown */}
                        {entityBreakdownByCategory.length > 0 && (
                          <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, overflow: 'hidden' }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid #1A2235', borderLeft: '3px solid #6366F1' }}>
                              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>ENTITY BREAKDOWN</span>
                              <span style={{ fontSize: 10, color: '#6366F1', background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)', padding: '2px 7px', borderRadius: 3, letterSpacing: '0.06em' }}>ONTOLOGY v2.0</span>
                            </div>
                            <div style={{ padding: '0 20px' }}>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 120px 50px', gap: 8, padding: '10px 0', borderBottom: '1px solid #1A2235' }}>
                                {['ENTITY', 'ROLE', 'AMOUNT', 'TXNS'].map((h) => <span key={h} style={{ fontSize: 10, fontWeight: 700, color: '#2D3748', letterSpacing: '0.1em' }}>{h}</span>)}
                              </div>
                              {entityBreakdown.slice(0, 10).map((r) => (
                                <div key={r.entityId} style={{ display: 'grid', gridTemplateColumns: '1fr 100px 120px 50px', gap: 8, padding: '10px 0', borderBottom: '1px solid #1A2235', alignItems: 'center' }}>
                                  <span style={{ fontSize: 12, color: r.role === 'needs_review' ? '#F59E0B' : '#CBD5E1', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: r.role === 'needs_review' ? 600 : 400 }}>{r.entityName}</span>
                                  <span style={{ fontSize: 10, fontWeight: 600, color: roleBadgeColor[r.role] ?? '#374151', background: `${roleBadgeColor[r.role] ?? '#374151'}18`, padding: '2px 5px', borderRadius: 3, letterSpacing: '0.04em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.role.replace(/_/g, '_')}</span>
                                  <span style={{ fontSize: 12, color: '#94A3B8', fontFamily: "'IBM Plex Mono', monospace" }}>{formatCents(r.totalAbsCents)}</span>
                                  <span style={{ fontSize: 12, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace" }}>{r.txnCount}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Items Requiring Review */}
                        {needsReviewItems.length > 0 && (
                          <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, overflow: 'hidden' }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid #1A2235', borderLeft: '3px solid #F59E0B' }}>
                              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>ITEMS REQUIRING REVIEW</span>
                              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                                <span style={{ fontSize: 10, fontWeight: 700, color: '#F59E0B', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)', padding: '2px 7px', borderRadius: 3 }}>{needsReviewItems.length} flagged</span>
                                <button onClick={() => setActiveTab('review')} style={{ fontSize: 10, color: '#6366F1', background: 'transparent', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 3, padding: '2px 8px', cursor: 'pointer' }}>Review →</button>
                              </div>
                            </div>
                            <div style={{ padding: '8px 0' }}>
                              {needsReviewItems.slice(0, 5).map((item, idx) => (
                                <div key={(item.row_id as string) ?? idx} style={{ padding: '12px 20px', borderBottom: '1px solid #1A2235' }}>
                                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#F59E0B', display: 'inline-block', flexShrink: 0 }} />
                                        <span style={{ fontSize: 13, fontWeight: 600, color: '#F59E0B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{(item.entity_name || item.description) as string}</span>
                                      </div>
                                      <div style={{ fontSize: 11, color: '#374151', fontFamily: "'IBM Plex Mono', monospace" }}>
                                        needs_review · {item.txn_date as string}
                                        {item.flag_reason != null && <div style={{ color: '#F59E0B', marginTop: 2, fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11 }}>{String(item.flag_reason)}</div>}
                                      </div>
                                    </div>
                                    <span style={{ fontSize: 13, fontWeight: 700, color: '#F87171', fontFamily: "'IBM Plex Mono', monospace", flexShrink: 0 }}>{formatCents(Math.abs(Number(item.signed_amount_cents ?? 0)))}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Concentration: Suppliers / Revenue / Payroll */}
                      {entityBreakdown.length > 0 && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
                          {[
                            { label: 'SUPPLIERS', role: 'supplier', color: '#6366F1' },
                            { label: 'REVENUE', roles: ['revenue_operational', 'revenue_non_operational'], color: '#4ADE80' },
                            { label: 'PAYROLL', role: 'payroll', color: '#F59E0B' },
                          ].map((section) => {
                            const rows = entityBreakdown.filter((r) =>
                              section.role ? r.role === section.role : (section.roles ?? []).includes(r.role)
                            ).slice(0, 5);
                            const total = rows.reduce((s, r) => s + r.totalAbsCents, 0);
                            return (
                              <div key={section.label} style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, overflow: 'hidden' }}>
                                <div style={{ padding: '12px 16px', borderBottom: '1px solid #1A2235', borderLeft: `3px solid ${section.color}` }}>
                                  <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>{section.label}</span>
                                </div>
                                <div style={{ padding: '4px 0' }}>
                                  {rows.length === 0 && <div style={{ padding: '12px 16px', fontSize: 12, color: '#374151' }}>None detected</div>}
                                  {rows.map((r) => (
                                    <div key={r.entityId} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '9px 16px', borderBottom: '1px solid #1A2235' }}>
                                      <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ fontSize: 12, color: '#CBD5E1', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.entityName}</div>
                                        <div style={{ fontSize: 10, color: section.color, fontFamily: "'IBM Plex Mono', monospace", marginTop: 2 }}>{(r.pctBps / 100).toFixed(1)}% of category</div>
                                      </div>
                                      <span style={{ fontSize: 12, color: '#94A3B8', fontFamily: "'IBM Plex Mono', monospace", flexShrink: 0 }}>{formatCents(r.totalAbsCents)}</span>
                                    </div>
                                  ))}
                                  {rows.length > 0 && (
                                    <div style={{ padding: '9px 16px', display: 'flex', justifyContent: 'space-between' }}>
                                      <span style={{ fontSize: 11, color: '#374151' }}>Total</span>
                                      <span style={{ fontSize: 12, fontWeight: 700, color: section.color, fontFamily: "'IBM Plex Mono', monospace" }}>{formatCents(total)}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* Debit / Credit lists */}
                      {rawTransactions.length > 0 && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                          {[
                            { label: 'TOP DEBITS', filter: (t: Record<string,unknown>) => Number(t.signed_amount_cents ?? 0) < 0, color: '#F87171' },
                            { label: 'TOP CREDITS', filter: (t: Record<string,unknown>) => Number(t.signed_amount_cents ?? 0) > 0, color: '#4ADE80' },
                          ].map((section) => {
                            const txns = (rawTransactions as Array<Record<string,unknown>>)
                              .filter(section.filter)
                              .sort((a, b) => Math.abs(Number(b.signed_amount_cents ?? 0)) - Math.abs(Number(a.signed_amount_cents ?? 0)))
                              .slice(0, 8);
                            return (
                              <div key={section.label} style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, overflow: 'hidden' }}>
                                <div style={{ padding: '12px 16px', borderBottom: '1px solid #1A2235', borderLeft: `3px solid ${section.color}` }}>
                                  <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1' }}>{section.label}</span>
                                </div>
                                <div style={{ padding: '4px 0' }}>
                                  {txns.map((t, i) => (
                                    <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', borderBottom: '1px solid #1A2235', gap: 8 }}>
                                      <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ fontSize: 12, color: '#CBD5E1', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{(t.description || t.narrative || '—') as string}</div>
                                        <div style={{ fontSize: 10, color: '#374151', fontFamily: "'IBM Plex Mono', monospace" }}>{t.txn_date as string}</div>
                                      </div>
                                      <span style={{ fontSize: 13, fontWeight: 600, color: section.color, fontFamily: "'IBM Plex Mono', monospace", flexShrink: 0 }}>{formatCents(Math.abs(Number(t.signed_amount_cents ?? 0)))}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </>
                  )}
                </>
              )}
            </div>
            );
          })()}

          {/* ── PARITY REVIEW TAB ── Intelligence Console */}
          {activeTab === 'review' && (() => {
            const classified = entities.length > 0 ? entities.length : (exportData ? entities.length : 0);
            const txnTotal = rawTransactions.length;
            const reconDelta = creditScoringInputs ? (creditScoringInputs.average_net_monthly_cents as number ?? 0) : 0;
            const confidence = snapshot?.confidence_score ?? (exportData?.analysis_run as any)?.confidence_score ?? null;
            const corpusReady = analysisState === 'done';
            const SUGGESTION_CHIPS = [
              'What is the average monthly net cashflow?',
              'Which entities represent the highest concentration risk?',
              'Are there any irregular payroll patterns?',
              'What is the peak debt service coverage ratio?',
            ];
            return (
              <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
                {/* Left: Chat area */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  {/* Header */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                    <span style={{ fontSize: 15, fontWeight: 700, color: '#CBD5E1', letterSpacing: '0.02em' }}>Ask Parity</span>
                    <span style={{
                      fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', padding: '2px 8px', borderRadius: 3,
                      background: corpusReady ? 'rgba(74,222,128,0.12)' : 'rgba(99,102,241,0.12)',
                      color: corpusReady ? '#4ADE80' : '#818CF8',
                      border: `1px solid ${corpusReady ? 'rgba(74,222,128,0.25)' : 'rgba(99,102,241,0.25)'}`,
                    }}>
                      {corpusReady ? 'READY' : 'PENDING'}
                    </span>
                  </div>

                  {/* Corpus description card */}
                  {!corpusReady && (
                    <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: '14px 18px', marginBottom: 16 }}>
                      <div style={{ fontSize: 12, color: '#4A5568', lineHeight: 1.6 }}>
                        Parity Intelligence is available once analysis completes. Run analysis from the Documents tab to activate.
                      </div>
                    </div>
                  )}
                  {corpusReady && chatHistory.length === 0 && (
                    <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: '14px 18px', marginBottom: 16 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#374151', letterSpacing: '0.08em', marginBottom: 6 }}>CORPUS LOADED</div>
                      <div style={{ fontSize: 12, color: '#4A5568', lineHeight: 1.6 }}>
                        {txnTotal > 0 ? `${txnTotal} transactions` : 'Transactions'} across {statementQueue.filter(s => s.status === 'ready').length || 1} statement{statementQueue.filter(s => s.status === 'ready').length !== 1 ? 's' : ''} indexed. Ask any question about this borrower's financial history.
                      </div>
                    </div>
                  )}

                  {/* Chat history */}
                  {chatHistory.length > 0 && (
                    <div style={{ marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {chatHistory.map((msg, i) => (
                        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: msg.role === 'analyst' ? 'flex-end' : 'flex-start' }}>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <span style={{ fontSize: 9, fontWeight: 700, color: msg.role === 'analyst' ? '#6366F1' : '#4ADE80', letterSpacing: '0.1em', fontFamily: "'IBM Plex Mono', monospace" }}>
                              {msg.role === 'analyst' ? 'ANALYST' : 'PARITY'}
                            </span>
                            <span style={{ fontSize: 9, color: '#2D3748', fontFamily: "'IBM Plex Mono', monospace" }}>{msg.time}</span>
                          </div>
                          <div style={{
                            maxWidth: '85%',
                            background: msg.role === 'analyst' ? 'rgba(99,102,241,0.1)' : '#0D1220',
                            border: `1px solid ${msg.role === 'analyst' ? 'rgba(99,102,241,0.2)' : '#1E2A3A'}`,
                            borderRadius: msg.role === 'analyst' ? '8px 8px 2px 8px' : '8px 8px 8px 2px',
                            padding: '10px 14px',
                          }}>
                            <p style={{ fontSize: 13, color: msg.role === 'analyst' ? '#A5B4FC' : '#CBD5E1', lineHeight: 1.6, whiteSpace: 'pre-line', margin: 0 }}>{msg.text}</p>
                          </div>
                        </div>
                      ))}
                      {reviewLoading && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-start' }}>
                          <span style={{ fontSize: 9, fontWeight: 700, color: '#4ADE80', letterSpacing: '0.1em', fontFamily: "'IBM Plex Mono', monospace" }}>PARITY</span>
                          <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: '8px 8px 8px 2px', padding: '10px 14px' }}>
                            <span style={{ fontSize: 13, color: '#374151' }}>Computing…</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Suggestion chips */}
                  {corpusReady && chatHistory.length === 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
                      {SUGGESTION_CHIPS.map((chip) => (
                        <button
                          key={chip}
                          onClick={() => { setReviewQuestion(chip); }}
                          style={{ padding: '5px 12px', background: 'transparent', border: '1px solid #1E2A3A', borderRadius: 20, fontSize: 11, color: '#4A5568', cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif", transition: 'all 0.15s' }}
                          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#6366F1'; (e.currentTarget as HTMLElement).style.color = '#A5B4FC'; }}
                          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#1E2A3A'; (e.currentTarget as HTMLElement).style.color = '#4A5568'; }}
                        >
                          {chip}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Input */}
                  <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 14 }}>
                    <textarea
                      value={reviewQuestion}
                      onChange={(e) => setReviewQuestion(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void handleAsk(); }}
                      placeholder={corpusReady ? "Ask anything about this borrower's financials…" : 'Run analysis first to enable Parity Review…'}
                      disabled={!corpusReady || reviewLoading}
                      rows={2}
                      style={{ width: '100%', background: 'transparent', border: 'none', outline: 'none', padding: 0, fontSize: 13, color: '#CBD5E1', resize: 'none', fontFamily: "'IBM Plex Sans', sans-serif", boxSizing: 'border-box', opacity: !corpusReady ? 0.4 : 1 }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10, gap: 8, alignItems: 'center' }}>
                      <span style={{ fontSize: 10, color: '#2D3748', fontFamily: "'IBM Plex Mono', monospace" }}>⌘↵ to send</span>
                      <button
                        onClick={() => void handleAsk()}
                        disabled={!corpusReady || reviewLoading || !reviewQuestion.trim()}
                        style={{ padding: '7px 16px', background: '#6366F1', color: '#fff', border: 'none', borderRadius: 5, fontSize: 12, fontWeight: 600, cursor: !corpusReady || reviewLoading || !reviewQuestion.trim() ? 'not-allowed' : 'pointer', opacity: !corpusReady || reviewLoading || !reviewQuestion.trim() ? 0.4 : 1 }}
                      >
                        {reviewLoading ? 'Computing…' : 'Ask →'}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Right: Corpus state sidebar */}
                <div style={{ width: 220, flexShrink: 0 }}>
                  <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 16, marginBottom: 12 }}>
                    <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', color: '#374151', marginBottom: 14 }}>CORPUS STATE</div>
                    {[
                      { label: 'Transactions', value: txnTotal > 0 ? String(txnTotal) : '—' },
                      { label: 'Classified', value: classified > 0 ? `${classified} entities` : '—' },
                      { label: 'Entities', value: entities.length > 0 ? String(entities.length) : '—' },
                      { label: 'Needs review', value: needsReviewItems.length > 0 ? String(needsReviewItems.length) : '0' },
                      { label: 'Recon delta', value: reconDelta !== 0 ? `${(reconDelta / 100).toLocaleString('en-KE', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '—' },
                      { label: 'Confidence', value: confidence != null ? `${(Number(confidence) * 100).toFixed(1)}%` : '—' },
                    ].map(({ label, value }) => (
                      <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
                        <span style={{ fontSize: 11, color: '#4A5568' }}>{label}</span>
                        <span style={{ fontSize: 12, color: '#94A3B8', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600 }}>{value}</span>
                      </div>
                    ))}
                  </div>

                  {/* Override queue */}
                  <button
                    onClick={() => setActiveTab('analysis')}
                    style={{ width: '100%', padding: '9px 12px', background: 'transparent', border: '1px solid #1E2A3A', borderRadius: 6, color: '#64748B', fontSize: 12, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif", textAlign: 'left', marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#6366F1'; (e.currentTarget as HTMLElement).style.color = '#A5B4FC'; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#1E2A3A'; (e.currentTarget as HTMLElement).style.color = '#64748B'; }}
                  >
                    <span>Override queue</span>
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: needsReviewItems.length > 0 ? '#F59E0B' : '#374151' }}>({needsReviewItems.length}) →</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('snapshot')}
                    style={{ width: '100%', padding: '9px 12px', background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 6, color: '#A5B4FC', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(99,102,241,0.18)'; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(99,102,241,0.1)'; }}
                  >
                    Export snapshot
                  </button>
                </div>
              </div>
            );
          })()}

          {/* ── SNAPSHOT TAB ── */}
          {activeTab === 'snapshot' && (
            <div style={{ maxWidth: 720 }}>
              {!run ? (
                <div style={{ padding: '48px 0', textAlign: 'center', color: '#374151', fontSize: 13 }}>
                  Run analysis first to generate a snapshot.
                </div>
              ) : (
                <>
                  <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 20, marginBottom: 16 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1', marginBottom: 14 }}>EXPORT SNAPSHOT</div>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
                      <button onClick={handleReExport} disabled={analysisState === 'exporting'}
                        style={{ padding: '9px 18px', background: '#6366F1', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: analysisState === 'exporting' ? 'not-allowed' : 'pointer', opacity: analysisState === 'exporting' ? 0.6 : 1 }}>
                        {analysisState === 'exporting' ? 'Generating PDF…' : 'Save & Export PDF'}
                      </button>
                      <button onClick={handleDownloadCSV}
                        style={{ padding: '9px 18px', background: 'transparent', color: '#94A3B8', border: '1px solid #1E2A3A', borderRadius: 6, fontSize: 13, cursor: 'pointer' }}>
                        Download CSV
                      </button>
                    </div>
                    {exportSuccess && <div style={{ fontSize: 12, color: '#4ADE80', marginBottom: 10 }}>{exportSuccess}</div>}
                    {exportError && <div style={{ fontSize: 12, color: '#F87171', marginBottom: 10 }}>{exportError}</div>}
                    {lastExportedAt && <div style={{ fontSize: 11, color: '#374151', fontFamily: "'IBM Plex Mono', monospace" }}>Last exported {lastExportedAt.toLocaleTimeString()}</div>}
                  </div>

                  {snapshot && (
                    <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 20 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1', marginBottom: 14 }}>SNAPSHOT HASHES</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {[
                          { label: 'snapshot_id', value: snapshot.id },
                          { label: 'sha256_hash', value: snapshot.sha256_hash },
                          { label: 'financial_state_hash', value: snapshot.financial_state_hash },
                        ].map(({ label, value }) => (
                          <div key={label}>
                            <div style={{ fontSize: 10, color: '#374151', marginBottom: 3, letterSpacing: '0.08em' }}>{label}</div>
                            <div style={{ fontSize: 12, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace", wordBreak: 'break-all' }}>{value}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

        </div>
      </div>

      {/* ── Unknown Parser Modal ── */}
      {unknownParserDoc && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(8,12,24,0.85)', backdropFilter: 'blur(4px)' }}>
          <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 10, width: 480, maxWidth: '90vw', padding: 28, boxShadow: '0 24px 64px rgba(0,0,0,0.6)' }}>
            {!parserRequestSubmitted ? (
              <>
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#F59E0B', display: 'inline-block' }} />
                      <span style={{ fontSize: 10, fontWeight: 700, color: '#F59E0B', letterSpacing: '0.1em', fontFamily: "'IBM Plex Mono', monospace" }}>UNKNOWN FORMAT</span>
                    </div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: '#F1F5F9', margin: 0 }}>Parser not found for this bank</h3>
                    <p style={{ fontSize: 12, color: '#4A5568', marginTop: 6, lineHeight: 1.5 }}>
                      <span style={{ color: '#64748B', fontFamily: "'IBM Plex Mono', monospace" }}>{unknownParserDoc.fileName}</span> uses a format we don't currently support. Request a parser and we'll add it to the pipeline.
                    </p>
                  </div>
                  <button
                    onClick={() => { setUnknownParserDoc(null); setParserRequestSubmitted(false); setParserRequestForm({ bankName: '', country: 'Kenya', accountType: 'Business Current', notes: '' }); }}
                    style={{ background: 'transparent', border: 'none', color: '#374151', fontSize: 18, cursor: 'pointer', padding: '0 0 0 12px', lineHeight: 1, flexShrink: 0 }}
                  >×</button>
                </div>

                {/* Form */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 11, color: '#64748B', marginBottom: 5, letterSpacing: '0.06em' }}>BANK NAME *</label>
                    <input
                      type="text"
                      value={parserRequestForm.bankName}
                      onChange={(e) => setParserRequestForm((p) => ({ ...p, bankName: e.target.value }))}
                      placeholder="e.g. Stanbic Bank, Absa, DTB"
                      autoFocus
                      style={{ width: '100%', background: '#080C18', border: '1px solid #1E2A3A', borderRadius: 6, padding: '8px 12px', color: '#F1F5F9', fontSize: 13, outline: 'none', boxSizing: 'border-box', fontFamily: "'IBM Plex Sans', sans-serif" }}
                    />
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, color: '#64748B', marginBottom: 5, letterSpacing: '0.06em' }}>COUNTRY</label>
                      <select
                        value={parserRequestForm.country}
                        onChange={(e) => setParserRequestForm((p) => ({ ...p, country: e.target.value }))}
                        style={{ width: '100%', background: '#080C18', border: '1px solid #1E2A3A', borderRadius: 6, padding: '8px 12px', color: '#CBD5E1', fontSize: 13, outline: 'none', boxSizing: 'border-box' }}
                      >
                        {['Kenya', 'Nigeria', 'Uganda', 'Tanzania', 'Ghana', 'South Africa', 'Rwanda', 'Ethiopia', 'Other'].map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 11, color: '#64748B', marginBottom: 5, letterSpacing: '0.06em' }}>ACCOUNT TYPE</label>
                      <select
                        value={parserRequestForm.accountType}
                        onChange={(e) => setParserRequestForm((p) => ({ ...p, accountType: e.target.value }))}
                        style={{ width: '100%', background: '#080C18', border: '1px solid #1E2A3A', borderRadius: 6, padding: '8px 12px', color: '#CBD5E1', fontSize: 13, outline: 'none', boxSizing: 'border-box' }}
                      >
                        {['Business Current', 'Business Savings', 'Personal Current', 'Personal Savings', 'Mobile Money', 'Other'].map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: 11, color: '#64748B', marginBottom: 5, letterSpacing: '0.06em' }}>NOTES <span style={{ color: '#2D3748' }}>optional</span></label>
                    <textarea
                      value={parserRequestForm.notes}
                      onChange={(e) => setParserRequestForm((p) => ({ ...p, notes: e.target.value }))}
                      placeholder="Any additional info about the format — e.g. PDF vs CSV, layout description…"
                      rows={2}
                      style={{ width: '100%', background: '#080C18', border: '1px solid #1E2A3A', borderRadius: 6, padding: '8px 12px', color: '#CBD5E1', fontSize: 12, outline: 'none', resize: 'none', boxSizing: 'border-box', fontFamily: "'IBM Plex Sans', sans-serif" }}
                    />
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
                  <button
                    onClick={handleParserRequestSubmit}
                    disabled={!parserRequestForm.bankName.trim() || parserRequestSubmitting}
                    style={{ flex: 1, padding: '10px 0', background: !parserRequestForm.bankName.trim() || parserRequestSubmitting ? '#1A2235' : '#6366F1', color: !parserRequestForm.bankName.trim() || parserRequestSubmitting ? '#374151' : '#fff', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: !parserRequestForm.bankName.trim() || parserRequestSubmitting ? 'not-allowed' : 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
                  >
                    {parserRequestSubmitting ? 'Submitting…' : 'Request parser →'}
                  </button>
                  <button
                    onClick={() => { setUnknownParserDoc(null); setParserRequestSubmitted(false); setParserRequestForm({ bankName: '', country: 'Kenya', accountType: 'Business Current', notes: '' }); }}
                    style={{ padding: '10px 16px', background: 'transparent', color: '#4A5568', border: '1px solid #1E2A3A', borderRadius: 6, fontSize: 13, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
                  >
                    Dismiss
                  </button>
                </div>
              </>
            ) : (
              /* Confirmation */
              <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M4 10l4.5 4.5L16 6" stroke="#A5B4FC" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: '#F1F5F9', margin: '0 0 8px' }}>Parser request submitted</h3>
                <p style={{ fontSize: 13, color: '#4A5568', margin: '0 0 20px', lineHeight: 1.5 }}>
                  We've logged <strong style={{ color: '#6366F1' }}>{parserRequestForm.bankName}</strong> ({parserRequestForm.country}) for the engineering queue. You'll be able to re-upload once the parser is live.
                </p>
                <button
                  onClick={() => { setUnknownParserDoc(null); setParserRequestSubmitted(false); setParserRequestForm({ bankName: '', country: 'Kenya', accountType: 'Business Current', notes: '' }); }}
                  style={{ padding: '9px 20px', background: '#6366F1', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
                >
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  );
}

export default function V1DealPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', background: '#080C18', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace", fontSize: 12 }}>LOADING…</div>}>
      <V1DealPageInner />
    </Suspense>
  );
}
