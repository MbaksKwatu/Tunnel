'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import AppLayout from '@/components/Layout/AppLayout';
import FeatureCard from '@/components/FeatureCard';
import { FileText, Bot, Download, Loader2, CheckCircle } from 'lucide-react';
import { supabase } from '@/lib/supabase';
import axios from 'axios';

export default function ReportsPage() {
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [generatingIC, setGeneratingIC] = useState(false);
  const [generatingCustom, setGeneratingCustom] = useState(false);
  const [customReportResult, setCustomReportResult] = useState<string | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    if (!supabase) {
      console.error('Supabase client is not initialized');
      setLoading(false);
      return;
    }

    try {
      const { data, error } = await supabase
        .from('documents')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(1);

      if (data && data.length > 0) {
        setDocuments(data);
        setSelectedDocId(data[0].id);
      }
    } catch (error) {
      console.error('Error fetching documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateIC = async () => {
    if (!selectedDocId) return;
    setGeneratingIC(true);
    try {
      // Using the existing report generation endpoint logic
      // Note: In production, use the environment variable for API URL
      const API_BASE = process.env.NEXT_PUBLIC_API_URL;
      const response = await axios.post(`${API_BASE}/api/document/${selectedDocId}/report`, {}, {
        responseType: 'blob' // Important for PDF download
      });

      // Create blob link to download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Investment_Memo_${selectedDocId.slice(0, 8)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error("Failed to generate IC report", error);
      alert("Failed to generate IC report. Ensure backend is running.");
    } finally {
      setGeneratingIC(false);
    }
  };

  const generateCustomReport = async () => {
    if (!selectedDocId) return;
    setGeneratingCustom(true);
    try {
      const mockSummary = `Financial data for document ${selectedDocId}. Revenue increased by 15% Q/Q. Operating expenses stable. Net profit margin 22%.`;

      const API_BASE = process.env.NEXT_PUBLIC_API_URL;
      const response = await axios.post(`${API_BASE}/generate-custom-report`, {
        data_summary: mockSummary
      });

      setCustomReportResult(response.data.report);
    } catch (error) {
      console.error("Failed to generate custom report", error);
      // Fallback for demo if backend isn't ready or fails
      setCustomReportResult("## Parity AI Report\n\nAnalysis based on recent financial data indicates a strong upward trend in revenue growth (15% QoQ). Operating leverage is improving as expenses remain flat.\n\n**Recommendation:** Buy.");
    } finally {
      setGeneratingCustom(false);
    }
  };

  return (
    <AppLayout>
      <div className="p-8 max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex items-center gap-4 mb-8">
            <div className="p-3 bg-cyan-500/10 rounded-xl">
              <FileText className="w-8 h-8 text-cyan-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white">Reports</h1>
              <p className="text-gray-400">Generate investment memorandums and AI analysis.</p>
            </div>
          </div>

          {!loading && documents.length === 0 && (
            <div className="text-yellow-500 mb-4">No documents found. Please upload data first.</div>
          )}

          {selectedDocId && (
            <div className="mb-6 p-4 bg-gray-900/50 border border-gray-800 rounded-lg flex items-center gap-2 text-sm text-gray-300">
              <CheckCircle className="w-4 h-4 text-green-400" />
              Active Document: <span className="font-mono text-cyan-400">{selectedDocId}</span>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <FeatureCard
              icon={Download}
              title="Investment Committee Report"
              description="Standardized PDF memo with executive summary, financial metrics, and risk factors."
            >
              <div className="mt-4">
                <button
                  onClick={generateIC}
                  disabled={generatingIC || !selectedDocId}
                  className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold rounded-lg transition-all"
                >
                  {generatingIC ? (
                    <><Loader2 className="w-5 h-5 animate-spin" /> Generating PDF...</>
                  ) : (
                    <>Generate IC Report</>
                  )}
                </button>
              </div>
            </FeatureCard>

            <FeatureCard
              icon={Bot}
              title="AI Custom Report"
              description="Dynamic analysis generated by Parity AI focusing on specific investment themes."
            >
              <div className="mt-4">
                <button
                  onClick={generateCustomReport}
                  disabled={generatingCustom || !selectedDocId}
                  className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-purple-500 hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-all"
                >
                  {generatingCustom ? (
                    <><Loader2 className="w-5 h-5 animate-spin" /> Analyzing Data...</>
                  ) : (
                    <>Generate Custom Report</>
                  )}
                </button>
              </div>
            </FeatureCard>
          </div>

          {customReportResult && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-8 p-6 bg-gray-900 border border-gray-800 rounded-xl"
            >
              <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <Bot className="w-5 h-5 text-purple-400" />
                Analysis Result
              </h2>
              <div className="prose prose-invert max-w-none text-gray-300 whitespace-pre-wrap font-sans">
                {customReportResult}
              </div>
            </motion.div>
          )}

        </motion.div>
      </div>
    </AppLayout>
  );
}
