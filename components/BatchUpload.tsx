'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload } from 'lucide-react';

interface BatchUploadProps {
  dealId: string;
  onFileDrop: (file: File) => void;
}

export function BatchUpload({ dealId: _dealId, onFileDrop }: BatchUploadProps) {
  const [error, setError] = useState<string | null>(null);

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

    onFileDrop(files[0]);
    setError(null);
  }, [onFileDrop]);

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
    noClick: true,
    noKeyboard: true,
  });

  return (
    <div>
      <div
        {...getRootProps({
          className: `border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
            isDragActive ? 'border-blue-500 bg-blue-500/10' : 'border-gray-600 hover:border-gray-500'
          }`,
        })}
      >
        <input {...getInputProps()} />
        <Upload className="h-8 w-8 mx-auto text-gray-500 mb-3" />
        <p className="text-sm text-gray-300">
          <span className="font-medium text-white">Drop next statement here</span>
          <span className="text-gray-500"> · </span>
          <button
            type="button"
            onClick={() => open()}
            className="text-sm font-medium text-blue-400 hover:underline"
          >
            or click to select
          </button>
          <span className="text-gray-500"> · 1 PDF at once</span>
        </p>
        <p className="text-xs text-gray-500 mt-2">Upload one monthly statement per drop</p>
      </div>
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
    </div>
  );
}
