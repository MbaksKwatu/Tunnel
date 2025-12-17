'use client';

import { useMemo } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  Cell,
} from 'recharts';
import { ExtractedRow } from '@/lib/supabase';
import { Info, MessageSquare } from 'lucide-react';

type Severity = 'high' | 'medium' | 'low';

interface Anomaly {
  anomaly_type: string;
  severity: Severity;
}

interface InsightsDashboardProps {
  rows: ExtractedRow[];
  anomalies: Anomaly[] | { anomalies?: Anomaly[]; count?: number };
}

type TrendPoint = {
  period: string;
  revenue: number;
  expense: number;
};

function formatNumber(n: number): string {
  return n.toLocaleString('en-US', {
    maximumFractionDigits: 2,
  });
}

function parseISODate(value: unknown): Date | null {
  if (typeof value !== 'string') return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d;
}

function normalizeAmount(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const normalized = value.replace(/[$,\s]/g, '');
    if (normalized === '') return null;
    const n = Number(normalized);
    if (!Number.isFinite(n)) return null;
    return n;
  }
  return null;
}

function periodKey(d: Date, granularity: 'day' | 'month'): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  if (granularity === 'month') return `${yyyy}-${mm}`;
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function inferGranularity(dates: Date[]): 'day' | 'month' {
  if (dates.length < 2) return 'day';
  const sorted = [...dates].sort((a, b) => a.getTime() - b.getTime());
  const rangeMs = sorted[sorted.length - 1].getTime() - sorted[0].getTime();
  const rangeDays = rangeMs / (1000 * 60 * 60 * 24);
  return rangeDays > 90 ? 'month' : 'day';
}

function severityColor(sev: Severity): string {
  if (sev === 'high') return 'rgba(248,113,113,0.55)';
  if (sev === 'medium') return 'rgba(251,191,36,0.55)';
  return 'rgba(34,211,238,0.45)';
}

export default function InsightsDashboard({ rows, anomalies }: InsightsDashboardProps) {
  const anomaliesArray: Anomaly[] = useMemo(() => {
    if (Array.isArray(anomalies)) return anomalies;
    if (anomalies && typeof anomalies === 'object' && Array.isArray((anomalies as any).anomalies)) {
      return (anomalies as any).anomalies;
    }
    return [];
  }, [anomalies]);

  const hasAnomalies = anomaliesArray.length > 0;

  const evaluatedAt = useMemo(() => new Date().toLocaleString(), []);

  const { trend, dateRange } = useMemo(() => {
    const usable: { date: Date; amount: number }[] = [];

    for (const r of rows) {
      const raw = r.raw_json || {};
      const d = parseISODate(raw.transaction_date);
      const amt = normalizeAmount(raw.amount);
      if (!d || amt == null) continue;
      usable.push({ date: d, amount: amt });
    }

    const g = inferGranularity(usable.map(u => u.date));

    const buckets = new Map<string, { revenue: number; expense: number }>();
    for (const u of usable) {
      const key = periodKey(u.date, g);
      const prev = buckets.get(key) || { revenue: 0, expense: 0 };

      if (u.amount > 0) prev.revenue += u.amount;
      if (u.amount < 0) prev.expense += Math.abs(u.amount);

      buckets.set(key, prev);
    }

    const points: TrendPoint[] = Array.from(buckets.entries())
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([period, v]) => ({ period, revenue: v.revenue, expense: v.expense }));

    const sortedDates = usable.map(u => u.date).sort((a, b) => a.getTime() - b.getTime());
    const min = sortedDates[0] || null;
    const max = sortedDates[sortedDates.length - 1] || null;
    const fmt = (d: Date | null) => (d ? d.toISOString().slice(0, 10) : '—');

    return {
      trend: points,
      dateRange: {
        min: fmt(min),
        max: fmt(max),
      },
    };
  }, [rows]);

  const anomalyTop = useMemo(() => {
    const counts = new Map<string, { count: number; severity: Severity }>();

    for (const a of anomaliesArray || []) {
      const key = a?.anomaly_type || 'unknown';
      const prev = counts.get(key);

      const sevText = typeof a?.severity === 'string' ? a.severity.toLowerCase() : 'low';
      const sev: Severity = sevText === 'high' || sevText === 'medium' || sevText === 'low' ? sevText : 'low';

      if (!prev) {
        counts.set(key, { count: 1, severity: sev || 'low' });
        continue;
      }

      prev.count += 1;
      const sevRank = (s: Severity) => (s === 'high' ? 3 : s === 'medium' ? 2 : 1);
      if (sevRank(sev) > sevRank(prev.severity)) prev.severity = sev;
      counts.set(key, prev);
    }

    return Array.from(counts.entries())
      .map(([category, v]) => ({ category, count: v.count, severity: v.severity }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }, [anomaliesArray]);

  const AnomalyOverviewTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || payload.length === 0) return null;
    const entry = payload?.[0]?.payload;
    const sev = typeof entry?.severity === 'string' ? String(entry.severity).toUpperCase() : '';

    return (
      <div className="bg-[#0D0F12] border border-gray-700 rounded-lg px-3 py-2">
        <div className="text-sm text-gray-200 font-medium">{label}</div>
        {sev && <div className="text-xs text-gray-500 mt-0.5">{sev}</div>}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="bg-[#0D0F12] border border-gray-700 rounded-lg p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-semibold text-gray-100">Risk Coverage</div>
            <div className="text-xs text-gray-500 mt-1">Coverage reflects the breadth of enabled detection checks.</div>
          </div>

          <div className="text-right">
            <div className="text-2xl font-semibold text-cyan-200">72%</div>
            <div className="text-[11px] uppercase tracking-wider text-gray-500">coverage</div>
          </div>
        </div>

        <div className="mt-4 h-2 bg-[#0B0D10] border border-gray-800 rounded overflow-hidden">
          <div className="h-full bg-cyan-500/40" style={{ width: '72%' }} />
        </div>

        <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="text-xs font-semibold text-gray-300 mb-2">Completed checks</div>
            <div className="space-y-2 text-sm text-gray-200">
              <div className="flex items-center justify-between bg-[#0B0D10] border border-gray-800 rounded px-3 py-2">
                <div>Amount outliers</div>
                <div className="text-xs text-gray-500">Enabled</div>
              </div>
              <div className="flex items-center justify-between bg-[#0B0D10] border border-gray-800 rounded px-3 py-2">
                <div>Frequency anomalies</div>
                <div className="text-xs text-gray-500">Enabled</div>
              </div>
              <div className="flex items-center justify-between bg-[#0B0D10] border border-gray-800 rounded px-3 py-2">
                <div>Balance inconsistencies</div>
                <div className="text-xs text-gray-500">Enabled</div>
              </div>
            </div>
          </div>

          <div>
            <div className="text-xs font-semibold text-gray-300 mb-2">Roadmap</div>
            <div className="space-y-2 text-sm text-gray-400">
              <div className="flex items-center justify-between bg-[#0B0D10] border border-gray-800 rounded px-3 py-2 opacity-70">
                <div className="flex items-center gap-2">
                  <Info className="h-4 w-4 text-gray-500" />
                  Counterparty concentration
                </div>
                <div className="text-xs text-gray-500">Coming soon</div>
              </div>
              <div className="flex items-center justify-between bg-[#0B0D10] border border-gray-800 rounded px-3 py-2 opacity-70">
                <div className="flex items-center gap-2">
                  <Info className="h-4 w-4 text-gray-500" />
                  Seasonal drift
                </div>
                <div className="text-xs text-gray-500">Coming soon</div>
              </div>
              <div className="flex items-center justify-between bg-[#0B0D10] border border-gray-800 rounded px-3 py-2 opacity-70">
                <div className="flex items-center gap-2">
                  <Info className="h-4 w-4 text-gray-500" />
                  Macro stress overlays
                </div>
                <div className="text-xs text-gray-500">Coming soon</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {!hasAnomalies && (
        <div className="bg-[#0D0F12] border border-gray-700 rounded-lg p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-semibold text-gray-100">Clean Data Snapshot</div>
              <div className="mt-1 text-sm text-gray-300 leading-relaxed">
                No anomalies were detected by the current detection engines for this dataset.
              </div>
              <div className="mt-2 text-xs text-gray-500">
                This reflects only the checks currently enabled and does not guarantee the absence of financial, operational, or fraud risk.
              </div>

              <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-3">
                <div className="bg-[#0B0D10] border border-gray-800 rounded p-3">
                  <div className="text-[11px] text-gray-500">Rows analyzed</div>
                  <div className="text-sm text-gray-200 mt-1">{rows.length.toLocaleString()}</div>
                </div>
                <div className="bg-[#0B0D10] border border-gray-800 rounded p-3">
                  <div className="text-[11px] text-gray-500">Date range</div>
                  <div className="text-sm text-gray-200 mt-1">
                    {dateRange.min} → {dateRange.max}
                  </div>
                </div>
                <div className="bg-[#0B0D10] border border-gray-800 rounded p-3">
                  <div className="text-[11px] text-gray-500">Engines</div>
                  <div className="text-sm text-gray-200 mt-1">Rules + statistical outliers</div>
                </div>
                <div className="bg-[#0B0D10] border border-gray-800 rounded p-3">
                  <div className="text-[11px] text-gray-500">Evaluated</div>
                  <div className="text-sm text-gray-200 mt-1">{evaluatedAt}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#0D0F12] border border-gray-700 rounded-lg p-4">
          <div className="text-sm font-semibold text-gray-200 mb-3">Revenue Trends</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#2B2F36" strokeDasharray="3 3" />
                <XAxis dataKey="period" tick={{ fill: '#9CA3AF', fontSize: 12 }} />
                <YAxis tick={{ fill: '#9CA3AF', fontSize: 12 }} tickFormatter={(v) => formatNumber(Number(v))} />
                <Tooltip
                  contentStyle={{ background: '#0D0F12', border: '1px solid #374151', color: '#E5E7EB' }}
                  formatter={(v: any) => formatNumber(Number(v))}
                />
                <Line type="monotone" dataKey="revenue" stroke="#22D3EE" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-[#0D0F12] border border-gray-700 rounded-lg p-4">
          <div className="text-sm font-semibold text-gray-200 mb-3">Expense Trends</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#2B2F36" strokeDasharray="3 3" />
                <XAxis dataKey="period" tick={{ fill: '#9CA3AF', fontSize: 12 }} />
                <YAxis tick={{ fill: '#9CA3AF', fontSize: 12 }} tickFormatter={(v) => formatNumber(Number(v))} />
                <Tooltip
                  contentStyle={{ background: '#0D0F12', border: '1px solid #374151', color: '#E5E7EB' }}
                  formatter={(v: any) => formatNumber(Number(v))}
                />
                <Line type="monotone" dataKey="expense" stroke="#94A3B8" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {hasAnomalies && (
        <div className="bg-[#0D0F12] border border-gray-700 rounded-lg p-4">
          <div className="text-sm font-semibold text-gray-200 mb-3">Anomalies Overview (Top Categories)</div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={anomalyTop} margin={{ top: 10, right: 16, left: 0, bottom: 40 }}>
                <CartesianGrid stroke="#2B2F36" strokeDasharray="3 3" />
                <XAxis
                  dataKey="category"
                  interval={0}
                  angle={-25}
                  textAnchor="end"
                  height={60}
                  tick={{ fill: '#9CA3AF', fontSize: 12 }}
                />
                <Tooltip content={<AnomalyOverviewTooltip />} />
                <Bar dataKey="count">
                  {anomalyTop.map((entry, idx) => (
                    <Cell key={idx} fill={severityColor(entry.severity)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="bg-[#0D0F12] border border-gray-700 rounded-lg p-4" title="Insights assistant coming soon">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold text-gray-200">Ask Parity</div>
          <MessageSquare className="h-4 w-4 text-gray-500" />
        </div>
        <div className="flex items-center gap-3">
          <input
            disabled
            className="flex-1 px-3 py-2 bg-[#0D0F12] border border-gray-700 rounded-lg text-gray-400 placeholder-gray-600"
            placeholder="Ask Parity…"
            value=""
            readOnly
          />
          <button
            disabled
            className="px-4 py-2 bg-gray-800 text-gray-500 rounded-lg border border-gray-700 cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
