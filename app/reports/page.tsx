'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import Sidebar from '@/components/Layout/Sidebar';

interface DocumentSummary {
  id: string;
  file_name: string;
  upload_date: string;
  status: string;
}

export default function ReportsPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<DocumentSummary[]>(`${apiUrl}/documents`);
      setDocuments(res.data || []);
      if (res.data && res.data.length > 0) {
        setSelectedDocId(res.data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch documents', err);
      setError('Failed to load documents. Please check the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const generateIC = async () => {
    if (!selectedDocId) {
      setError('Select a document first.');
      return;
    }
    setError(null);
    setMessage('Generating IC Report...');
    try {
      const url = `${apiUrl}/document/${selectedDocId}/report`;
      window.open(url, '_blank');
      setMessage('IC Report requested. It should download/open in a new tab.');
    } catch (err) {
      console.error('Failed to generate IC report', err);
      setError('Failed to generate IC report.');
      setMessage(null);
    }
  };

  const generateCustomReport = async () => {
    if (!selectedDocId) {
      setError('Select a document first.');
      return;
    }
    setError(null);
    setMessage('Generating AI Custom Report...');
    try {
      // For now we pass a very lightweight summary; in a richer version
      // you might fetch /document/{id}/insights or metrics first.
      const selected = documents.find((d) => d.id === selectedDocId);
      const payload = {
        data_summary: selected
          ? `Document ${selected.file_name} (id=${selected.id}, uploaded=${selected.upload_date}).`
          : `Document id=${selectedDocId}.`,
      };
      const res = await axios.post<{ report: string }>(
        `${apiUrl}/generate-custom-report`,
        payload
      );
      const text = res.data?.report || 'No report text returned.';
      setMessage(null);
      // Show the report in a simple modal-like overlay for now
      alert(text);
    } catch (err: any) {
      console.error('Failed to generate custom report', err);
      setError(
        err?.response?.data?.detail ||
          'Failed to generate AI custom report. Check OPENAI_API_KEY on the backend.'
      );
      setMessage(null);
    }
  };

  return (
    <div className="flex min-h-screen bg-base-950">
      <Sidebar />

      <main className="flex-1 p-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Reports</h1>
            <p className="text-slate-400 mt-1">
              Generate Investment Committee PDFs or AI-powered narrative reports.
            </p>
          </div>
          <button
            onClick={() => router.push('/dashboard')}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-100 text-sm"
          >
            Back to Dashboard
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm text-red-200">
            {error}
          </div>
        )}
        {message && (
          <div className="mb-4 rounded border border-blue-500/40 bg-blue-500/10 px-4 py-2 text-sm text-blue-200">
            {message}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
              Documents
            </h2>
            <div className="rounded-lg border border-slate-800 bg-dark-card overflow-hidden">
              {loading ? (
                <div className="p-6 text-slate-400 text-sm">Loading documents…</div>
              ) : documents.length === 0 ? (
                <div className="p-6 text-slate-400 text-sm">
                  No documents found. Upload a file from the Dashboard or Upload page.
                </div>
              ) : (
                <ul className="divide-y divide-slate-800">
                  {documents.map((doc) => (
                    <li
                      key={doc.id}
                      onClick={() => setSelectedDocId(doc.id)}
                      className={`flex items-center justify-between px-4 py-3 text-sm cursor-pointer transition-colors
                        ${
                          selectedDocId === doc.id
                            ? 'bg-blue-500/10 border-l-2 border-l-blue-500'
                            : 'hover:bg-slate-900'
                        }`}
                    >
                      <div>
                        <div className="font-medium text-slate-100">{doc.file_name}</div>
                        <div className="text-xs text-slate-500">
                          Uploaded {doc.upload_date || 'unknown'} • Status {doc.status}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
              Report Types
            </h2>

            <div className="rounded-lg border border-slate-800 bg-dark-card p-4 space-y-3">
              <h3 className="text-base font-semibold text-slate-100">IC Report (PDF)</h3>
              <p className="text-xs text-slate-400">
                Generates a structured Investment Committee PDF using anomalies, insights, and
                key metrics from the selected document.
              </p>
              <button
                onClick={generateIC}
                disabled={!selectedDocId}
                className="mt-2 w-full px-4 py-2 rounded-lg bg-blue-500 hover:bg-blue-600 disabled:bg-slate-700 disabled:text-slate-400 text-white text-sm font-medium"
              >
                Generate IC Report
              </button>
            </div>

            <div className="rounded-lg border border-slate-800 bg-dark-card p-4 space-y-3">
              <h3 className="text-base font-semibold text-slate-100">AI Custom Report</h3>
              <p className="text-xs text-slate-400">
                Uses Parity&apos;s AI analyst to generate a narrative investment memo for the
                selected document. Requires OPENAI_API_KEY on the backend.
              </p>
              <button
                onClick={generateCustomReport}
                disabled={!selectedDocId}
                className="mt-2 w-full px-4 py-2 rounded-lg bg-purple-500 hover:bg-purple-600 disabled:bg-slate-700 disabled:text-slate-400 text-white text-sm font-medium"
              >
                Generate AI Custom Report
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

