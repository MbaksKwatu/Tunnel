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
import { MessageSquare } from 'lucide-react';

type Severity = 'high' | 'medium' | 'low';

interface Anomaly {
  anomaly_type: string;
  severity: Severity;
}

interface InsightsDashboardProps {
  rows: ExtractedRow[];
  anomalies: Anomaly[];
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
  if (sev === 'high') return '#EF4444';
  if (sev === 'medium') return '#F59E0B';
  return '#3B82F6';
}

export default function InsightsDashboard({ rows, anomalies }: InsightsDashboardProps) {
  const { trend } = useMemo(() => {
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

    return {
      trend: points,
    };
  }, [rows]);

  const anomalyTop = useMemo(() => {
    const counts = new Map<string, { count: number; severity: Severity }>();

    for (const a of anomalies || []) {
      const key = a.anomaly_type || 'unknown';
      const prev = counts.get(key);

      if (!prev) {
        counts.set(key, { count: 1, severity: a.severity || 'low' });
        continue;
      }

      prev.count += 1;
      const sevRank = (s: Severity) => (s === 'high' ? 3 : s === 'medium' ? 2 : 1);
      if (sevRank(a.severity) > sevRank(prev.severity)) prev.severity = a.severity;
      counts.set(key, prev);
    }

    return Array.from(counts.entries())
      .map(([category, v]) => ({ category, count: v.count, severity: v.severity }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }, [anomalies]);

  return (
    <div className="space-y-6">
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
                <Line type="monotone" dataKey="revenue" stroke="#22C55E" strokeWidth={2} dot={false} />
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
                <Line type="monotone" dataKey="expense" stroke="#EF4444" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

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
              <YAxis tick={{ fill: '#9CA3AF', fontSize: 12 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: '#0D0F12', border: '1px solid #374151', color: '#E5E7EB' }}
              />
              <Bar dataKey="count">
                {anomalyTop.map((entry, idx) => (
                  <Cell key={idx} fill={severityColor(entry.severity)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

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
