'use client';

import { useState, useEffect } from 'react';
import { getDocuments } from '@/lib/supabase';

export default function DebugPage() {
  const [status, setStatus] = useState<string>('Loading...');
  const [documents, setDocuments] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const testConnection = async () => {
      try {
        setStatus('Testing Supabase connection...');
        
        // Test with demo user ID
        const userId = '12345678-1234-1234-1234-123456789abc';
        const docs = await getDocuments(userId);
        
        setDocuments(docs);
        setStatus(`✅ Connected! Found ${docs.length} documents`);
      } catch (err: any) {
        setError(err.message);
        setStatus(`❌ Error: ${err.message}`);
        console.error('Debug error:', err);
      }
    };

    testConnection();
  }, []);

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">FundIQ Debug Page</h1>
        
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Connection Status</h2>
          <p className="text-lg">{status}</p>
          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded">
              <p className="text-red-800 font-mono text-sm">{error}</p>
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Documents Found</h2>
          <pre className="bg-gray-100 p-4 rounded text-sm overflow-auto">
            {JSON.stringify(documents, null, 2)}
          </pre>
        </div>

        <div className="mt-6">
          <a 
            href="/" 
            className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
          >
            ← Back to Main App
          </a>
        </div>
      </div>
    </div>
  );
}

