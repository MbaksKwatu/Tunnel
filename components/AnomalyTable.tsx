'use client';

import { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { API_URL } from '@/lib/api';

interface Anomaly {
  id: string;
  document_id: string;
  row_index: number;
  anomaly_type: string;
  severity: 'high' | 'medium' | 'low';
  description: string;
  suggested_action?: string;
  raw_json?: Record<string, any>;
  detected_at?: string;
}

interface AnomalyTableProps {
  documentId: string;
  onRowClick?: (rowIndex: number) => void;
}

export default function AnomalyTable({ documentId, onRowClick }: AnomalyTableProps) {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<'all' | 'high' | 'medium' | 'low'>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [sortColumn, setSortColumn] = useState<string>('severity');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    loadAnomalies();
  }, [documentId]);

  const loadAnomalies = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_URL}/api/anomalies?doc_id=${documentId}`);
      if (!response.ok) throw new Error('Failed to load anomalies');
      const data = await response.json();
      setAnomalies(data.anomalies || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load anomalies');
    } finally {
      setLoading(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    const colors = {
      high: 'border-red-500/40 text-red-300',
      medium: 'border-amber-500/40 text-amber-300',
      low: 'border-cyan-400/30 text-cyan-200',
    };

    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border bg-transparent ${colors[severity as keyof typeof colors] || 'border-gray-600 text-gray-300'}`}
      >
        {severity.toUpperCase()}
      </span>
    );
  };

  const getAnomalyTypeName = (type: string) => {
    const names: Record<string, string> = {
      revenue_anomaly: 'Revenue Anomaly',
      expense_integrity: 'Expense Integrity',
      cashflow_consistency: 'Cash Flow Consistency',
      payroll_pattern: 'Payroll Pattern',
      declared_mismatch: 'Declared Mismatch',
      unsupervised_outlier: 'Statistical Outlier'
    };
    return names[type] || type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const getTransactionContext = (anomaly: Anomaly) => {
    const raw = anomaly.raw_json || {};

    const findValue = (pred: (key: string, value: any) => boolean) => {
      for (const [k, v] of Object.entries(raw)) {
        if (v == null || v === '') continue;
        if (pred(k, v)) return v;
      }
      return undefined;
    };

    const txType =
      (typeof raw.type === 'string' && raw.type) ||
      (typeof raw.transaction_type === 'string' && raw.transaction_type) ||
      (typeof findValue((k, v) => /transaction\s*type/i.test(k) && typeof v === 'string') === 'string'
        ? (findValue((k, v) => /transaction\s*type/i.test(k) && typeof v === 'string') as string)
        : undefined);

    const direction =
      (typeof raw.direction === 'string' && raw.direction) ||
      (typeof raw.paid_in_out === 'string' && raw.paid_in_out) ||
      (typeof findValue((k, v) => /(paid\s*in\s*\/?\s*out|direction|debit|credit)/i.test(k) && typeof v === 'string') === 'string'
        ? (findValue((k, v) => /(paid\s*in\s*\/?\s*out|direction|debit|credit)/i.test(k) && typeof v === 'string') as string)
        : undefined);

    const amountVal =
      raw.amount ??
      raw.Amount ??
      findValue((k, _v) => /amount/i.test(k));

    const amount = (() => {
      if (amountVal == null || amountVal === '') return undefined;
      if (typeof amountVal === 'number' && Number.isFinite(amountVal)) return amountVal.toLocaleString('en-US');
      return String(amountVal);
    })();

    const parts = [txType, amount, direction, anomaly.row_index >= 0 ? `Row ${anomaly.row_index + 1}` : undefined].filter(Boolean);
    return parts.length > 0 ? `Transaction: ${parts.join(' · ')}` : undefined;
  };

  const filteredAnomalies = anomalies.filter(a => {
    if (filterSeverity !== 'all' && a.severity !== filterSeverity) return false;
    if (filterType !== 'all' && a.anomaly_type !== filterType) return false;
    return true;
  });

  const sortedAnomalies = [...filteredAnomalies].sort((a, b) => {
    let aVal: any, bVal: any;

    switch (sortColumn) {
      case 'severity':
        const severityOrder = { high: 3, medium: 2, low: 1 };
        aVal = severityOrder[a.severity as keyof typeof severityOrder] || 0;
        bVal = severityOrder[b.severity as keyof typeof severityOrder] || 0;
        break;
      case 'type':
        aVal = a.anomaly_type;
        bVal = b.anomaly_type;
        break;
      case 'row':
        aVal = a.row_index;
        bVal = b.row_index;
        break;
      default:
        aVal = a.description;
        bVal = b.description;
    }

    if (sortDirection === 'asc') {
      return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
    } else {
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
    }
  });

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  const uniqueTypes = Array.from(new Set(anomalies.map(a => a.anomaly_type)));

  if (loading) {
    return (
      <div className="p-4 bg-[#1B1E23] border border-gray-700 rounded-lg">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-700/50 rounded w-1/4"></div>
          <div className="flex gap-4">
            <div className="h-8 bg-gray-700/50 rounded w-32"></div>
            <div className="h-8 bg-gray-700/50 rounded w-32"></div>
          </div>
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="h-12 bg-gray-800/60 rounded w-full"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-900/20 border border-red-800 rounded-lg">
        <p className="text-red-300">{error}</p>
      </div>
    );
  }

  if (anomalies.length === 0) {
    return (
      <div className="p-6 bg-[#1B1E23] border border-gray-700 rounded-lg">
        <h3 className="text-lg font-semibold text-gray-100 mb-2">Anomalies</h3>
        <p className="text-gray-400">No anomalies detected. Data appears clean.</p>
      </div>
    );
  }

  return (
    <div className="p-6 bg-[#1B1E23] border border-gray-700 rounded-lg">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-100">Detected Anomalies</h3>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6">
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1">Severity</label>
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value as any)}
            className="bg-[#0D0F12] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-cyan-400 focus:border-transparent"
          >
            <option value="all">All</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1">Type</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-[#0D0F12] border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-cyan-400 focus:border-transparent"
          >
            <option value="all">All Types</option>
            {uniqueTypes.map(type => (
              <option key={type} value={type}>{getAnomalyTypeName(type)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#0D0F12] border-b border-gray-700">
            <tr>
              <th
                className="text-left px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-[#23272E] transition-colors"
                onClick={() => handleSort('severity')}
              >
                <div className="flex items-center gap-1">
                  Severity
                  {sortColumn === 'severity' && (
                    sortDirection === 'asc' ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
                  )}
                </div>
              </th>
              <th className="text-left px-3 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Anomaly</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {sortedAnomalies.map((anomaly) => (
              <tr
                key={anomaly.id}
                className={`${onRowClick && anomaly.row_index >= 0 ? 'cursor-pointer' : ''} hover:bg-[#23272E] transition-colors`}
                onClick={() => {
                  if (!onRowClick) return;
                  if (anomaly.row_index < 0) return;
                  onRowClick(anomaly.row_index);
                }}
              >
                <td className="px-3 py-3">
                  {getSeverityBadge(anomaly.severity)}
                </td>
                <td className="px-3 py-3">
                  <div className="space-y-1">
                    <div className="text-gray-100 font-medium">{anomaly.description}</div>
                    {getTransactionContext(anomaly) && (
                      <div className="text-gray-400 text-xs">{getTransactionContext(anomaly)}</div>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sortedAnomalies.length === 0 && (
        <p className="text-center text-gray-400 py-6">No anomalies match the selected filters.</p>
      )}
    </div>
  );
}


