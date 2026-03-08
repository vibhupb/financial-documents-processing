import { useState, useCallback, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import { Upload, CheckCircle, AlertCircle, Loader2, X } from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';
import { optimisticUploads } from '../services/optimistic-uploads';
import type { Document } from '../types';

type UploadBarStatus = 'idle' | 'uploading' | 'success' | 'error';
type ProcessingMode = 'extract' | 'understand' | 'both';

export default function UploadBar() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<UploadBarStatus>('idle');
  const [fileName, setFileName] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Dialog state
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [dialogMode, setDialogMode] = useState<ProcessingMode>('extract');
  const [dialogBaselines, setDialogBaselines] = useState<string[]>([]);
  const [dialogPluginId, setDialogPluginId] = useState<string>('');

  // Fetch published compliance baselines
  const { data: baselinesData } = useQuery({
    queryKey: ['baselines', 'published'],
    queryFn: () => api.listBaselines({ status: 'published' }),
  });

  // Fetch registered plugins
  const { data: pluginsData } = useQuery({
    queryKey: ['plugins'],
    queryFn: () => api.getPlugins(),
  });

  const publishedBaselines = baselinesData?.baselines || [];
  const pluginList = pluginsData?.plugins ? Object.keys(pluginsData.plugins) : [];

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
    mutationFn: async ({ file, mode, baselineIds, pluginId }: {
      file: File;
      mode: ProcessingMode;
      baselineIds: string[];
      pluginId?: string;
    }) => {
      const urlResponse = await api.createUploadUrl(
        file.name,
        mode,
        baselineIds.length > 0 ? baselineIds : undefined,
        pluginId || undefined
      );
      await api.uploadFile(urlResponse.uploadUrl, urlResponse.fields, file);
      return urlResponse;
    },
    onSuccess: (data, { file }) => {
      setStatus('success');

      const placeholder: Document = {
        documentId: data.documentId,
        documentType: '' as Document['documentType'],
        status: 'PENDING',
        createdAt: new Date().toISOString(),
        fileName: file.name,
        latestEvent: {
          ts: new Date().toISOString(),
          stage: 'trigger',
          message: 'Waiting for processing pipeline...',
        },
      };

      optimisticUploads.add(placeholder);

      queryClient.setQueriesData<{ documents: Document[]; count: number }>(
        { queryKey: ['documents'] },
        (old) => {
          if (!old) return { documents: [placeholder], count: 1 };
          if (old.documents.some((d) => d.documentId === placeholder.documentId)) return old;
          return { ...old, documents: [placeholder, ...old.documents], count: old.count + 1 };
        }
      );

      queryClient.invalidateQueries({ queryKey: ['metrics'] });
    },
    onError: (error: Error) => {
      setStatus('error');
      setErrorMessage(error.message);
    },
  });

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      // Open dialog instead of uploading immediately
      setPendingFile(file);
      setDialogMode('extract');
      setDialogBaselines([]);
      setDialogPluginId('');
    }
  }, []);

  const handleDialogConfirm = useCallback(() => {
    if (!pendingFile) return;

    // Validate: compliance or both requires at least one baseline
    if ((dialogMode === 'understand' || dialogMode === 'both') && dialogBaselines.length === 0) {
      return; // Button is disabled, but guard anyway
    }

    setFileName(pendingFile.name);
    setStatus('uploading');
    setErrorMessage(null);
    uploadMutation.mutate({
      file: pendingFile,
      mode: dialogMode,
      baselineIds: dialogBaselines,
      pluginId: dialogPluginId || undefined,
    });
    setPendingFile(null);
  }, [pendingFile, dialogMode, dialogBaselines, dialogPluginId, uploadMutation]);

  const handleDialogCancel = useCallback(() => {
    setPendingFile(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
    disabled: status === 'uploading' || !!pendingFile,
  });

  const showPluginSelector = dialogMode === 'extract' || dialogMode === 'both';
  const showBaselineSelector = dialogMode === 'understand' || dialogMode === 'both';
  const needsBaseline = showBaselineSelector && dialogBaselines.length === 0;

  return (
    <>
      <div>
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
      </div>

      {/* Upload Mode Dialog */}
      {pendingFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
              <div>
                <h3 className="text-base font-semibold text-gray-900">Upload Options</h3>
                <p className="text-xs text-gray-500 mt-0.5 truncate max-w-[300px]">{pendingFile.name}</p>
              </div>
              <button
                onClick={handleDialogCancel}
                className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="px-5 py-4 space-y-5">
              {/* Processing Mode */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Processing Mode</label>
                <div className="space-y-2">
                  {([
                    { value: 'extract' as const, label: 'Document Extraction', desc: 'Extract structured data from the document' },
                    { value: 'understand' as const, label: 'Compliance Validation', desc: 'Evaluate against compliance policies' },
                    { value: 'both' as const, label: 'Both', desc: 'Extract data and run compliance checks' },
                  ]).map(({ value, label, desc }) => (
                    <label
                      key={value}
                      className={clsx(
                        'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                        dialogMode === value
                          ? 'border-primary-300 bg-primary-50'
                          : 'border-gray-200 hover:border-gray-300'
                      )}
                    >
                      <input
                        type="radio"
                        name="processingMode"
                        value={value}
                        checked={dialogMode === value}
                        onChange={() => setDialogMode(value)}
                        className="mt-0.5 text-primary-600 focus:ring-primary-500"
                      />
                      <div>
                        <span className="text-sm font-medium text-gray-900">{label}</span>
                        <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Plugin Selector */}
              {showPluginSelector && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Document Type</label>
                  <select
                    value={dialogPluginId}
                    onChange={(e) => setDialogPluginId(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="">Auto-detect (recommended)</option>
                    {pluginList.map((id) => (
                      <option key={id} value={id}>
                        {id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-400 mt-1">The router will classify automatically if auto-detect is selected</p>
                </div>
              )}

              {/* Baseline Selector */}
              {showBaselineSelector && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Compliance Policies
                    <span className="text-red-500 ml-0.5">*</span>
                  </label>
                  {publishedBaselines.length === 0 ? (
                    <p className="text-xs text-gray-400 italic">No published policies available. Create one in Compliance Policies first.</p>
                  ) : (
                    <div className="space-y-1.5 max-h-32 overflow-y-auto">
                      {publishedBaselines.map((bl: any) => (
                        <label
                          key={bl.baselineId}
                          className={clsx(
                            'flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors text-sm',
                            dialogBaselines.includes(bl.baselineId)
                              ? 'border-primary-300 bg-primary-50'
                              : 'border-gray-200 hover:border-gray-300'
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={dialogBaselines.includes(bl.baselineId)}
                            onChange={(e) =>
                              setDialogBaselines((prev) =>
                                e.target.checked
                                  ? [...prev, bl.baselineId]
                                  : prev.filter((id) => id !== bl.baselineId)
                              )
                            }
                            className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                          />
                          <span className="text-gray-800">{bl.name}</span>
                          {bl.description && (
                            <span className="text-xs text-gray-400 ml-auto truncate max-w-[140px]">{bl.description}</span>
                          )}
                        </label>
                      ))}
                    </div>
                  )}
                  {needsBaseline && publishedBaselines.length > 0 && (
                    <p className="text-xs text-red-500 mt-1">Select at least one baseline</p>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-200 bg-gray-50">
              <button
                onClick={handleDialogCancel}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDialogConfirm}
                disabled={needsBaseline}
                className={clsx(
                  'px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors',
                  needsBaseline
                    ? 'bg-gray-300 cursor-not-allowed'
                    : 'bg-primary-600 hover:bg-primary-700'
                )}
              >
                Upload
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
