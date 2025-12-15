'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import AppLayout from '@/components/Layout/AppLayout';
import { Mail, Send, Loader2, ArrowLeft, CheckCircle } from 'lucide-react';
import { useRouter } from 'next/navigation';
import axios from 'axios';

export default function RequestReviewPage() {
  const router = useRouter();
  const [missingInfo, setMissingInfo] = useState('');
  const [draft, setDraft] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [sent, setSent] = useState(false);

  const handleGenerate = async () => {
    if (!missingInfo.trim()) return;
    setIsGenerating(true);
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL;
      const response = await axios.post(`${API_BASE}/draft-review-email`, {
        missing_info: missingInfo
      });
      setDraft(response.data.email);
    } catch (error) {
      console.error("Failed to generate draft", error);
      setDraft("Error generating draft. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSend = async () => {
    setIsSending(true);
    // Mock send
    await new Promise(resolve => setTimeout(resolve, 1500));
    setIsSending(false);
    setSent(true);
    setTimeout(() => {
      router.push('/dashboard');
    }, 2000);
  };

  return (
    <AppLayout>
      <div className="p-8 max-w-4xl mx-auto">
        <button
          onClick={() => router.back()}
          className="flex items-center text-gray-400 hover:text-white mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-2" /> Back
        </button>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex items-center gap-4 mb-8">
            <div className="p-3 bg-purple-500/10 rounded-xl">
              <Mail className="w-8 h-8 text-purple-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white">Request Review</h1>
              <p className="text-gray-400">Draft and send formal document requests to portfolio companies.</p>
            </div>
          </div>

          {!sent ? (
            <div className="grid gap-8">
              {/* Step 1: Input */}
              <div className="bg-[#1B1E23] border border-gray-700 rounded-xl p-6">
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  What information is missing?
                </label>
                <textarea
                  value={missingInfo}
                  onChange={(e) => setMissingInfo(e.target.value)}
                  placeholder="e.g., Missing Q3 bank statements, clarification on legal fees, updated cap table..."
                  className="w-full h-32 bg-gray-900 border border-gray-700 rounded-lg p-4 text-white focus:outline-none focus:border-purple-500 transition-colors resize-none"
                />
                <div className="mt-4 flex justify-end">
                  <button
                    onClick={handleGenerate}
                    disabled={isGenerating || !missingInfo.trim()}
                    className="flex items-center gap-2 px-6 py-2 bg-purple-500 hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-all"
                  >
                    {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    {isGenerating ? 'Drafting...' : 'Generate Draft'}
                  </button>
                </div>
              </div>

              {/* Step 2: Preview & Edit */}
              {draft && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-[#1B1E23] border border-gray-700 rounded-xl p-6"
                >
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Email Draft (Editable)
                  </label>
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    className="w-full h-64 bg-gray-900 border border-gray-700 rounded-lg p-4 text-gray-300 font-mono text-sm focus:outline-none focus:border-purple-500 transition-colors resize-none"
                  />
                  <div className="mt-4 flex justify-end gap-4">
                    <button
                      onClick={() => setDraft('')}
                      className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
                    >
                      Discard
                    </button>
                    <button
                      onClick={handleSend}
                      disabled={isSending}
                      className="flex items-center gap-2 px-6 py-2 bg-green-500 hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold rounded-lg transition-all"
                    >
                      {isSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                      {isSending ? 'Sending...' : 'Send Request'}
                    </button>
                  </div>
                </motion.div>
              )}
            </div>
          ) : (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center justify-center py-20 text-center"
            >
              <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mb-6">
                <CheckCircle className="w-10 h-10 text-green-400" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">Request Sent Successfully</h2>
              <p className="text-gray-400 mb-8">The email has been delivered to the portfolio company contact.</p>
              <button
                onClick={() => router.push('/dashboard')}
                className="px-6 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors"
              >
                Return to Dashboard
              </button>
            </motion.div>
          )}

        </motion.div>
      </div>
    </AppLayout>
  );
}
