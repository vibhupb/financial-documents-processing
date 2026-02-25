import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  AlertCircle,
  Clock,
  DollarSign,
  Timer,
  ChevronRight,
  FileText,
} from 'lucide-react';
import { api } from '../services/api';
import StatusBadge from '../components/StatusBadge';
import DocumentViewer from '../components/DocumentViewer';
import PipelineTracker from '../components/PipelineTracker';
import LiveResultsStream from '../components/LiveResultsStream';
import InlineReviewActions from '../components/InlineReviewActions';
import UnknownTypePrompt from '../components/UnknownTypePrompt';
import type { Document, EnrichedStatusResponse, ProcessingStatus } from '../types';

const PROCESSING_STATUSES: ProcessingStatus[] = [
  'PENDING',
  'CLASSIFIED',
  'EXTRACTING',
  'EXTRACTED',
  'NORMALIZING',
  'REPROCESSING',
];
const COMPLETED_STATUSES: ProcessingStatus[] = ['PROCESSED', 'FAILED', 'SKIPPED'];

function isProcessingStatus(status: string): boolean {
  return PROCESSING_STATUSES.includes(status as ProcessingStatus);
}

function isCompletedStatus(status: string): boolean {
  return COMPLETED_STATUSES.includes(status as ProcessingStatus);
}

function isUnknownTypeFailure(
  doc: Document,
  statusData: EnrichedStatusResponse | undefined
): boolean {
  if (doc.status !== 'FAILED') return false;
  if (!statusData?.stages?.classification) return false;
  const classResult = statusData.stages.classification.result;
  if (!classResult) return false;
  const docType = classResult.documentType?.toLowerCase() ?? '';
  const confidence = typeof classResult.confidence === 'number' ? classResult.confidence : 0;
  return docType === 'unknown' || docType === '' || confidence < 50;
}

function formatDocType(docType?: string): string {
  if (!docType) return '';
  return docType
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatCost(cost?: { totalCost: number }): string {
  if (!cost) return '';
  return `$${cost.totalCost.toFixed(2)}`;
}

function formatTime(time?: { totalSeconds: number }): string {
  if (!time) return '';
  const s = Math.round(time.totalSeconds);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}m ${rem}s`;
}

export default function DocumentDetail() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();

  // --- Data fetching ---

  const {
    data: documentData,
    isLoading: isDocumentLoading,
    error: documentError,
    failureCount,
  } = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => api.getDocument(documentId!),
    enabled: !!documentId,
    retry: 10,
    retryDelay: (attemptIndex) => Math.min(1000 * (attemptIndex + 1), 5000),
    refetchInterval: (query) => {
      const data = query.state.data;
      // Document not created yet by trigger Lambda -- keep polling
      if (data && 'error' in data) return 2000;
      const status = data && 'document' in data ? data.document?.status : undefined;
      if (!status || isCompletedStatus(status)) return false;
      return 3000;
    },
  });

  const currentDoc: Document | undefined =
    documentData && 'document' in documentData ? documentData.document : undefined;

  const docStatus = currentDoc?.status;
  const isProcessing = !!docStatus && isProcessingStatus(docStatus);
  const isProcessedOrReview =
    docStatus === 'PROCESSED' || !!currentDoc?.reviewStatus;

  // Processing status -- polls while processing
  const { data: statusData } = useQuery({
    queryKey: ['document-status', documentId],
    queryFn: () => api.getProcessingStatus(documentId!),
    enabled: !!documentId && (isProcessing || docStatus === 'FAILED'),
    refetchInterval: isProcessing ? 3000 : false,
  });

  // PDF URL -- fetch only when completed
  const {
    data: pdfData,
    isLoading: isPdfLoading,
  } = useQuery({
    queryKey: ['document-pdf', documentId],
    queryFn: () => api.getDocumentPdfUrl(documentId!),
    enabled: !!documentId && isProcessedOrReview,
    staleTime: 50 * 60 * 1000,
  });

  // Review queue for "Next in Queue" button
  const { data: reviewQueueData } = useQuery({
    queryKey: ['review-queue-nav'],
    queryFn: () => api.listDocuments({ status: 'PENDING_REVIEW' }),
    enabled: currentDoc?.reviewStatus === 'PENDING_REVIEW',
    staleTime: 30_000,
  });

  // --- Computed ---

  const handleNextInQueue = () => {
    if (!reviewQueueData?.documents?.length) return;
    const docs = reviewQueueData.documents;
    const currentIndex = docs.findIndex((d) => d.documentId === documentId);
    const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % docs.length : 0;
    const nextDoc = docs[nextIndex];
    if (nextDoc && nextDoc.documentId !== documentId) {
      navigate(`/documents/${nextDoc.documentId}`);
    }
  };

  // --- Loading state ---

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

  // --- Initializing state (trigger Lambda hasn't created DB record yet) ---

  if (documentData && 'error' in documentData && failureCount < 10) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <div className="relative">
            <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary-200 border-t-primary-600 mx-auto" />
            <Clock className="w-6 h-6 text-primary-600 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
          </div>
          <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-2">
            Initializing Document
          </h3>
          <p className="text-gray-500 mb-2">
            Your document is being uploaded and initialized...
          </p>
          <p className="text-sm text-gray-400 font-mono">ID: {documentId}</p>
        </div>
      </div>
    );
  }

  // --- Error state (retries exhausted, no document) ---

  if (documentError || !currentDoc) {
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
            to="/"
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Queue
          </Link>
        </div>
      </div>
    );
  }

  const doc = currentDoc;

  // --- Mode C: Unknown Type (failed + unknown/low confidence classification) ---

  if (isUnknownTypeFailure(doc, statusData)) {
    const classResult = statusData?.stages?.classification?.result;
    return (
      <div className="h-full flex flex-col">
        <DetailHeader
          doc={doc}
          documentId={documentId!}
        />

        <div className="flex-1 overflow-y-auto">
          {/* Pipeline tracker showing where it failed */}
          {statusData?.stages && (
            <div className="px-6 py-4 border-b border-gray-200 bg-white">
              <PipelineTracker stages={statusData.stages} />
            </div>
          )}

          {/* Unknown type prompt */}
          <div className="px-6 py-12">
            <UnknownTypePrompt
              documentId={documentId!}
              bestGuess={classResult?.documentType}
              confidence={
                typeof classResult?.confidence === 'number'
                  ? classResult.confidence
                  : undefined
              }
            />
          </div>
        </div>
      </div>
    );
  }

  // --- Mode A: Processing View ---

  if (isProcessing) {
    return (
      <div className="h-full flex flex-col">
        <DetailHeader
          doc={doc}
          documentId={documentId!}
          docType={statusData?.documentType}
        />

        <div className="flex-1 overflow-y-auto">
          {/* Pipeline tracker */}
          {statusData?.stages && (
            <div className="px-6 py-4 border-b border-gray-200 bg-white">
              <PipelineTracker stages={statusData.stages} />
            </div>
          )}

          {/* Live results stream */}
          <div className="px-6 py-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">
              Processing Log
            </h3>
            <LiveResultsStream
              events={statusData?.events ?? []}
              startedAt={statusData?.startedAt}
            />
          </div>
        </div>
      </div>
    );
  }

  // --- FAILED state (not unknown type -- general failure) ---

  if (doc.status === 'FAILED') {
    return (
      <div className="h-full flex flex-col">
        <DetailHeader
          doc={doc}
          documentId={documentId!}
        />

        <div className="flex-1 overflow-y-auto">
          {statusData?.stages && (
            <div className="px-6 py-4 border-b border-gray-200 bg-white">
              <PipelineTracker stages={statusData.stages} />
            </div>
          )}

          <div className="flex-1 flex items-center justify-center py-16">
            <div className="text-center max-w-md">
              <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                Processing Failed
              </h3>
              <p className="text-gray-500 mb-6">
                An error occurred during document processing.
              </p>
              <InlineReviewActions
                documentId={documentId!}
                status={doc.status}
                reviewStatus={doc.reviewStatus}
              />
            </div>
          </div>

          {/* Show events log if available */}
          {statusData?.events && statusData.events.length > 0 && (
            <div className="px-6 py-4 border-t border-gray-200">
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Processing Log
              </h3>
              <LiveResultsStream
                events={statusData.events}
                startedAt={statusData.startedAt}
              />
            </div>
          )}
        </div>
      </div>
    );
  }

  // --- Mode B: Review/Completed View ---

  // Build review bar for PENDING_REVIEW documents
  const reviewBar =
    doc.reviewStatus === 'PENDING_REVIEW' ? (
      <div className="flex items-center justify-between px-4 py-3 bg-amber-50 border-t border-amber-200">
        <InlineReviewActions
          documentId={documentId!}
          status={doc.status}
          reviewStatus={doc.reviewStatus}
        />
        {reviewQueueData?.documents && reviewQueueData.documents.length > 1 && (
          <button
            onClick={handleNextInQueue}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-amber-700 bg-amber-100 rounded-md hover:bg-amber-200 transition-colors"
          >
            Next in Queue
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    ) : undefined;

  // PDF still loading
  if (isPdfLoading) {
    return (
      <div className="h-full flex flex-col">
        <DetailHeader
          doc={doc}
          documentId={documentId!}
          showMeta
        />

        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto" />
            <p className="mt-4 text-gray-500">Loading document viewer...</p>
          </div>
        </div>
      </div>
    );
  }

  // PDF error or no URL -- show data-only fallback
  if (!pdfData?.pdfUrl) {
    return (
      <div className="h-full flex flex-col">
        <DetailHeader
          doc={doc}
          documentId={documentId!}
          showMeta
        />

        <div className="flex-1 flex overflow-hidden">
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
              reviewBar={reviewBar}
            />
          </div>
        </div>
      </div>
    );
  }

  // Full document viewer
  return (
    <div className="h-full flex flex-col">
      <DetailHeader
        doc={doc}
        documentId={documentId!}
        showMeta
      />

      <div className="flex-1 overflow-hidden">
        <DocumentViewer
          document={doc}
          pdfUrl={pdfData.pdfUrl}
          className="h-full"
          reviewBar={reviewBar}
        />
      </div>
    </div>
  );
}

// --- Header component shared across modes ---

interface DetailHeaderProps {
  doc: Document;
  documentId: string;
  docType?: string;
  showMeta?: boolean;
}

function DetailHeader({ doc, documentId, docType, showMeta }: DetailHeaderProps) {
  const displayType = docType || doc.documentType;
  const cost = formatCost(doc.processingCost);
  const time = formatTime(doc.processingTime);

  return (
    <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white flex-shrink-0">
      <div className="flex items-center gap-4 min-w-0">
        <Link
          to="/"
          className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors flex-shrink-0"
        >
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </Link>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-gray-900 truncate">
              {doc.fileName || 'Document'}
            </h1>
            {displayType && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-gray-100 text-xs font-medium text-gray-600 flex-shrink-0">
                {formatDocType(displayType)}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 font-mono truncate">{documentId}</p>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-shrink-0">
        {showMeta && cost && (
          <span className="inline-flex items-center gap-1 text-sm text-gray-500">
            <DollarSign className="w-3.5 h-3.5" />
            {cost}
          </span>
        )}
        {showMeta && time && (
          <span className="inline-flex items-center gap-1 text-sm text-gray-500">
            <Timer className="w-3.5 h-3.5" />
            {time}
          </span>
        )}
        <StatusBadge status={doc.reviewStatus || doc.status} />
      </div>
    </div>
  );
}
