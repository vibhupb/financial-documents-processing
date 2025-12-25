import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  FileText,
  AlertCircle,
  Clock,
  RefreshCw,
} from 'lucide-react';
import { format } from 'date-fns';
import { api } from '../services/api';
import StatusBadge from '../components/StatusBadge';
import DocumentViewer from '../components/DocumentViewer';

export default function DocumentDetail() {
  const { documentId } = useParams<{ documentId: string }>();

  // Fetch document data
  const {
    data: documentData,
    isLoading: isDocumentLoading,
    error: documentError,
  } = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => api.getDocument(documentId!),
    enabled: !!documentId,
  });

  // Fetch PDF URL for viewing
  const {
    data: pdfData,
    isLoading: isPdfLoading,
    error: pdfError,
  } = useQuery({
    queryKey: ['document-pdf', documentId],
    queryFn: () => api.getDocumentPdfUrl(documentId!),
    enabled: !!documentId && documentData?.document?.status === 'PROCESSED',
    staleTime: 1000 * 60 * 50, // 50 minutes (URLs expire in 1 hour)
  });

  // Fetch processing status (polling while processing)
  const { data: statusData } = useQuery({
    queryKey: ['document-status', documentId],
    queryFn: () => api.getProcessingStatus(documentId!),
    enabled: !!documentId,
    refetchInterval:
      documentData?.document?.status === 'PROCESSED' ||
      documentData?.document?.status === 'FAILED'
        ? false
        : 5000,
  });

  // Loading state
  if (isDocumentLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto" />
          <p className="mt-4 text-gray-500">Loading document...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (documentError || !documentData?.document) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-900 mb-2">
            Document Not Found
          </h3>
          <p className="text-gray-500 mb-6">
            The requested document could not be found or you don't have permission to view it.
          </p>
          <Link
            to="/documents"
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Documents
          </Link>
        </div>
      </div>
    );
  }

  const doc = documentData.document;
  const isProcessing = !['PROCESSED', 'FAILED', 'SKIPPED'].includes(doc.status);

  // Processing state - show progress
  if (isProcessing) {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-4">
            <Link
              to="/documents"
              className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                {doc.fileName || 'Document Processing'}
              </h1>
              <p className="text-sm text-gray-500 font-mono">{documentId}</p>
            </div>
          </div>
          <StatusBadge status={doc.status} />
        </div>

        {/* Processing Progress */}
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-md">
            <div className="relative">
              <div className="animate-spin rounded-full h-20 w-20 border-4 border-primary-200 border-t-primary-600 mx-auto" />
              <Clock className="w-8 h-8 text-primary-600 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-2">
              Processing Document
            </h3>
            <p className="text-gray-500 mb-4">
              Your document is being processed. This typically takes 30-60 seconds.
            </p>

            {/* Processing stages */}
            <div className="bg-gray-50 rounded-lg p-4 text-left">
              <ProcessingStage
                label="Classification"
                status={getStageStatus('CLASSIFIED', doc.status)}
              />
              <ProcessingStage
                label="Extraction"
                status={getStageStatus('EXTRACTED', doc.status)}
              />
              <ProcessingStage
                label="Normalization"
                status={getStageStatus('PROCESSED', doc.status)}
              />
            </div>

            {statusData?.startDate && (
              <p className="text-xs text-gray-400 mt-4">
                Started: {format(new Date(statusData.startDate), 'MMM d, yyyy h:mm:ss a')}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Failed state
  if (doc.status === 'FAILED') {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-4">
            <Link
              to="/documents"
              className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                {doc.fileName || 'Processing Failed'}
              </h1>
              <p className="text-sm text-gray-500 font-mono">{documentId}</p>
            </div>
          </div>
          <StatusBadge status={doc.status} />
        </div>

        {/* Error message */}
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-md">
            <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              Processing Failed
            </h3>
            <p className="text-gray-500 mb-6">
              We encountered an error while processing your document. Please try uploading again.
            </p>
            <div className="flex items-center justify-center gap-4">
              <Link
                to="/upload"
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </Link>
              <Link
                to="/documents"
                className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Back to Documents
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // PDF loading
  if (isPdfLoading) {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-4">
            <Link
              to="/documents"
              className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                {doc.fileName || 'Document'}
              </h1>
              <p className="text-sm text-gray-500 font-mono">{documentId}</p>
            </div>
          </div>
          <StatusBadge status={doc.status} />
        </div>

        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto" />
            <p className="mt-4 text-gray-500">Loading document viewer...</p>
          </div>
        </div>
      </div>
    );
  }

  // PDF error - show data only view
  if (pdfError || !pdfData?.pdfUrl) {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-4">
            <Link
              to="/documents"
              className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                {doc.fileName || 'Document'}
              </h1>
              <p className="text-sm text-gray-500 font-mono">{documentId}</p>
            </div>
          </div>
          <StatusBadge status={doc.status} />
        </div>

        {/* Data only fallback */}
        <div className="flex-1 flex">
          <div className="w-1/3 border-r border-gray-200 flex items-center justify-center bg-gray-50">
            <div className="text-center p-8">
              <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">PDF preview unavailable</p>
              <p className="text-sm text-gray-400 mt-1">
                View extracted data on the right
              </p>
            </div>
          </div>
          <div className="flex-1">
            <DocumentViewer
              document={doc}
              pdfUrl=""
              className="h-full"
            />
          </div>
        </div>
      </div>
    );
  }

  // Full document viewer with PDF
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-4">
          <Link
            to="/documents"
            className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              {doc.fileName || 'Document'}
            </h1>
            <p className="text-sm text-gray-500 font-mono">{documentId}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">
            {doc.createdAt && format(new Date(doc.createdAt), 'MMM d, yyyy h:mm a')}
          </span>
          <StatusBadge status={doc.status} />
        </div>
      </div>

      {/* Document Viewer */}
      <div className="flex-1 overflow-hidden">
        <DocumentViewer
          document={doc}
          pdfUrl={pdfData.pdfUrl}
          className="h-full"
        />
      </div>
    </div>
  );
}

// Helper function to determine processing stage status
function getStageStatus(
  targetStage: string,
  currentStatus: string
): 'pending' | 'active' | 'completed' {
  const stages = ['PENDING', 'CLASSIFIED', 'EXTRACTING', 'EXTRACTED', 'NORMALIZING', 'PROCESSED'];
  const targetIndex = stages.indexOf(targetStage);
  const currentIndex = stages.indexOf(currentStatus);

  if (currentIndex > targetIndex) return 'completed';
  if (currentIndex === targetIndex) return 'active';
  return 'pending';
}

// Processing stage indicator component
function ProcessingStage({
  label,
  status,
}: {
  label: string;
  status: 'pending' | 'active' | 'completed';
}) {
  return (
    <div className="flex items-center gap-3 py-2">
      <div
        className={`w-6 h-6 rounded-full flex items-center justify-center ${
          status === 'completed'
            ? 'bg-green-500'
            : status === 'active'
              ? 'bg-primary-500 animate-pulse'
              : 'bg-gray-200'
        }`}
      >
        {status === 'completed' ? (
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        ) : status === 'active' ? (
          <div className="w-2 h-2 bg-white rounded-full" />
        ) : null}
      </div>
      <span
        className={`text-sm ${
          status === 'completed'
            ? 'text-green-600 font-medium'
            : status === 'active'
              ? 'text-primary-600 font-medium'
              : 'text-gray-400'
        }`}
      >
        {label}
      </span>
    </div>
  );
}
