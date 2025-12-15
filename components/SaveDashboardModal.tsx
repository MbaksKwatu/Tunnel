'use client';

import { useState } from 'react';
import { X, Save, Loader2, LayoutDashboard } from 'lucide-react';
import axios from 'axios';

interface SaveDashboardModalProps {
  investeeName: string;
  dashboardSpec: any;
  onSave: (dashboardId: string) => void;
  onCancel: () => void;
}

export default function SaveDashboardModal({
  investeeName,
  dashboardSpec,
  onSave,
  onCancel
}: SaveDashboardModalProps) {
  const [dashboardName, setDashboardName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!dashboardName.trim()) {
      setError('Please enter a dashboard name');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL;
      const response = await axios.post(`${apiUrl}/dashboards/save`, {
        investee_name: investeeName,
        dashboard_name: dashboardName.trim(),
        spec: dashboardSpec
      });

      onSave(response.data.dashboard_id);
    } catch (err: any) {
      console.error('Error saving dashboard:', err);
      setError(err.response?.data?.detail || 'Failed to save dashboard');
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
            <div className="p-2 bg-green-500/20 rounded-lg">
              <LayoutDashboard className="w-5 h-5 text-green-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">Save Dashboard</h2>
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
            Save this dashboard configuration for <span className="text-white font-medium">{investeeName}</span>
          </p>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Dashboard Name
            </label>
            <input
              type="text"
              value={dashboardName}
              onChange={(e) => setDashboardName(e.target.value)}
              className="w-full px-4 py-3 bg-slate-800 border border-slate-600 rounded-lg 
                         text-white placeholder-slate-500 focus:outline-none focus:ring-2 
                         focus:ring-green-500 focus:border-transparent transition-all"
              placeholder="e.g., Q4 Financial Overview"
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
            onClick={handleSave}
            disabled={isSubmitting || !dashboardName.trim()}
            className="flex-1 px-4 py-2.5 bg-green-500 hover:bg-green-600 
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
                <Save className="w-4 h-4" />
                Save Dashboard
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
