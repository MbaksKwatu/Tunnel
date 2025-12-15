'use client';

import { X, Share2, Link, Mail, Copy, Check } from 'lucide-react';
import { useState } from 'react';

interface ShareModalProps {
  title?: string;
  onClose: () => void;
}

export default function ShareModal({ title = 'Dashboard', onClose }: ShareModalProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyLink = () => {
    // In a real implementation, this would copy a shareable link
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-dark-card border border-slate-700 rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Share2 className="w-5 h-5 text-purple-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">Share {title}</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-700 rounded transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Content */}
        <div className="space-y-4">
          <p className="text-sm text-slate-400">
            Share this {title.toLowerCase()} with your team or stakeholders.
          </p>

          {/* Coming Soon Notice */}
          <div className="p-4 bg-slate-800/50 border border-slate-700 rounded-lg">
            <p className="text-sm text-slate-300 text-center">
              Sharing features coming soon!
            </p>
            <p className="text-xs text-slate-500 text-center mt-1">
              You'll be able to share via link, email, or export.
            </p>
          </div>

          {/* Share Options (disabled for now) */}
          <div className="space-y-2 opacity-50">
            <button
              onClick={handleCopyLink}
              className="w-full flex items-center gap-3 p-3 bg-slate-800 border border-slate-700 
                         rounded-lg hover:bg-slate-700 transition-colors"
            >
              {copied ? (
                <Check className="w-5 h-5 text-green-400" />
              ) : (
                <Link className="w-5 h-5 text-slate-400" />
              )}
              <span className="text-sm text-white">
                {copied ? 'Link copied!' : 'Copy link'}
              </span>
            </button>

            <button
              disabled
              className="w-full flex items-center gap-3 p-3 bg-slate-800 border border-slate-700 
                         rounded-lg cursor-not-allowed"
            >
              <Mail className="w-5 h-5 text-slate-400" />
              <span className="text-sm text-slate-400">Share via email</span>
            </button>

            <button
              disabled
              className="w-full flex items-center gap-3 p-3 bg-slate-800 border border-slate-700 
                         rounded-lg cursor-not-allowed"
            >
              <Copy className="w-5 h-5 text-slate-400" />
              <span className="text-sm text-slate-400">Export as PDF</span>
            </button>
          </div>
        </div>

        {/* Actions */}
        <div className="mt-6">
          <button
            onClick={onClose}
            className="w-full px-4 py-2.5 bg-slate-700 hover:bg-slate-600 
                       text-white rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
