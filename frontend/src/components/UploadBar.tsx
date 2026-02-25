import { useState, useCallback, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import { Upload, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';

type UploadBarStatus = 'idle' | 'uploading' | 'success' | 'error';

export default function UploadBar() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<UploadBarStatus>('idle');
  const [fileName, setFileName] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Auto-reset to idle after success (3s) or error (5s)
  useEffect(() => {
    if (status === 'success') {
      const timer = setTimeout(() => {
        setStatus('idle');
        setFileName(null);
      }, 3000);
      return () => clearTimeout(timer);
    }
    if (status === 'error') {
      const timer = setTimeout(() => {
        setStatus('idle');
        setFileName(null);
        setErrorMessage(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [status]);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const urlResponse = await api.createUploadUrl(file.name);
      await api.uploadFile(urlResponse.uploadUrl, urlResponse.fields, file);
      return urlResponse;
    },
    onSuccess: () => {
      setStatus('success');
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['metrics'] });
    },
    onError: (error: Error) => {
      setStatus('error');
      setErrorMessage(error.message);
    },
  });

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (file) {
        setFileName(file.name);
        setStatus('uploading');
        setErrorMessage(null);
        uploadMutation.mutate(file);
      }
    },
    [uploadMutation]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
    disabled: status === 'uploading',
  });

  return (
    <div
      {...getRootProps()}
      className={clsx(
        'flex items-center gap-3 px-4 py-2.5 rounded-lg border transition-colors cursor-pointer',
        status === 'idle' && !isDragActive && 'border-gray-200 bg-white hover:border-primary-300 hover:bg-gray-50',
        status === 'idle' && isDragActive && 'border-primary-400 bg-primary-50',
        status === 'uploading' && 'border-primary-200 bg-primary-50 cursor-wait',
        status === 'success' && 'border-green-300 bg-green-50',
        status === 'error' && 'border-red-300 bg-red-50'
      )}
    >
      <input {...getInputProps()} />

      {status === 'idle' && (
        <>
          <Upload className="w-4 h-4 text-gray-400 flex-shrink-0" />
          <span className="text-sm text-gray-500">
            {isDragActive ? 'Drop PDF here' : 'Drop a PDF here or click to upload'}
          </span>
        </>
      )}

      {status === 'uploading' && (
        <>
          <Loader2 className="w-4 h-4 text-primary-600 animate-spin flex-shrink-0" />
          <span className="text-sm text-primary-700">
            Uploading {fileName}...
          </span>
        </>
      )}

      {status === 'success' && (
        <>
          <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
          <span className="text-sm text-green-700">
            {fileName} uploaded successfully
          </span>
        </>
      )}

      {status === 'error' && (
        <>
          <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
          <span className="text-sm text-red-700">
            Upload failed{errorMessage ? `: ${errorMessage}` : ''}
          </span>
        </>
      )}
    </div>
  );
}
