import { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Search, SlidersHorizontal, FileText } from 'lucide-react';
import { format } from 'date-fns';
import clsx from 'clsx';
import { api } from '../services/api';
import { optimisticUploads } from '../services/optimistic-uploads';
import type { Document, ProcessingStatus } from '../types';
import UploadBar from '../components/UploadBar';
import MetricsStrip from '../components/MetricsStrip';
import StatusBadge from '../components/StatusBadge';
import InlineReviewActions from '../components/InlineReviewActions';

// Statuses that indicate active processing
const PROCESSING_STATUSES: ProcessingStatus[] = [
  'PENDING',
  'CLASSIFIED',
  'EXTRACTING',
  'EXTRACTED',
  'NORMALIZING',
  'REPROCESSING',
];

type SortMode = 'attention' | 'newest' | 'oldest' | 'cost';

const STATUS_FILTER_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'PROCESSING', label: 'Processing' },
  { value: 'PENDING_REVIEW', label: 'Needs Review' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'FAILED', label: 'Failed' },
];

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: 'attention', label: 'Needs Attention' },
  { value: 'newest', label: 'Newest' },
  { value: 'oldest', label: 'Oldest' },
  { value: 'cost', label: 'Highest Cost' },
];

/** Map UI status filter to API status parameter */
function toApiStatus(filter: string): string | undefined {
  if (!filter) return undefined;
  if (filter === 'PROCESSING') return 'PENDING';
  return filter;
}

/** Check if a document is actively processing */
function isProcessing(doc: Document): boolean {
  return PROCESSING_STATUSES.includes(doc.status);
}

/** Priority bucket for "Needs Attention" sort */
function attentionBucket(doc: Document): number {
  if (doc.status === 'FAILED') return 0;
  if (isProcessing(doc)) return 1;
  if (doc.reviewStatus === 'PENDING_REVIEW') return 2;
  return 3;
}

/** Format document type from SCREAMING_SNAKE to Title Case */
function formatDocType(docType: string): string {
  return docType
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

export default function WorkQueue() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('attention');

  // Fetch documents
  const { data, isLoading, error } = useQuery({
    queryKey: ['documents', statusFilter],
    queryFn: () =>
      api.listDocuments({ status: toApiStatus(statusFilter), limit: 100 }),
    refetchInterval: (query) => {
      const docs = query.state.data?.documents;
      if (docs?.some(isProcessing)) return 5000;
      if (optimisticUploads.hasPending()) return 3000;
      return 15000;
    },
  });

  // Resolve optimistic placeholders once real data arrives from the server
  useEffect(() => {
    if (data?.documents) {
      optimisticUploads.resolve(data.documents.map((d) => d.documentId));
    }
  }, [data?.documents]);

  // Fetch plugins for type filter dropdown
  const { data: pluginsData } = useQuery({
    queryKey: ['plugins'],
    queryFn: api.getPlugins,
    staleTime: 60000,
  });

  // Build type options from plugin registry
  const typeOptions = useMemo(() => {
    if (!pluginsData?.plugins) return [];
    return Object.entries(pluginsData.plugins).map(([id, plugin]: [string, any]) => ({
      value: id.toUpperCase(),
      label: plugin.name || formatDocType(id),
    }));
  }, [pluginsData]);

  // Filter and sort documents
  const sortedDocuments = useMemo(() => {
    let docs = data?.documents ?? [];

    // Merge optimistic placeholders not yet in server data
    const serverIds = new Set(docs.map((d) => d.documentId));
    const pending = optimisticUploads.getPending().filter((d) => !serverIds.has(d.documentId));
    if (pending.length) docs = [...pending, ...docs];

    // Client-side search filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      docs = docs.filter(
        (doc) =>
          doc.documentId.toLowerCase().includes(q) ||
          (doc.fileName && doc.fileName.toLowerCase().includes(q))
      );
    }

    // Client-side type filter
    if (typeFilter) {
      docs = docs.filter((doc) => doc.documentType === typeFilter);
    }

    // Sort
    const sorted = [...docs];
    sorted.sort((a, b) => {
      switch (sortMode) {
        case 'attention': {
          const bucketA = attentionBucket(a);
          const bucketB = attentionBucket(b);
          if (bucketA !== bucketB) return bucketA - bucketB;
          // Within same bucket: failed/completed newest first, processing/review oldest first
          if (bucketA <= 1) {
            // Failed (0) = newest first; Processing (1) = oldest first
            if (bucketA === 0) return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
            return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
          }
          if (bucketA === 2) return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
        }
        case 'newest':
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
        case 'oldest':
          return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
        case 'cost':
          return (b.processingCost?.totalCost ?? 0) - (a.processingCost?.totalCost ?? 0);
        default:
          return 0;
      }
    });

    return sorted;
  }, [data?.documents, searchQuery, typeFilter, sortMode]);

  /** Row border color based on document state */
  function rowBorderClass(doc: Document): string {
    if (doc.status === 'FAILED') return 'border-l-4 border-l-red-400';
    if (isProcessing(doc)) return 'border-l-4 border-l-blue-400';
    if (doc.reviewStatus === 'PENDING_REVIEW') return 'border-l-4 border-l-amber-400';
    return 'border-l-4 border-l-transparent';
  }

  /** Handle MetricsStrip filter change */
  const handleMetricsFilter = (status: string) => {
    setStatusFilter(status);
  };

  return (
    <div className="h-full overflow-auto p-8 space-y-6">
      {/* Zone 1 -- Upload */}
      <UploadBar />

      {/* Zone 2 -- Metrics */}
      <MetricsStrip onFilterChange={handleMetricsFilter} activeFilter={statusFilter} />

      {/* Zone 3 -- Document List */}
      <div className="space-y-4">
        {/* Filters bar */}
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search by filename or ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          {/* Status dropdown */}
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {STATUS_FILTER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Type dropdown */}
          {typeOptions.length > 0 && (
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All Types</option>
              {typeOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}

          {/* Sort dropdown */}
          <select
            value={sortMode}
            onChange={(e) => setSortMode(e.target.value as SortMode)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="relative w-12 h-12">
                <div className="absolute inset-0 rounded-full border-4 border-primary-100" />
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-transparent border-t-primary-600" />
              </div>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <p className="text-red-500">Failed to load documents</p>
            </div>
          ) : sortedDocuments.length === 0 ? (
            <div className="text-center py-16">
              <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">
                No documents yet — Drop a PDF above to get started
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Document
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Cost
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Time
                  </th>
                  <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sortedDocuments.map((doc) => (
                  <tr
                    key={doc.documentId}
                    onClick={() => navigate(`/documents/${doc.documentId}`)}
                    className={clsx(
                      'hover:bg-gray-50 transition-colors cursor-pointer',
                      rowBorderClass(doc)
                    )}
                  >
                    {/* Document column */}
                    <td className="px-6 py-4">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                          <FileText className="w-4 h-4 text-gray-500" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {doc.fileName || `${doc.documentId.slice(0, 12)}...`}
                          </p>
                          <p className="text-xs text-gray-400 font-mono truncate">
                            {doc.documentId.slice(0, 12)}
                          </p>
                          {isProcessing(doc) && doc.latestEvent && (
                            <div className="flex items-center gap-2 mt-1.5">
                              <span className="relative flex h-3 w-3 flex-shrink-0">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                                <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500" />
                              </span>
                              <span className="text-sm text-blue-600 truncate font-medium">
                                {doc.latestEvent.message}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Type column */}
                    <td className="px-4 py-4 text-sm text-gray-600">
                      {doc.documentType ? formatDocType(doc.documentType) : '-'}
                    </td>

                    {/* Status column */}
                    <td className="px-4 py-4">
                      <StatusBadge
                        status={doc.reviewStatus || doc.status}
                      />
                    </td>

                    {/* Cost column */}
                    <td className="px-4 py-4 text-sm text-gray-600">
                      {doc.processingCost
                        ? `$${doc.processingCost.totalCost.toFixed(2)}`
                        : '-'}
                    </td>

                    {/* Time column */}
                    <td className="px-4 py-4 text-sm text-gray-500">
                      {doc.processingTime
                        ? `${doc.processingTime.totalSeconds.toFixed(1)}s`
                        : doc.createdAt
                        ? format(new Date(doc.createdAt), 'MMM d, h:mm a')
                        : '-'}
                    </td>

                    {/* Actions column */}
                    <td className="px-6 py-4 text-right">
                      <InlineReviewActions
                        documentId={doc.documentId}
                        status={doc.status}
                        reviewStatus={doc.reviewStatus}
                        compact
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
