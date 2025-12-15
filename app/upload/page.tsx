'use client';

import { useEffect, useState } from 'react';
import AppLayout from '@/components/Layout/AppLayout';
import FeatureCard from '@/components/FeatureCard';
import FileUpload from '@/components/FileUpload';
import DocumentList from '@/components/DocumentList';
import DataReview from '@/components/DataReview';
import { Upload } from 'lucide-react';
import { Document } from '@/lib/supabase';
import { getOrCreateParityUserId } from '@/lib/session';

export default function UploadPage() {
  const [userId, setUserId] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);

  useEffect(() => {
    setUserId(getOrCreateParityUserId());
  }, []);

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
      <div>
        <h1 className="text-3xl font-bold text-white mb-8">Upload</h1>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <FeatureCard
            icon={Upload}
            title="Upload File"
            description="Upload PDF or CSV files to extract and analyze financial data."
          >
            {userId && <FileUpload userId={userId} onUploadComplete={handleUploadComplete} />}
          </FeatureCard>

          <FeatureCard
            icon={Upload}
            title="Your Documents"
            description="View and manage your uploaded documents."
          >
            {userId && (
              <DocumentList
                userId={userId}
                onViewDocument={handleViewDocument}
                refreshTrigger={refreshTrigger}
              />
            )}
          </FeatureCard>
        </div>

        {selectedDocument && (
          <DataReview document={selectedDocument} onClose={handleCloseReview} />
        )}
      </div>
    </AppLayout>
  );
}
