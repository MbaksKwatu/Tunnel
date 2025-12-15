'use client';

import { useState } from 'react';
import { X, Building2, Check, Loader2 } from 'lucide-react';
import axios from 'axios';
import { API_URL } from '@/lib/api';

interface InvesteeConfirmModalProps {
  suggestedName: string;
  documentId: string;
  onConfirm: (name: string) => void;
  onCancel: () => void;
}

export default function InvesteeConfirmModal({
  suggestedName,
  documentId,
  onConfirm,
  onCancel
}: InvesteeConfirmModalProps) {
  const [investeeName, setInvesteeName] = useState(suggestedName);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    if (!investeeName.trim()) {
      setError('Please enter an investee name');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await axios.post(`${API_URL}/documents/${documentId}/set-investee`, {
        investee_name: investeeName.trim()
      });

      onConfirm(investeeName.trim());
    } catch (err: any) {
      console.error('Error setting investee name:', err);
      setError(err.response?.data?.detail || 'Failed to set investee name');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Modal */}
      <div className="relative bg-dark-card border border-slate-700 rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Building2 className="w-5 h-5 text-blue-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">Confirm Investee</h2>
          </div>
          <button
            onClick={onCancel}
            className="p-1 hover:bg-slate-700 rounded transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Content */}
        <div className="space-y-4">
          <p className="text-sm text-slate-400">
            We detected the following company name from your document.
            Please confirm or edit it.
          </p>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Investee / Company Name
            </label>
            <input
              type="text"
              value={investeeName}
              onChange={(e) => setInvesteeName(e.target.value)}
              className="w-full px-4 py-3 bg-slate-800 border border-slate-600 rounded-lg 
                         text-white placeholder-slate-500 focus:outline-none focus:ring-2 
                         focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder="Enter company name"
              autoFocus
            />
          </div>

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 mt-6">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 bg-slate-700 hover:bg-slate-600 
                       text-white rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isSubmitting || !investeeName.trim()}
            className="flex-1 px-4 py-2.5 bg-blue-500 hover:bg-blue-600 
                       text-white rounded-lg transition-colors flex items-center 
                       justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                Confirm
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
