'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, X, AlertCircle } from 'lucide-react';
import { uploadDocument } from '@/lib/v1-api';

interface BatchUploadProps {
  dealId: string;
  batchesUsed: number;
  /** Session counter for single-file uploads (increments in parent). When set, preferred over `batchesUsed` for the 4-upload cap. */
  localBatchesUsed?: number;
  onUploadComplete: () => void;
  onUploadSuccess?: (fileName: string) => void;
}

export function BatchUpload({
  dealId,
  batchesUsed,
  localBatchesUsed,
  onUploadComplete,
  onUploadSuccess,
}: BatchUploadProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const effectiveBatchesUsed = localBatchesUsed ?? batchesUsed;
  const uploadsRemaining = Math.max(0, 4 - effectiveBatchesUsed);
  const atLimit = uploadsRemaining <= 0;
  const canUpload = !atLimit;

  const applyPickedFiles = useCallback((files: File[]) => {
    if (files.length !== 1) {
      setError('Please select exactly 1 PDF');
      return;
    }

    const invalidFiles = files.filter((f) => !f.name.toLowerCase().endsWith('.pdf'));
    if (invalidFiles.length > 0) {
      setError('Only PDF files are supported');
      return;
    }

    setSelectedFiles(files);
    setError(null);
  }, []);

  const onDropBatch = useCallback(
    (accepted: File[]) => {
      if (accepted.length) applyPickedFiles(accepted);
    },
    [applyPickedFiles]
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: onDropBatch,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: uploading || atLimit,
    noClick: true,
    noKeyboard: true,
  });

  const handleUpload = async () => {
    if (selectedFiles.length !== 1) {
      setError('Select 1 PDF');
      return;
    }

    const uploaded = selectedFiles[0];

    setUploading(true);
    setProgress(10);
    setError(null);

    try {
      setProgress(30);
      await uploadDocument(dealId, uploaded);

      setProgress(100);
      setSelectedFiles([]);
      onUploadSuccess?.(uploaded.name);
      onUploadComplete();
    } catch (err: unknown) {
      console.error('Batch upload error:', err);
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      setTimeout(() => setProgress(0), 500);
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
            <p className="font-medium text-amber-100">Upload limit reached (4 of 4 used)</p>
            <p className="text-sm text-amber-200/80 mt-1">
              Use single-file upload above or contact support for more capacity.
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
            <p className="text-sm text-gray-400">Upload one monthly statement per upload (sequential)</p>
          </div>
          <div className="text-right shrink-0">
            <div className="text-2xl font-bold text-white">{uploadsRemaining}</div>
            <div className="text-xs text-gray-400">uploads remaining</div>
          </div>
        </div>

        {selectedFiles.length === 0 && (
          <div
            {...getRootProps({
              className: `border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragActive
                  ? 'border-blue-500 bg-blue-500/10'
                  : 'border-gray-600 hover:border-gray-500'
              }`,
            })}
          >
            <input {...getInputProps()} />
            <Upload className="h-12 w-12 mx-auto text-gray-500 mb-3" />
            <p className="text-sm text-gray-300 mb-2">
              <span className="font-medium text-white">Drop 1 PDF here</span>
              <span className="text-gray-500"> · </span>
              <button
                type="button"
                onClick={() => open()}
                disabled={uploading}
                className="text-sm font-medium text-blue-400 hover:underline disabled:opacity-50"
              >
                or click to select
              </button>
            </p>
            <p className="text-xs text-gray-500">e.g. April 2025 statement · upload one month at a time</p>
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
              {progress < 30 && 'Uploading…'}
              {progress >= 30 && progress < 100 && 'Sending to server…'}
              {progress >= 100 && 'Almost done…'}
            </p>
          </div>
        )}

        {error && (
          <div className="p-3 bg-red-950/40 border border-red-800 rounded-lg">
            <p className="text-sm text-red-200">{error}</p>
          </div>
        )}

        {selectedFiles.length > 0 && !uploading && (
          <div className="flex gap-3 flex-wrap">
            <button
              type="button"
              onClick={handleUpload}
              disabled={selectedFiles.length !== 1}
              className="flex-1 min-w-[12rem] px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded text-white text-sm font-medium inline-flex items-center justify-center gap-2"
            >
              <Upload className="h-4 w-4" />
              Upload &amp; process
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
