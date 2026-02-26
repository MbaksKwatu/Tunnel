'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  createDeal,
  uploadDocument,
  getDocumentStatus,
  exportSnapshot,
  getDocumentTransactions,
  addOverride,
  listOverrides,
  listDocuments,
} from '@/lib/v1-api';
import type {
  Deal,
  AnalysisRun,
  Snapshot,
  Entity,
  TxnEntityMapping,
  ExportResponse,
} from '@/lib/v1-api';

const CURRENCIES = ['USD', 'EUR', 'GBP', 'KES', 'NGN'];

type AnalysisState = 'idle' | 'uploading' | 'polling' | 'exporting' | 'done' | 'error';

interface EntityBreakdownRow {
  entityId: string;
  entityName: string;
  role: string;
  totalAbsCents: number;
  pctOfTotal: number;
  txnCount: number;
}

export default function V1DealPage() {
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
  const [rawTransactions, setRawTransactions] = useState<Array<Record<string, unknown>>>([]);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length) setFile(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
    maxFiles: 1,
  });

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
      let status = await getDocumentStatus(ingestion.document_id);
      while (status.status !== 'completed') {
        await new Promise((r) => setTimeout(r, 500));
        status = await getDocumentStatus(ingestion.document_id);
      }

      setAnalysisState('exporting');
      const data = await exportSnapshot(d.id);
      setExportData(data);
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
    try {
      await addOverride(deal.id, overrideEntityId, overrideRole, overrideNote || undefined);
      const data = await exportSnapshot(deal.id);
      setExportData(data);
      setOverrideEntityId('');
      setOverrideNote('');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Override failed');
    } finally {
      setOverrideSaving(false);
    }
  };

  const handleReExport = async () => {
    if (!deal) return;
    setAnalysisState('exporting');
    try {
      const data = await exportSnapshot(deal.id);
      setExportData(data);
      setAnalysisState('done');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Export failed');
    }
  };

  const run = exportData?.analysis_run;
  const snapshot = exportData?.snapshot;
  const entities = exportData?.entities ?? [];
  const txnMap = exportData?.txn_entity_map ?? [];

  const entityBreakdown: EntityBreakdownRow[] = (() => {
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
    const total = Object.values(byEntity).reduce((s, v) => s + v.totalCents, 0);
    return Object.entries(byEntity)
      .map(([entityId, v]) => ({
        entityId,
        entityName: v.name,
        role: v.role,
        totalAbsCents: v.totalCents,
        pctOfTotal: total > 0 ? (v.totalCents / total) * 100 : 0,
        txnCount: v.count,
      }))
      .sort((a, b) => b.totalAbsCents - a.totalAbsCents);
  })();

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
          .reduce((max, r) => Math.max(max, r.pctOfTotal), 0)
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
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer mb-4 ${
            isDragActive ? 'border-blue-500 bg-blue-500/10' : 'border-gray-600 hover:border-gray-500'
          }`}
        >
          <input {...getInputProps()} />
          {file ? file.name : 'Drop CSV or XLSX here, or click to select'}
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
                      (Math.abs(
                        (deal.accrual_revenue_cents - (run.bank_operational_inflow_cents ?? 0)) /
                          deal.accrual_revenue_cents
                      ) *
                        100
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
          {entityBreakdown.length > 0 && (
            <section className="bg-gray-800 rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Entity Breakdown</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left border-b border-gray-700">
                      <th className="py-2">Entity</th>
                      <th className="py-2">Role</th>
                      <th className="py-2">Total</th>
                      <th className="py-2">% of total</th>
                      <th className="py-2">Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entityBreakdown.map((r) => (
                      <tr key={r.entityId} className="border-b border-gray-700/50">
                        <td className="py-2">{r.entityName}</td>
                        <td className="py-2">{r.role}</td>
                        <td className="py-2 font-mono">{formatCents(r.totalAbsCents)}</td>
                        <td className="py-2">{r.pctOfTotal.toFixed(1)}%</td>
                        <td className="py-2">{r.txnCount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
                        {r.entityName}: {r.pctOfTotal.toFixed(1)}%
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
                <p>Largest revenue entity %: {largestRevenuePct.toFixed(1)}%</p>
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
          </section>

          {/* 6. Export Snapshot */}
          <section className="bg-gray-800 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Export Snapshot</h2>
            <button
              onClick={handleReExport}
              disabled={analysisState === 'exporting'}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded mb-4"
            >
              Export Snapshot
            </button>
            <div className="font-mono text-sm space-y-1">
              <p>snapshot_id: {snapshot.id}</p>
              <p>sha256_hash: {snapshot.sha256_hash}</p>
              <p>financial_state_hash: {snapshot.financial_state_hash}</p>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
