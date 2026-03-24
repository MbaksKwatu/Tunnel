'use client';

import { useState } from 'react';
import { Upload, FileText, X, AlertCircle, CheckCircle } from 'lucide-react';
import { uploadDocumentsBatch } from '@/lib/v1-api';

interface BatchUploadProps {
  dealId: string;
  batchesUsed: number;
  onUploadComplete: () => void;
}

export function BatchUpload({ dealId, batchesUsed, onUploadComplete }: BatchUploadProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const batchesRemaining = Math.max(0, 4 - batchesUsed);
  const canUpload = batchesRemaining > 0;

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);

    if (files.length < 2) {
      setError('Please select at least 2 files');
      return;
    }

    if (files.length > 3) {
      setError('Maximum 3 files per batch');
      return;
    }

    const invalidFiles = files.filter((f) => !f.name.toLowerCase().endsWith('.pdf'));
    if (invalidFiles.length > 0) {
      setError('Only PDF files are supported');
      return;
    }

    setSelectedFiles(files);
    setError(null);
    setSuccess(false);
  };

  const handleUpload = async () => {
    if (selectedFiles.length < 2 || selectedFiles.length > 3) {
      setError('Select 2–3 files');
      return;
    }

    setUploading(true);
    setProgress(10);
    setError(null);
    setSuccess(false);

    try {
      setProgress(30);
      await uploadDocumentsBatch(dealId, selectedFiles);

      setProgress(100);
      setSuccess(true);

      setTimeout(() => {
        setSelectedFiles([]);
        setSuccess(false);
        onUploadComplete();
      }, 2000);
    } catch (err: unknown) {
      console.error('Batch upload error:', err);
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      setTimeout(() => setProgress(0), 1000);
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((files) => files.filter((_, i) => i !== index));
  };

  if (!canUpload) {
    return (
      <div className="rounded-lg border border-amber-700/50 bg-amber-950/40 p-6">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 shrink-0 text-amber-400 mt-0.5" />
          <div>
            <p className="font-medium text-amber-100">Batch upload limit reached</p>
            <p className="text-sm text-amber-200/80 mt-1">
              This deal has used all 4 batch uploads. Use single-file upload or contact support for
              more capacity.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-600 bg-gray-800/80 p-6">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="font-semibold text-lg text-white">Batch upload (PDF)</h3>
            <p className="text-sm text-gray-400">Upload 2–3 monthly statements at once (merged server-side)</p>
          </div>
          <div className="text-right shrink-0">
            <div className="text-2xl font-bold text-white">{batchesRemaining}</div>
            <div className="text-xs text-gray-400">of 4 batches left</div>
          </div>
        </div>

        {selectedFiles.length === 0 && !success && (
          <div className="border-2 border-dashed border-gray-600 rounded-lg p-8 text-center hover:border-gray-500 transition-colors">
            <Upload className="h-12 w-12 mx-auto text-gray-500 mb-3" />
            <label className="cursor-pointer">
              <span className="text-sm font-medium text-blue-400 hover:underline">
                Click to select 2–3 PDF files
              </span>
              <input
                type="file"
                multiple
                accept=".pdf,application/pdf"
                onChange={handleFileSelect}
                className="hidden"
                disabled={uploading}
              />
            </label>
            <p className="text-xs text-gray-500 mt-2">e.g. Jan, Feb, Mar statements</p>
          </div>
        )}

        {selectedFiles.length > 0 && (
          <div className="space-y-2">
            {selectedFiles.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="flex items-center gap-3 p-3 bg-gray-900/80 rounded-lg border border-gray-700"
              >
                <FileText className="h-5 w-5 shrink-0 text-gray-500" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-200 truncate">{file.name}</p>
                  <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(0)} KB</p>
                </div>
                {!uploading && (
                  <button
                    type="button"
                    onClick={() => removeFile(index)}
                    className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
                    aria-label="Remove file"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {uploading && (
          <div className="space-y-2">
            <div className="h-2 w-full bg-gray-900 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-sm text-center text-gray-400">
              {progress < 30 && 'Uploading files…'}
              {progress >= 30 && progress < 100 && 'Merging & processing…'}
              {progress >= 100 && 'Almost done…'}
            </p>
          </div>
        )}

        {success && (
          <div className="flex items-center gap-2 p-3 bg-green-950/50 border border-green-800 rounded-lg">
            <CheckCircle className="h-5 w-5 text-green-400 shrink-0" />
            <p className="text-sm text-green-100 font-medium">
              Batch uploaded successfully. Processing in the background…
            </p>
          </div>
        )}

        {error && (
          <div className="p-3 bg-red-950/40 border border-red-800 rounded-lg">
            <p className="text-sm text-red-200">{error}</p>
          </div>
        )}

        {selectedFiles.length > 0 && !uploading && !success && (
          <div className="flex gap-3 flex-wrap">
            <button
              type="button"
              onClick={handleUpload}
              disabled={selectedFiles.length < 2 || selectedFiles.length > 3}
              className="flex-1 min-w-[12rem] px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded text-white text-sm font-medium inline-flex items-center justify-center gap-2"
            >
              <Upload className="h-4 w-4" />
              Upload &amp; process {selectedFiles.length} files
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedFiles([]);
                setError(null);
              }}
              className="px-4 py-2 border border-gray-600 rounded text-gray-200 hover:bg-gray-700 text-sm"
            >
              Clear
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
