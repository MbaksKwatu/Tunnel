'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File, CheckCircle, XCircle, Loader2, Lock, Unlock, RotateCcw, X } from 'lucide-react';
import { isLocalMode } from '@/lib/supabase';
import { FileType, UploadProgress } from '@/lib/types';
import { API_URL } from '@/lib/api';

interface FileUploadProps {
  userId: string;
  onUploadComplete?: () => void;
}

// Extended upload progress to include document info
interface ExtendedUploadProgress extends UploadProgress {
  documentId?: string;
  investeeNameSuggested?: string;
  investeeConfirmed?: boolean;
}

export default function FileUpload({ userId, onUploadComplete }: FileUploadProps) {
  const [uploads, setUploads] = useState<ExtendedUploadProgress[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  // Password handling state
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordInput, setPasswordInput] = useState('');
  const [fileToRetry, setFileToRetry] = useState<File | null>(null);

  const getFileType = (file: File): FileType | null => {
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (extension === 'pdf') return 'pdf';
    if (extension === 'csv') return 'csv';
    return null;
  };

  const processFile = async (file: File, password?: string) => {
    const fileType = getFileType(file);

    if (!fileType) {
      throw new Error('Unsupported file type. Please upload PDF or CSV files.');
    }

    // Local-first mode: upload to backend and process asynchronously
    if (isLocalMode) {
      // Update progress: uploading
      setUploads(prev => prev.map(u =>
        u.fileName === file.name ? { ...u, status: 'uploading', progress: 20, error: undefined } : u
      ));

      const formData = new FormData();
      formData.append('file', file);
      formData.append('session_id', userId);
      if (password) {
        formData.append('password', password);
      }

      try {
        setUploads(prev => prev.map(u =>
          u.fileName === file.name ? { ...u, status: 'processing', progress: 40 } : u
        ));

        const uploadRes = await fetch(`${API_URL}/documents/upload`, {
          method: 'POST',
          body: formData
        });

        const uploadJson = await uploadRes.json().catch(() => ({}));
        if (!uploadRes.ok) {
          const msg = String(uploadJson?.detail || uploadJson?.error || 'Upload failed');
          throw new Error(msg);
        }

        const docId = String(uploadJson.document_id || '');
        if (!docId) {
          throw new Error('Upload failed: missing document_id');
        }

        setUploads(prev => prev.map(u =>
          u.fileName === file.name ? { ...u, status: 'processing', progress: 60, documentId: docId } : u
        ));

        const start = Date.now();
        const maxMs = 120_000;
        const pollEveryMs = 3_000;

        while (Date.now() - start < maxMs) {
          await new Promise(r => setTimeout(r, pollEveryMs));

          const statusRes = await fetch(`${API_URL}/documents/${docId}/status`);
          const statusJson = await statusRes.json().catch(() => ({}));
          const status = String(statusJson.status || '').toLowerCase();
          const errMsg = String(statusJson.error_message || '');
          const errCode = String(statusJson.error_code || '');
          const nextAction = String(statusJson.next_action || '');

          if (status === 'completed') {
            setUploads(prev => prev.map(u =>
              u.fileName === file.name ? { ...u, status: 'completed', progress: 100, documentId: docId } : u
            ));
            if (onUploadComplete) onUploadComplete();
            return;
          }

          if (status === 'failed') {
            const token = errCode || errMsg;
            const normalized = token === 'PASSWORD_REQUIRED' ? 'PASSWORD_REQUIRED' : (token || 'Processing failed');
            setUploads(prev => prev.map(u =>
              u.fileName === file.name ? { ...u, status: 'error', error: normalized, progress: 0, documentId: docId } : u
            ));
            return;
          }

          if (status === 'partial') {
            const token = errCode || errMsg;
            const normalized = token === 'PASSWORD_REQUIRED' ? 'PASSWORD_REQUIRED' : (token || nextAction || 'Partial success');
            setUploads(prev => prev.map(u =>
              u.fileName === file.name ? { ...u, status: 'error', error: normalized, progress: 0, documentId: docId } : u
            ));
            return;
          }

          setUploads(prev => prev.map(u =>
            u.fileName === file.name ? { ...u, status: 'processing', progress: 75, documentId: docId } : u
          ));
        }

        setUploads(prev => prev.map(u =>
          u.fileName === file.name ? { ...u, status: 'error', error: 'Processing timed out. Please retry.', progress: 0, documentId: docId } : u
        ));
      } catch (error: any) {
        const errorMessage = (error.message || 'Unknown error');

        setUploads(prev => prev.map(u =>
          u.fileName === file.name ? { ...u, status: 'error', error: errorMessage, progress: 0 } : u
        ));
      }
      return;
    }

    throw new Error('Upload is only supported via the backend API.');
  };

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setIsUploading(true);

    // Initialize upload progress for all files
    const newUploads: UploadProgress[] = acceptedFiles.map(file => ({
      fileName: file.name,
      progress: 0,
      status: 'uploading'
    }));
    setUploads(prev => [...prev, ...newUploads]);

    // Process files sequentially
    for (const file of acceptedFiles) {
      // Store file in a map or just pass it down? 
      // We can't easily store File objects in state if we want to retry later without re-selecting
      // But for now, retry logic will need the file object.
      // We'll assume the user handles one batch at a time or we store it if needed.
      // Actually, we can attach the File object to the upload state if we wanted, but UploadProgress is serializable usually.
      // For the retry to work, we need access to the File object.
      // We can add a custom property to the state component locally or just find it from acceptedFiles if scope allows.
      // Since we need to support retry later, we'll need to store it.
      // Let's just process.
      try {
        await processFile(file);
      } catch {
        // errors are handled per-file in state
      }
    }

    setIsUploading(false);

    // Clear completed uploads after 5 seconds (keep errors for retry)
    setTimeout(() => {
      setUploads(prev => prev.filter(u => u.status === 'uploading' || u.status === 'processing' || u.status === 'error'));
    }, 5000);
  }, [userId, onUploadComplete]);

  // Need to keep track of files for retry
  const [filesMap, setFilesMap] = useState<Map<string, File>>(new Map());

  // Intercept onDrop to store files
  const onDropWithStorage = useCallback((acceptedFiles: File[]) => {
    setFilesMap(prev => {
      const newMap = new Map(prev);
      acceptedFiles.forEach(f => newMap.set(f.name, f));
      return newMap;
    });
    onDrop(acceptedFiles);
  }, [onDrop]);

  const handleRetryWithPassword = (fileName: string) => {
    const file = filesMap.get(fileName);
    if (file) {
      setFileToRetry(file);
      setPasswordInput('');
      setShowPasswordModal(true);
    }
  };

  const handleRetry = (fileName: string) => {
    const file = filesMap.get(fileName);
    if (file) {
      processFile(file);
    }
  };

  const handleDismiss = (fileName: string) => {
    setUploads(prev => prev.filter(u => u.fileName !== fileName));
  };

  const handlePasswordSubmit = async () => {
    if (fileToRetry && passwordInput) {
      setShowPasswordModal(false);
      try {
        await processFile(fileToRetry, passwordInput);
        // Refresh
        if (onUploadComplete) onUploadComplete();
      } catch (e) {
        console.error("Retry failed", e);
      }
      setFileToRetry(null);
      setPasswordInput('');
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: onDropWithStorage,
    accept: {
      'application/pdf': ['.pdf'],
      'text/csv': ['.csv']
    },
    disabled: isUploading
  });

  return (
    <div className="w-full relative">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-12 text-center cursor-pointer
          transition-colors duration-200
          ${isDragActive
            ? 'border-accent-cyan bg-accent-cyan/10'
            : 'border-gray-600 hover:border-accent-cyan bg-base-900 shadow-inner-dark'
          }
          ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
        {isDragActive ? (
          <p className="text-lg text-accent-cyan">Drop the files here...</p>
        ) : (
          <>
            <p className="text-lg text-gray-700 mb-2">
              Drag & drop files here, or click to select
            </p>
            <p className="text-sm text-gray-500">
              Supports: PDF, CSV (Excel coming soon)
            </p>
          </>
        )}
      </div>

      {/* Upload Progress */}
      {uploads.length > 0 && (
        <div className="mt-6 space-y-3">
          <h3 className="text-sm font-semibold text-gray-300">Upload Progress</h3>
          {uploads.map((upload, index) => (
            <div key={index} className="bg-base-900 shadow-inner-dark border border-gray-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-3">
                  <File className="h-5 w-5 text-gray-400" />
                  <span className="text-sm font-medium text-gray-200">
                    {upload.fileName}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  {upload.error === 'PASSWORD_REQUIRED' ? (
                    <button
                      onClick={() => handleRetryWithPassword(upload.fileName)}
                      className="flex items-center space-x-1 px-3 py-1 rounded bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 transition-colors text-xs font-medium border border-yellow-500/50"
                    >
                      <Lock className="h-3 w-3" />
                      <span>Unlock</span>
                    </button>
                  ) : null}

                  {upload.status === 'error' && upload.error !== 'PASSWORD_REQUIRED' ? (
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleRetry(upload.fileName)}
                        className="p-1.5 rounded-full bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-white transition-colors"
                        title="Retry"
                      >
                        <RotateCcw className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDismiss(upload.fileName)}
                        className="p-1.5 rounded-full hover:bg-gray-700 text-gray-500 hover:text-red-400 transition-colors"
                        title="Dismiss"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ) : null}

                  {upload.status === 'uploading' && (
                    <Loader2 className="h-5 w-5 text-accent-cyan animate-spin" />
                  )}
                  {upload.status === 'processing' && (
                    <Loader2 className="h-5 w-5 text-accent-indigo animate-spin" />
                  )}
                  {upload.status === 'completed' && (
                    <CheckCircle className="h-5 w-5 text-green-400" />
                  )}
                </div>
              </div>

              {/* Progress Bar */}
              {(upload.status === 'uploading' || upload.status === 'processing') && (
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-accent-cyan to-accent-indigo h-2 rounded-full transition-all duration-300"
                    style={{ width: `${upload.progress}%` }}
                  />
                </div>
              )}

              {/* Status Text */}
              <div className="mt-2">
                {upload.status === 'uploading' && (
                  <p className="text-xs text-gray-400">Uploading...</p>
                )}
                {upload.status === 'processing' && (
                  <p className="text-xs text-accent-indigo">Extracting data...</p>
                )}
                {upload.status === 'completed' && (
                  <div className="space-y-2">
                    <p className="text-xs text-green-400">
                      Completed successfully!
                    </p>
                  </div>
                )}
                {upload.status === 'error' && (
                  upload.error === 'PASSWORD_REQUIRED' ? (
                    <p className="text-xs text-yellow-400 font-medium">Password required to decrypt file.</p>
                  ) : (
                    <p className="text-xs text-red-400 flex items-center">
                      <XCircle className="h-3 w-3 mr-1" />
                      {upload.error}
                    </p>
                  )
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Password Modal */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-base-900 border border-gray-800 rounded-xl p-6 w-full max-w-md shadow-2xl shadow-inner-dark">
            <div className="flex items-center space-x-3 mb-4 text-yellow-400">
              <Lock className="h-6 w-6" />
              <h3 className="text-xl font-bold text-white">Password Required</h3>
            </div>

            <p className="text-gray-300 mb-6">
              The file <span className="font-mono text-accent-cyan">{fileToRetry?.name}</span> is encrypted.
              Please enter the password to continue.
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 uppercase mb-1">Password</label>
                <input
                  type="password"
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  className="w-full bg-base-950 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-accent-cyan transition-colors"
                  placeholder="Enter document password"
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handlePasswordSubmit()}
                />
              </div>

              <div className="flex space-x-3 pt-2">
                <button
                  onClick={() => {
                    setShowPasswordModal(false);
                    setFileToRetry(null);
                    setPasswordInput('');
                  }}
                  className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={handlePasswordSubmit}
                  disabled={!passwordInput}
                  className="flex-1 px-4 py-2 bg-gradient-to-r from-accent-cyan to-accent-indigo hover:from-accent-cyan hover:to-accent-indigo text-white rounded-lg transition-all font-bold shadow-lg shadow-glow-cyan disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                >
                  <Unlock className="h-4 w-4" />
                  <span>Unlock & Process</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}


