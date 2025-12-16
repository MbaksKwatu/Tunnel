'use client';

import { useState, useEffect, useMemo } from 'react';
import { Download, X, Search, ArrowUpDown, ChevronLeft, ChevronRight, RefreshCw, AlertTriangle } from 'lucide-react';
import { getExtractedRows, Document, ExtractedRow } from '@/lib/supabase';
import AnomalyTable from './AnomalyTable';
import InsightsDashboard from './InsightsDashboard';
import { API_URL } from '@/lib/api';

interface DataReviewProps {
  document: Document;
  onClose: () => void;
}

export default function DataReview({ document, onClose }: DataReviewProps) {
  const [rows, setRows] = useState<ExtractedRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [anomaliesLoading, setAnomaliesLoading] = useState(false);
  const [anomaliesError, setAnomaliesError] = useState<string | null>(null);
  const [anomaliesLoaded, setAnomaliesLoaded] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const [viewMode, setViewMode] = useState<'data' | 'anomalies' | 'insights'>('data');
  const [rerunLoading, setRerunLoading] = useState(false);
  const [showColumnsMenu, setShowColumnsMenu] = useState(false);
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const rowsPerPage = 50;

  useEffect(() => {
    loadRows();
  }, [document.id]);

  useEffect(() => {
    setAnomalies([]);
    setAnomaliesError(null);
    setAnomaliesLoaded(false);
  }, [document.id]);

  useEffect(() => {
    if (viewMode !== 'insights') return;
    if (anomaliesLoading) return;
    if (anomaliesLoaded) return;

    const loadAnomalies = async () => {
      try {
        setAnomaliesLoading(true);
        setAnomaliesError(null);
        const res = await fetch(`${API_URL}/document/${document.id}/anomalies`);
        if (!res.ok) throw new Error('Failed to load anomalies');
        const data = await res.json();
        setAnomalies(data.anomalies || []);
      } catch (e: any) {
        setAnomaliesError(e?.message || 'Failed to load anomalies');
        setAnomalies([]);
      } finally {
        setAnomaliesLoaded(true);
        setAnomaliesLoading(false);
      }
    };

    loadAnomalies();
  }, [viewMode, anomaliesLoading, anomaliesLoaded, document.id]);

  const loadRows = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getExtractedRows(document.id);
      setRows(data);
    } catch (err: any) {
      console.error('Error loading rows:', err);
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const rerunDetection = async () => {
    try {
      setRerunLoading(true);
      const response = await fetch(`${API_URL}/api/anomalies/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_id: document.id })
      });

      if (!response.ok) throw new Error('Failed to rerun detection');

      // Refresh the page to show updated data
      window.location.reload();
    } catch (err: any) {
      console.error('Error rerunning detection:', err);
      setError(err.message || 'Failed to rerun detection');
    } finally {
      setRerunLoading(false);
    }
  };

  // Get all unique columns from the data
  const columns = useMemo(() => {
    if (rows.length === 0) return [];
    const allKeys = new Set<string>();
    rows.forEach(row => {
      Object.keys(row.raw_json).forEach(key => allKeys.add(key));
    });
    return Array.from(allKeys);
  }, [rows]);

  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (columns.length === 0) return;
    setVisibleColumns(prev => {
      if (prev.size > 0) return prev;
      return new Set(columns);
    });
  }, [columns]);

  const displayedColumns = useMemo(() => {
    if (columns.length === 0) return [];
    if (visibleColumns.size === 0) return columns;
    return columns.filter(c => visibleColumns.has(c));
  }, [columns, visibleColumns]);

  const formatCell = (column: string, value: any): { text: string; alignRight: boolean } => {
    if (value == null) return { text: '', alignRight: false };

    const rawText = typeof value === 'string' ? value : String(value);

    const looksLikeDate = typeof value === 'string' && value.length >= 8 && !Number.isNaN(Date.parse(value));
    if (looksLikeDate) {
      const d = new Date(value);
      const yyyy = d.getFullYear();
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return { text: `${yyyy}-${mm}-${dd}`, alignRight: false };
    }

    if (typeof value === 'number' && Number.isFinite(value)) {
      const isMoneyCol = /amount|revenue|cost|expense|price|total|balance|cash|usd|gbp|eur/i.test(column);
      const text = value.toLocaleString('en-US', {
        minimumFractionDigits: isMoneyCol ? 2 : 0,
        maximumFractionDigits: isMoneyCol ? 2 : 6,
      });
      return { text, alignRight: true };
    }

    const normalized = rawText.replace(/[$,\s]/g, '');
    const asNum = Number(normalized);
    if (rawText !== '' && Number.isFinite(asNum) && normalized !== '' && /^-?\d+(\.\d+)?$/.test(normalized)) {
      const isMoneyCol = /amount|revenue|cost|expense|price|total|balance|cash|usd|gbp|eur/i.test(column) || rawText.includes('$');
      const text = asNum.toLocaleString('en-US', {
        minimumFractionDigits: isMoneyCol ? 2 : 0,
        maximumFractionDigits: isMoneyCol ? 2 : 6,
      });
      return { text, alignRight: true };
    }

    return { text: rawText, alignRight: false };
  };

  // Filter and sort rows
  const processedRows = useMemo(() => {
    let filtered = rows;

    // Search filter
    if (searchTerm) {
      filtered = filtered.filter(row => {
        const searchLower = searchTerm.toLowerCase();
        return Object.values(row.raw_json).some(value =>
          String(value).toLowerCase().includes(searchLower)
        );
      });
    }

    // Sort
    if (sortColumn) {
      filtered = [...filtered].sort((a, b) => {
        const aVal = a.raw_json[sortColumn];
        const bVal = b.raw_json[sortColumn];

        if (aVal === bVal) return 0;
        if (aVal == null) return 1;
        if (bVal == null) return -1;

        const comparison = aVal < bVal ? -1 : 1;
        return sortDirection === 'asc' ? comparison : -comparison;
      });
    }

    return filtered;
  }, [rows, searchTerm, sortColumn, sortDirection]);

  // Pagination
  const totalPages = Math.ceil(processedRows.length / rowsPerPage);
  const paginatedRows = processedRows.slice(
    (currentPage - 1) * rowsPerPage,
    currentPage * rowsPerPage
  );

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const downloadCSV = () => {
    if (rows.length === 0) return;

    // Create CSV content
    const headers = columns.join(',');
    const csvRows = rows.map(row =>
      columns.map(col => {
        const value = row.raw_json[col];
        // Escape quotes and wrap in quotes if contains comma
        const stringValue = String(value ?? '');
        return stringValue.includes(',') || stringValue.includes('"')
          ? `"${stringValue.replace(/"/g, '""')}"`
          : stringValue;
      }).join(',')
    );

    const csv = [headers, ...csvRows].join('\n');

    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = `${document.file_name}_extracted.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const startResize = (column: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const startX = e.clientX;
    const startWidth = columnWidths[column] || 180;

    const onMove = (ev: MouseEvent) => {
      const delta = ev.clientX - startX;
      const next = Math.max(90, startWidth + delta);
      setColumnWidths(prev => ({ ...prev, [column]: next }));
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-[#1B1E23] border border-gray-700 rounded-lg shadow-xl max-w-7xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <div>
            <h2 className="text-xl font-semibold text-gray-100">{document.file_name}</h2>
            <p className="text-sm text-gray-400 mt-1">
              {processedRows.length} rows {searchTerm && `(filtered from ${rows.length})`}
            </p>
          </div>

          <div className="flex items-center space-x-3">
            {/* View Mode Toggle */}
            <div className="flex bg-[#0D0F12] rounded-lg p-1 border border-gray-700">
              <button
                onClick={() => setViewMode('data')}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${viewMode === 'data'
                  ? 'bg-[#1B1E23] text-gray-100 shadow-sm border border-gray-700'
                  : 'text-gray-400 hover:text-gray-200'
                  }`}
              >
                Data
              </button>
              <button
                onClick={() => setViewMode('anomalies')}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors relative ${viewMode === 'anomalies'
                  ? 'bg-[#1B1E23] text-gray-100 shadow-sm border border-gray-700'
                  : 'text-gray-400 hover:text-gray-200'
                  }`}
              >
                Anomalies
                {document.anomalies_count && document.anomalies_count > 0 && (
                  <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                    {document.anomalies_count}
                  </span>
                )}
              </button>
              <button
                onClick={() => setViewMode('insights')}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${viewMode === 'insights'
                  ? 'bg-[#1B1E23] text-gray-100 shadow-sm border border-gray-700'
                  : 'text-gray-400 hover:text-gray-200'
                  }`}
              >
                Insights
              </button>
            </div>

            {/* Re-run Detection Button (shown only in Anomalies tab) */}
            {viewMode === 'anomalies' && (
              <button
                onClick={rerunDetection}
                disabled={rerunLoading}
                className="px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 transition-colors flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw className={`h-4 w-4 ${rerunLoading ? 'animate-spin' : ''}`} />
                <span>{rerunLoading ? 'Running...' : 'Re-run Detection'}</span>
              </button>
            )}

            
            <button
              disabled
              className="px-4 py-2 bg-gray-800 text-gray-400 rounded-lg border border-gray-700 cursor-not-allowed"
              title="Disabled"
            >
              Generate Report
            </button>

            {/* Download Buttons */}
            <button
              onClick={downloadCSV}
              className="px-4 py-2 bg-gradient-to-r from-cyan-400 to-green-400 text-[#0D0F12] font-semibold rounded-lg hover:opacity-90 transition-opacity flex items-center space-x-2"
            >
              <Download className="h-4 w-4" />
              <span>CSV</span>
            </button>

            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-[#23272E] transition-colors"
            >
              <X className="h-6 w-6" />
            </button>
          </div>
        </div>

        {viewMode === 'data' && (
          <div className="p-4 border-b border-gray-700">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search in data..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full pl-10 pr-4 py-2 bg-[#0D0F12] border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:ring-2 focus:ring-cyan-400 focus:border-transparent"
              />
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {viewMode === 'anomalies' ? (
            <AnomalyTable documentId={document.id} />
          ) : viewMode === 'insights' ? (
            loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-gray-400">Loading data...</div>
              </div>
            ) : error ? (
              <div className="bg-red-900/20 border border-red-800 rounded-lg p-4">
                <p className="text-red-400">{error}</p>
              </div>
            ) : rows.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-400">No data found</p>
              </div>
            ) : anomaliesError ? (
              <div className="bg-red-900/20 border border-red-800 rounded-lg p-4">
                <p className="text-red-400">{anomaliesError}</p>
              </div>
            ) : anomaliesLoading ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-gray-400">Loading insights...</div>
              </div>
            ) : (
              <InsightsDashboard rows={rows} anomalies={anomalies} />
            )
          ) : loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-gray-400">Loading data...</div>
            </div>
          ) : error ? (
            <div className="bg-red-900/20 border border-red-800 rounded-lg p-4">
              <p className="text-red-400">{error}</p>
            </div>
          ) : rows.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400">No data found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <div className="flex items-center justify-between mb-3">
                <div className="text-xs text-gray-400">
                  Rows per page: {rowsPerPage}
                </div>

                <div className="relative">
                  <button
                    onClick={() => setShowColumnsMenu(v => !v)}
                    className="px-3 py-2 bg-[#0D0F12] border border-gray-700 text-gray-200 rounded-lg hover:bg-[#23272E] transition-colors text-sm"
                  >
                    Columns
                  </button>

                  {showColumnsMenu && (
                    <div className="absolute right-0 mt-2 w-64 bg-[#0D0F12] border border-gray-700 rounded-lg shadow-xl p-3 z-10 max-h-80 overflow-auto">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-xs font-semibold text-gray-300">Show/Hide</div>
                        <button
                          onClick={() => setVisibleColumns(new Set(columns))}
                          className="text-xs text-cyan-400 hover:text-cyan-300"
                        >
                          Reset
                        </button>
                      </div>

                      {columns.map(col => (
                        <label key={col} className="flex items-center space-x-2 py-1 text-sm text-gray-200">
                          <input
                            type="checkbox"
                            checked={visibleColumns.size === 0 ? true : visibleColumns.has(col)}
                            onChange={() => {
                              setVisibleColumns(prev => {
                                const base = prev.size === 0 ? new Set(columns) : new Set(prev);
                                if (base.has(col)) base.delete(col);
                                else base.add(col);
                                return base;
                              });
                            }}
                          />
                          <span className="truncate" title={col}>{col}</span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <table className="min-w-full divide-y divide-gray-700" style={{ tableLayout: 'fixed' }}>
                <thead className="bg-[#0D0F12] sticky top-0 border-b border-gray-700">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider" style={{ width: 70 }}>
                      #
                    </th>
                    {displayedColumns.map(column => (
                      <th
                        key={column}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-[#23272E] transition-colors relative"
                        onClick={() => handleSort(column)}
                        style={{ width: columnWidths[column] || 180 }}
                      >
                        <div className="flex items-center space-x-1">
                          <span>{column}</span>
                          {sortColumn === column && (
                            <ArrowUpDown className="h-3 w-3" />
                          )}
                        </div>
                        <div
                          onMouseDown={(e) => startResize(column, e)}
                          className="absolute right-0 top-0 h-full w-2 cursor-col-resize"
                          role="separator"
                          aria-label={`Resize ${column}`}
                        />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-[#1B1E23] divide-y divide-gray-700">
                  {paginatedRows.map((row, index) => (
                    <tr key={row.id} className="hover:bg-[#23272E] transition-colors">
                      <td className="px-4 py-3 text-sm text-gray-400">
                        {(currentPage - 1) * rowsPerPage + index + 1}
                      </td>
                      {displayedColumns.map(column => {
                        const formatted = formatCell(column, row.raw_json[column]);
                        return (
                          <td
                            key={column}
                            className={`px-4 py-3 text-sm text-gray-100 ${formatted.alignRight ? 'text-right tabular-nums' : ''}`}
                            style={{ width: columnWidths[column] || 180 }}
                          >
                            {formatted.text}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination */}
        {viewMode === 'data' && totalPages > 1 && (
          <div className="flex items-center justify-between p-4 border-t border-gray-700">
            <div className="text-sm text-gray-400">
              Rows {(currentPage - 1) * rowsPerPage + 1}
              {'–'}
              {Math.min(currentPage * rowsPerPage, processedRows.length)}
              {' '}of {processedRows.length}
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="p-2 rounded-lg border border-gray-700 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[#23272E] transition-colors text-gray-400 hover:text-gray-200"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>

              <span className="text-sm text-gray-300">
                Page {currentPage} of {totalPages}
              </span>

              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="p-2 rounded-lg border border-gray-700 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[#23272E] transition-colors text-gray-400 hover:text-gray-200"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


