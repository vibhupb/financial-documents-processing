import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import { Upload as UploadIcon, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

interface UploadState {
  file: File | null;
  status: UploadStatus;
  progress: number;
  documentId: string | null;
  error: string | null;
}

export default function Upload() {
  const navigate = useNavigate();
  const [uploadState, setUploadState] = useState<UploadState>({
    file: null,
    status: 'idle',
    progress: 0,
    documentId: null,
    error: null,
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      // Step 1: Get presigned POST URL and fields
      setUploadState((prev) => ({ ...prev, progress: 25 }));
      const urlResponse = await api.createUploadUrl(file.name);

      // Step 2: Upload file to S3 using presigned POST
      setUploadState((prev) => ({ ...prev, progress: 50 }));
      await api.uploadFile(urlResponse.uploadUrl, urlResponse.fields, file);

      // Step 3: Complete
      setUploadState((prev) => ({ ...prev, progress: 100 }));
      return urlResponse;
    },
    onSuccess: (data) => {
      setUploadState((prev) => ({
        ...prev,
        status: 'success',
        documentId: data.documentId,
      }));
    },
    onError: (error: Error) => {
      setUploadState((prev) => ({
        ...prev,
        status: 'error',
        error: error.message,
      }));
    },
  });

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      setUploadState({
        file,
        status: 'uploading',
        progress: 0,
        documentId: null,
        error: null,
      });
      uploadMutation.mutate(file);
    }
  }, [uploadMutation]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024, // 50MB
    disabled: uploadState.status === 'uploading',
  });

  const resetUpload = () => {
    setUploadState({
      file: null,
      status: 'idle',
      progress: 0,
      documentId: null,
      error: null,
    });
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Document</h1>
        <p className="mt-1 text-gray-500">
          Upload a loan package PDF for processing
        </p>
      </div>

      {/* Upload Area */}
      <div className="card">
        {uploadState.status === 'idle' && (
          <div
            {...getRootProps()}
            className={clsx(
              'border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors',
              isDragActive
                ? 'border-primary-400 bg-primary-50'
                : 'border-gray-200 hover:border-primary-300 hover:bg-gray-50'
            )}
          >
            <input {...getInputProps()} />
            <div className="w-16 h-16 bg-primary-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <UploadIcon className="w-8 h-8 text-primary-600" />
            </div>
            <p className="text-lg font-medium text-gray-900">
              {isDragActive ? 'Drop your file here' : 'Drag & drop your PDF'}
            </p>
            <p className="mt-2 text-sm text-gray-500">
              or click to browse (max 50MB)
            </p>
          </div>
        )}

        {uploadState.status === 'uploading' && (
          <div className="text-center py-12">
            <Loader2 className="w-12 h-12 text-primary-600 animate-spin mx-auto mb-4" />
            <p className="text-lg font-medium text-gray-900">Uploading document...</p>
            <p className="mt-2 text-sm text-gray-500">{uploadState.file?.name}</p>
            <div className="mt-4 w-full max-w-xs mx-auto">
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary-600 transition-all duration-300"
                  style={{ width: `${uploadState.progress}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-gray-500">{uploadState.progress}%</p>
            </div>
          </div>
        )}

        {uploadState.status === 'success' && (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-10 h-10 text-green-600" />
            </div>
            <p className="text-lg font-medium text-gray-900">Upload successful!</p>
            <p className="mt-2 text-sm text-gray-500">
              Your document is being processed
            </p>
            <p className="mt-1 text-xs text-gray-400 font-mono">
              ID: {uploadState.documentId}
            </p>
            <div className="mt-6 flex justify-center gap-4">
              <button onClick={resetUpload} className="btn-secondary">
                Upload Another
              </button>
              <button
                onClick={() => navigate(`/documents/${uploadState.documentId}`)}
                className="btn-primary"
              >
                View Document
              </button>
            </div>
          </div>
        )}

        {uploadState.status === 'error' && (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertCircle className="w-10 h-10 text-red-600" />
            </div>
            <p className="text-lg font-medium text-gray-900">Upload failed</p>
            <p className="mt-2 text-sm text-red-500">{uploadState.error}</p>
            <button onClick={resetUpload} className="mt-6 btn-primary">
              Try Again
            </button>
          </div>
        )}
      </div>

      {/* Info Section */}
      <div className="card bg-blue-50 border-blue-100">
        <h3 className="font-medium text-blue-900 mb-2">Supported Documents</h3>
        <p className="text-sm text-blue-700">
          Upload mortgage loan packages containing:
        </p>
        <ul className="mt-2 space-y-1 text-sm text-blue-700">
          <li className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Promissory Note
          </li>
          <li className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Closing Disclosure (TILA-RESPA)
          </li>
          <li className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Form 1003 (Uniform Residential Loan Application)
          </li>
        </ul>
      </div>

      {/* Processing Info */}
      <div className="card">
        <h3 className="font-medium text-gray-900 mb-3">How Processing Works</h3>
        <div className="space-y-3">
          <ProcessStep
            step={1}
            title="Classification"
            description="Claude 3 Haiku identifies document types and key pages"
          />
          <ProcessStep
            step={2}
            title="Extraction"
            description="Amazon Textract extracts data from targeted pages only"
          />
          <ProcessStep
            step={3}
            title="Normalization"
            description="Claude 3.5 Sonnet normalizes and validates the data"
          />
        </div>
      </div>
    </div>
  );
}

function ProcessStep({
  step,
  title,
  description,
}: {
  step: number;
  title: string;
  description: string;
}) {
  return (
    <div className="flex gap-3">
      <div className="w-6 h-6 bg-primary-100 text-primary-600 rounded-full flex items-center justify-center text-sm font-medium flex-shrink-0">
        {step}
      </div>
      <div>
        <p className="font-medium text-gray-900">{title}</p>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
    </div>
  );
}
