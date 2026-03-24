'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useDropzone } from 'react-dropzone';
import { supabase } from '@/lib/supabase';
import {
  createDeal,
  uploadDocument,
  getDocumentStatus,
  exportSnapshot,
  getDocumentTransactions,
  addOverride,
  listOverrides,
  listDocuments,
  askParity,
} from '@/lib/v1-api';
import { BatchUpload } from '@/components/BatchUpload';
import type {
  Deal,
  AnalysisRun,
  Snapshot,
  Entity,
  TxnEntityMapping,
  ExportResponse,
} from '@/lib/v1-api';
// generateParityPdf is loaded dynamically at click time so Next.js never
// evaluates jsPDF's Node.js build during server compilation.
type GeneratePdfFn = typeof import('@/lib/generate-parity-pdf').generateParityPdf;

const CURRENCIES = ['USD', 'EUR', 'GBP', 'KES', 'NGN'];

type AnalysisState = 'idle' | 'uploading' | 'polling' | 'exporting' | 'done' | 'error';

interface EntityBreakdownRow {
  entityId: string;
  entityName: string;
  role: string;
  totalAbsCents: number;
  pctBps: number; // basis points, display as pctBps/100 + '%'
  txnCount: number;
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

export default function V1DealPage() {
  const router = useRouter();
  useEffect(() => {
    if (!supabase) { router.replace('/login'); return; }
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) router.replace('/login');
    });
  }, [router]);

  const [file, setFile] = useState<File | null>(null);
  const [currency, setCurrency] = useState('USD');
  const [dealName, setDealName] = useState('');
  const [accrualRevenueCents, setAccrualRevenueCents] = useState('');
  const [accrualPeriodStart, setAccrualPeriodStart] = useState('');
  const [accrualPeriodEnd, setAccrualPeriodEnd] = useState('');
  const [deal, setDeal] = useState<Deal | null>(null);
  const [batchesUsed, setBatchesUsed] = useState(0);
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

  const refreshBatchUploadCount = useCallback(async () => {
    if (!deal) return;
    try {
      const { documents } = await listDocuments(deal.id);
      const nums = new Set<number>();
      for (const d of documents) {
        const bn = d.batch_number;
        if (bn != null && typeof bn === 'number') nums.add(bn);
      }
      setBatchesUsed(nums.size);
    } catch {
      setBatchesUsed(0);
    }
  }, [deal]);

  useEffect(() => {
    void refreshBatchUploadCount();
  }, [deal?.id, refreshBatchUploadCount]);

  const runAnalysis = async () => {
    if (!file) {
      setErrorMsg('Please select a file');
      return;
    }
    setErrorMsg('');
    setAnalysisState('uploading');
    try {
      const accrual =
        accrualRevenueCents && accrualPeriodStart && accrualPeriodEnd
          ? {
              accrual_revenue_cents: parseInt(accrualRevenueCents, 10) || 0,
              accrual_period_start: accrualPeriodStart,
              accrual_period_end: accrualPeriodEnd,
            }
          : undefined;

      const { deal: d } = await createDeal(currency, dealName || undefined, accrual);
      setDeal(d);

      const { ingestion } = await uploadDocument(d.id, file);
      setDocumentId(ingestion.document_id);

      setAnalysisState('polling');
      const POLL_INTERVAL_MS = 2000;
      const MAX_POLL_ATTEMPTS = 60; // ~2 min max, then timeout
      let status = await getDocumentStatus(ingestion.document_id);
      let pollCount = 0;
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
        pollCount += 1;
        if (pollCount >= MAX_POLL_ATTEMPTS) {
          setErrorMsg('Document processing timed out. The service may be overloaded — try again later.');
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

      setAnalysisState('exporting');
      const data = await exportSnapshot(d.id);
      setExportData(data);
      setLastExportedAt(new Date());
      setOverridesList([]);
      const docs = await listDocuments(d.id);
      if (docs.documents.length > 0) {
        const txRes = await getDocumentTransactions(docs.documents[0].id);
        setRawTransactions(txRes.transactions as Array<Record<string, unknown>>);
      }
      setAnalysisState('done');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Analysis failed');
      setAnalysisState('error');
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
    setReviewLoading(true);
    setReviewAnswer('');
    try {
      const { answer } = await askParity(deal.id, reviewQuestion.trim());
      setReviewAnswer(answer);
    } catch (e) {
      setReviewAnswer(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setReviewLoading(false);
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

  const formatCents = (c: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 2,
    }).format(c / 100);

  return (
    <div className="min-h-screen bg-base-950 text-gray-200 p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">Deal Analysis (v1)</h1>

      {/* Step 1: Upload + Accrual */}
      <section className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Upload & Accrual</h2>
        <p className="text-sm text-gray-400 mb-3">
          Upload a bank-export CSV or XLSX (must include <code className="text-gray-300">date</code>,{' '}
          <code className="text-gray-300">description</code>, <code className="text-gray-300">amount</code> columns).
          {deal && (
            <>
              {' '}
              <span className="text-gray-500">
                This zone is <strong className="text-gray-400">one file at a time</strong> for the initial
                analysis. To merge <strong className="text-gray-400">2–3 PDFs</strong> at once, use{' '}
                <strong className="text-gray-400">Batch upload</strong> below.
              </span>
            </>
          )}
        </p>
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer mb-4 ${
            isDragActive ? 'border-blue-500 bg-blue-500/10' : 'border-gray-600 hover:border-gray-500'
          }`}
        >
          <input {...getInputProps()} />
          {file ? file.name : 'Drop one CSV or XLSX here, or click to select'}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Currency</label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Deal name</label>
            <input
              type="text"
              value={dealName}
              onChange={(e) => setDealName(e.target.value)}
              placeholder="Optional"
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Accrual revenue (cents)</label>
            <input
              type="number"
              value={accrualRevenueCents}
              onChange={(e) => setAccrualRevenueCents(e.target.value)}
              placeholder="e.g. 100000"
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Accrual period start</label>
            <input
              type="date"
              value={accrualPeriodStart}
              onChange={(e) => setAccrualPeriodStart(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Accrual period end</label>
            <input
              type="date"
              value={accrualPeriodEnd}
              onChange={(e) => setAccrualPeriodEnd(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2"
            />
          </div>
        </div>
        <button
          onClick={runAnalysis}
          disabled={analysisState === 'uploading' || analysisState === 'polling' || analysisState === 'exporting'}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded"
        >
          {analysisState === 'uploading' && 'Creating deal...'}
          {analysisState === 'polling' && 'Processing...'}
          {analysisState === 'exporting' && 'Exporting...'}
          {(analysisState === 'idle' || analysisState === 'done' || analysisState === 'error') &&
            'Analyze'}
        </button>
        {errorMsg && <p className="mt-2 text-red-400 text-sm">{errorMsg}</p>}

        {deal && (
          <div className="mt-6 pt-6 border-t border-gray-700">
            <BatchUpload
              dealId={deal.id}
              batchesUsed={deal.batch_upload_count ?? batchesUsed}
              onUploadComplete={refreshBatchUploadCount}
            />
          </div>
        )}
      </section>

      {run && snapshot && (
        <>
          {/* 1. Deal Summary */}
          <section className="bg-gray-800 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Deal Summary</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <span className="text-gray-400 text-sm">Total transactions</span>
                <p className="font-mono">{rawTransactions.length > 0 ? rawTransactions.length : '—'}</p>
              </div>
              <div>
                <span className="text-gray-400 text-sm">Coverage %</span>
                <p className="font-mono">{(run.coverage_pct_bp / 100).toFixed(2)}%</p>
              </div>
              <div>
                <span className="text-gray-400 text-sm">Reconciliation</span>
                <p className="font-mono">{run.reconciliation_status}</p>
              </div>
              <div>
                <span className="text-gray-400 text-sm">Confidence %</span>
                <p className="font-mono">{(run.final_confidence_bp / 100).toFixed(2)}%</p>
              </div>
              <div>
                <span className="text-gray-400 text-sm">Tier</span>
                <p className="font-mono">{run.tier}</p>
              </div>
            </div>
          </section>

          {/* 2. Reconciliation Block */}
          <section className="bg-gray-800 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Reconciliation</h2>
            <div className="space-y-2">
              <p>
                Accrual revenue: {deal?.accrual_revenue_cents != null ? formatCents(deal.accrual_revenue_cents) : '—'}
              </p>
              <p>Bank operational inflow: {formatCents(run.bank_operational_inflow_cents ?? 0)}</p>
              {deal?.accrual_revenue_cents != null && deal.accrual_revenue_cents > 0 && (
                <>
                  <p>
                    % difference:{' '}
                    {(
                      Math.abs(
                        (deal.accrual_revenue_cents - (run.bank_operational_inflow_cents ?? 0)) /
                          deal.accrual_revenue_cents
                      ) * 100
                    ).toFixed(2)}
                    %
                  </p>
                  {run.reconciliation_status === 'FAILED_OVERLAP' && (
                    <p className="text-amber-400">
                      Overlap between accrual period and transaction dates is below 60%.
                    </p>
                  )}
                  {run.reconciliation_status === 'NOT_RUN' && (
                    <p className="text-amber-400">
                      Reconciliation not run (missing accrual or insufficient overlap).
                    </p>
                  )}
                </>
              )}
            </div>
          </section>

          {/* 3. Entity Breakdown - need transactions */}
          {entityBreakdownByCategory.length > 0 && (
            <section className="bg-gray-800 rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Entity Breakdown</h2>
              <div className="overflow-x-auto space-y-6">
                {entityBreakdownByCategory.map(({ role, rows, totalCents }) => (
                  <div key={role}>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left border-b border-gray-700">
                          <th className="py-2">Entity</th>
                          <th className="py-2">Role</th>
                          <th className="py-2">Amount ({currency})</th>
                          <th className="py-2">%</th>
                          <th className="py-2">Count</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((r) => (
                          <tr key={r.entityId} className="border-b border-gray-700/50">
                            <td className="py-2">{r.entityName}</td>
                            <td className="py-2 capitalize">{r.role.replace(/_/g, ' ')}</td>
                            <td className="py-2 font-mono">{formatCents(r.totalAbsCents)}</td>
                            <td className="py-2">{(r.pctBps / 100).toFixed(1)}%</td>
                            <td className="py-2">{r.txnCount}</td>
                          </tr>
                        ))}
                        <tr className="border-t-2 border-gray-600 font-medium">
                          <td className="py-2" colSpan={2}>Total {role.replace(/_/g, ' ')}</td>
                          <td className="py-2 font-mono">{formatCents(totalCents)}</td>
                          <td className="py-2">100.0%</td>
                          <td className="py-2">{rows.reduce((s, r) => s + r.txnCount, 0)}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* 4. Concentration */}
          {entityBreakdown.length > 0 && (
            <section className="bg-gray-800 rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Concentration</h2>
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm text-gray-400 mb-2">Top 5 suppliers by expense %</h3>
                  <ul className="list-disc list-inside">
                    {topSuppliers.map((r) => (
                      <li key={r.entityId}>
                        {r.entityName}: {(r.pctBps / 100).toFixed(1)}%
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 className="text-sm text-gray-400 mb-2">Top 5 revenue entities</h3>
                  <ul className="list-disc list-inside">
                    {topRevenue.map((r) => (
                      <li key={r.entityId}>
                        {r.entityName}: {formatCents(r.totalAbsCents)}
                      </li>
                    ))}
                  </ul>
                </div>
                <p>
                  Payroll % of total outflow:{' '}
                  {totalOutflow > 0 ? ((payrollTotal / totalOutflow) * 100).toFixed(1) : 0}%
                </p>
                <p>Largest revenue entity %: {(largestRevenuePct).toFixed(1)}%</p>
              </div>
            </section>
          )}

          {/* 5. Override Panel */}
          <section className="bg-gray-800 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Override Classification</h2>
            <div className="flex flex-wrap gap-4 items-end">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Entity</label>
                <select
                  value={overrideEntityId}
                  onChange={(e) => setOverrideEntityId(e.target.value)}
                  className="bg-gray-900 border border-gray-700 rounded px-3 py-2 min-w-[180px]"
                >
                  <option value="">Select...</option>
                  {entities.map((e) => (
                    <option key={e.entity_id} value={e.entity_id}>
                      {e.display_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">New role</label>
                <select
                  value={overrideRole}
                  onChange={(e) => setOverrideRole(e.target.value)}
                  className="bg-gray-900 border border-gray-700 rounded px-3 py-2"
                >
                  {['supplier', 'revenue_operational', 'revenue_non_operational', 'payroll', 'other'].map(
                    (r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    )
                  )}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Note (optional)</label>
                <input
                  type="text"
                  value={overrideNote}
                  onChange={(e) => setOverrideNote(e.target.value)}
                  placeholder="Optional"
                  className="bg-gray-900 border border-gray-700 rounded px-3 py-2 min-w-[120px]"
                />
              </div>
              <button
                onClick={handleAddOverride}
                disabled={!overrideEntityId || overrideSaving}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded"
              >
                {overrideSaving ? 'Saving...' : 'Save override'}
              </button>
            </div>
            {overrideSuccess && (
              <p className="mt-3 text-sm text-green-400">{overrideSuccess}</p>
            )}
            {overrideError && (
              <p className="mt-3 text-sm text-red-400">{overrideError}</p>
            )}
            {overridesList.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm text-gray-400 mb-2">Applied overrides this session</h3>
                <ul className="space-y-1">
                  {overridesList.map((ov, i) => {
                    const ent = entities.find((e) => e.entity_id === ov.entity_id);
                    return (
                      <li key={(ov.id as string) ?? i} className="text-sm font-mono bg-gray-900 rounded px-3 py-1">
                        <span className="text-gray-300">{ent?.display_name ?? (ov.entity_id as string)}</span>
                        <span className="text-gray-500 mx-2">→</span>
                        <span className="text-blue-300">{ov.new_value as string}</span>
                        {typeof ov.reason === 'string' && ov.reason && (
                          <span className="text-gray-500 ml-2 italic">({ov.reason})</span>
                        )}
                        <span className="text-gray-600 ml-2">
                          weight: {ov.weight as number}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </section>

          {/* 6. Save & Export Snapshot */}
          <section className="bg-gray-800 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Save &amp; Export Snapshot</h2>
            <div className="flex items-center gap-4 mb-4">
              <button
                onClick={handleReExport}
                disabled={analysisState === 'exporting'}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded"
              >
                {analysisState === 'exporting' ? 'Saving...' : 'Save & Export Snapshot'}
              </button>
              {lastExportedAt && (
                <span className="text-xs text-gray-400">
                  Last exported: {lastExportedAt.toLocaleTimeString()}
                </span>
              )}
            </div>
            {exportSuccess && (
              <p className="mb-3 text-sm text-green-400">{exportSuccess}</p>
            )}
            {exportError && (
              <p className="mb-3 text-sm text-red-400">{exportError}</p>
            )}
            <div className="font-mono text-sm space-y-1 text-gray-300">
              <p><span className="text-gray-500">snapshot_id:</span> {snapshot.id}</p>
              <p><span className="text-gray-500">sha256_hash:</span> {snapshot.sha256_hash}</p>
              <p><span className="text-gray-500">financial_state_hash:</span> {snapshot.financial_state_hash}</p>
            </div>
          </section>

          {/* 7. Parity Review */}
          <section className="bg-gray-800 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-1">Parity Review</h2>
            <p className="text-xs text-gray-400 mb-4">
              Ask a question about this deal. Answers are computed deterministically from the latest snapshot — no hallucination.
            </p>
            <textarea
              value={reviewQuestion}
              onChange={(e) => setReviewQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleAsk();
              }}
              placeholder="e.g. What percentage of revenue is payroll?"
              rows={2}
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm resize-none mb-3 focus:outline-none focus:border-gray-500"
            />
            <button
              onClick={handleAsk}
              disabled={reviewLoading || !reviewQuestion.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded text-sm font-medium"
            >
              {reviewLoading ? 'Thinking...' : 'Parity Review'}
            </button>
            {reviewAnswer && (
              <div className="mt-4 bg-gray-900 border border-gray-700 rounded p-4">
                <p className="text-sm text-gray-200 whitespace-pre-line">{reviewAnswer}</p>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
