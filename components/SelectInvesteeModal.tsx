'use client';

import { useState, useEffect } from 'react';
import { X, Search, Building2, Loader2, ChevronRight, Calendar } from 'lucide-react';
import axios from 'axios';
import { API_URL } from '@/lib/api';

interface Investee {
  investee_name: string;
  last_uploaded: string;
}

interface SelectInvesteeModalProps {
  onSelect: (investeeName: string, context: any) => void;
  onCancel: () => void;
}

export default function SelectInvesteeModal({
  onSelect,
  onCancel
}: SelectInvesteeModalProps) {
  const [investees, setInvestees] = useState<Investee[]>([]);
  const [filteredInvestees, setFilteredInvestees] = useState<Investee[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingContext, setIsLoadingContext] = useState(false);
  const [selectedInvestee, setSelectedInvestee] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = API_URL;

  useEffect(() => {
    fetchInvestees();
  }, []);

  useEffect(() => {
    if (searchQuery.trim()) {
      const filtered = investees.filter(inv =>
        inv.investee_name.toLowerCase().includes(searchQuery.toLowerCase())
      );
      setFilteredInvestees(filtered);
    } else {
      setFilteredInvestees(investees);
    }
  }, [searchQuery, investees]);

  const fetchInvestees = async () => {
    try {
      const response = await axios.get(`${apiUrl}/investees`);
      setInvestees(response.data);
      setFilteredInvestees(response.data);
    } catch (err: any) {
      console.error('Error fetching investees:', err);
      setError('Failed to load investees');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectInvestee = async (investeeName: string) => {
    setSelectedInvestee(investeeName);
    setIsLoadingContext(true);
    setError(null);

    try {
      const response = await axios.get(`${apiUrl}/investees/${encodeURIComponent(investeeName)}/full`);
      onSelect(investeeName, response.data);
    } catch (err: any) {
      console.error('Error fetching investee context:', err);
      setError('Failed to load investee data');
      setSelectedInvestee(null);
    } finally {
      setIsLoadingContext(false);
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      });
    } catch {
      return dateString;
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
      <div className="relative bg-dark-card border border-slate-700 rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Building2 className="w-5 h-5 text-blue-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">Select Investee</h2>
          </div>
          <button
            onClick={onCancel}
            className="p-1 hover:bg-slate-700 rounded transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Search */}
        <div className="p-4 border-b border-slate-700">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-slate-800 border border-slate-600 rounded-lg 
                         text-white placeholder-slate-500 focus:outline-none focus:ring-2 
                         focus:ring-blue-500 focus:border-transparent"
              placeholder="Search investees..."
              autoFocus
            />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
            </div>
          ) : error && !investees.length ? (
            <div className="text-center py-12">
              <p className="text-red-400">{error}</p>
            </div>
          ) : filteredInvestees.length === 0 ? (
            <div className="text-center py-12">
              <Building2 className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">
                {searchQuery ? 'No investees match your search' : 'No investees found'}
              </p>
              <p className="text-sm text-slate-500 mt-1">
                Upload a document to create an investee
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredInvestees.map((investee) => (
                <button
                  key={investee.investee_name}
                  onClick={() => handleSelectInvestee(investee.investee_name)}
                  disabled={isLoadingContext}
                  className={`w-full flex items-center justify-between p-4 rounded-lg border 
                             transition-all text-left group
                             ${selectedInvestee === investee.investee_name
                      ? 'bg-blue-500/20 border-blue-500'
                      : 'bg-slate-800/50 border-slate-700 hover:bg-slate-800 hover:border-slate-600'
                    }
                             disabled:opacity-50`}
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-slate-700 rounded-lg group-hover:bg-slate-600 transition-colors">
                      <Building2 className="w-4 h-4 text-slate-300" />
                    </div>
                    <div>
                      <p className="font-medium text-white">{investee.investee_name}</p>
                      <div className="flex items-center gap-1 text-xs text-slate-500 mt-0.5">
                        <Calendar className="w-3 h-3" />
                        <span>Last updated: {formatDate(investee.last_uploaded)}</span>
                      </div>
                    </div>
                  </div>

                  {selectedInvestee === investee.investee_name && isLoadingContext ? (
                    <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-slate-500 group-hover:text-slate-300 transition-colors" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-700">
          <button
            onClick={onCancel}
            className="w-full px-4 py-2.5 bg-slate-700 hover:bg-slate-600 
                       text-white rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
