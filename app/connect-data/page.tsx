'use client';

import { motion } from 'framer-motion';
import { useState } from 'react';
import AppLayout from '@/components/Layout/AppLayout';
import FeatureCard from '@/components/FeatureCard';
import FileUpload from '@/components/FileUpload';
import DocumentList from '@/components/DocumentList';
import DataReview from '@/components/DataReview';
import { Upload, Database, Link as LinkIcon, FileText, Zap } from 'lucide-react';
import { Document } from '@/lib/supabase';
import { useRouter } from 'next/navigation';

export default function ConnectDataPage() {
  const router = useRouter();
  const userId = '12345678-1234-1234-1234-123456789abc';
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);

  const handleUploadComplete = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  const handleViewDocument = (document: Document) => {
    setSelectedDocument(document);
  };

  const handleCloseReview = () => {
    setSelectedDocument(null);
  };

  return (
    <AppLayout>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-3xl font-bold text-white mb-8">Connect Your Data</h1>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Left Column: Upload Methods */}
          <div className="space-y-6">
            {/* Upload File Card */}
            <FeatureCard
              icon={Upload}
              title="Upload File"
              description="Upload PDF, CSV, or XLSX files to extract and analyze financial data."
            >
              <FileUpload userId={userId} onUploadComplete={handleUploadComplete} />
            </FeatureCard>

            {/* Connect Database Card */}
            <FeatureCard
              icon={Database}
              title="Connect Database"
              description="Connect directly to your database to import financial data automatically."
              comingSoon
            />

            {/* Attach Link Card */}
            <FeatureCard
              icon={LinkIcon}
              title="Attach Link"
              description="Import data from external sources via API or web links."
              comingSoon
            />
          </div>

          {/* Right Column: Document List */}
          <div>
            <FeatureCard
              icon={Upload}
              title="Your Documents"
              description="View and manage your uploaded documents."
            >
              <DocumentList
                userId={userId}
                onViewDocument={handleViewDocument}
                refreshTrigger={refreshTrigger}
              />
            </FeatureCard>
          </div>
        </div>

        {/* Next Steps Section */}
        <div className="mt-8 border-t border-gray-800 pt-8">
          <h2 className="text-xl font-bold text-white mb-6">Next Steps</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div 
              onClick={() => router.push('/reports')}
              className="group p-6 bg-gray-900/50 border border-gray-800 hover:border-cyan-500/50 rounded-xl transition-all cursor-pointer"
            >
              <div className="flex items-center gap-4">
                <div className="p-3 bg-cyan-500/10 rounded-lg group-hover:bg-cyan-500/20 transition-colors">
                  <FileText className="w-6 h-6 text-cyan-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white mb-1">Generate Reports</h3>
                  <p className="text-sm text-gray-400">Create IC memos and AI-customized investment reports.</p>
                </div>
              </div>
            </div>

            <div 
              onClick={() => router.push('/actions')}
              className="group p-6 bg-gray-900/50 border border-gray-800 hover:border-green-500/50 rounded-xl transition-all cursor-pointer"
            >
              <div className="flex items-center gap-4">
                <div className="p-3 bg-green-500/10 rounded-lg group-hover:bg-green-500/20 transition-colors">
                  <Zap className="w-6 h-6 text-green-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white mb-1">Take Action</h3>
                  <p className="text-sm text-gray-400">Evaluate with AI Assistant or request missing reviews.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Data Review Modal */}
      {selectedDocument && (
        <DataReview document={selectedDocument} onClose={handleCloseReview} />
      )}
    </AppLayout>
  );
}

