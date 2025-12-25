import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import type { Document, ReviewStatus } from '../types';
import StatusBadge from '../components/StatusBadge';

const REVIEW_STATUS_TABS: { status: ReviewStatus; label: string; color: string }[] = [
  { status: 'PENDING_REVIEW', label: 'Pending Review', color: 'bg-yellow-100 text-yellow-800' },
  { status: 'APPROVED', label: 'Approved', color: 'bg-green-100 text-green-800' },
  { status: 'REJECTED', label: 'Rejected', color: 'bg-red-100 text-red-800' },
];

export default function Review() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ReviewStatus>('PENDING_REVIEW');
  const [counts, setCounts] = useState<Record<ReviewStatus, number>>({
    PENDING_REVIEW: 0,
    APPROVED: 0,
    REJECTED: 0,
  });

  useEffect(() => {
    loadDocuments();
  }, [activeTab]);

  async function loadDocuments() {
    try {
      setLoading(true);
      setError(null);

      const result = await api.listReviewQueue({ status: activeTab, limit: 50 });
      setDocuments(result.documents);

      // Update count for current tab
      setCounts((prev) => ({ ...prev, [activeTab]: result.count }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }

  function formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function formatDocumentType(docType: string): string {
    return docType === 'CREDIT_AGREEMENT' ? 'Credit Agreement' : 'Loan Package';
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Review Queue</h1>
          <p className="mt-1 text-sm text-gray-500">
            Review and approve extracted document data
          </p>
        </div>
        <button
          onClick={loadDocuments}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
        >
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {REVIEW_STATUS_TABS.map((tab) => (
            <button
              key={tab.status}
              onClick={() => setActiveTab(tab.status)}
              className={`
                whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm
                ${
                  activeTab === tab.status
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              {tab.label}
              {counts[tab.status] > 0 && (
                <span
                  className={`ml-2 py-0.5 px-2.5 rounded-full text-xs font-medium ${tab.color}`}
                >
                  {counts[tab.status]}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
        </div>
      )}

      {/* Empty State */}
      {!loading && documents.length === 0 && (
        <div className="text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No documents</h3>
          <p className="mt-1 text-sm text-gray-500">
            {activeTab === 'PENDING_REVIEW'
              ? 'No documents are pending review.'
              : `No ${activeTab.toLowerCase().replace('_', ' ')} documents.`}
          </p>
        </div>
      )}

      {/* Document List */}
      {!loading && documents.length > 0 && (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {documents.map((doc) => (
              <li key={doc.documentId}>
                <Link
                  to={`/review/${doc.documentId}`}
                  className="block hover:bg-gray-50"
                >
                  <div className="px-4 py-4 sm:px-6">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="flex-shrink-0">
                          <div
                            className={`h-10 w-10 rounded-full flex items-center justify-center ${
                              doc.documentType === 'CREDIT_AGREEMENT'
                                ? 'bg-purple-100'
                                : 'bg-blue-100'
                            }`}
                          >
                            <svg
                              className={`h-6 w-6 ${
                                doc.documentType === 'CREDIT_AGREEMENT'
                                  ? 'text-purple-600'
                                  : 'text-blue-600'
                              }`}
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                              />
                            </svg>
                          </div>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-indigo-600 truncate">
                            {doc.documentId.substring(0, 8)}...
                          </p>
                          <p className="text-sm text-gray-500">
                            {formatDocumentType(doc.documentType)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-4">
                        <StatusBadge status={doc.status} />
                        {doc.validation && (
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              doc.validation.confidence === 'high'
                                ? 'bg-green-100 text-green-800'
                                : doc.validation.confidence === 'medium'
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-red-100 text-red-800'
                            }`}
                          >
                            {doc.validation.confidence} confidence
                          </span>
                        )}
                        <svg
                          className="h-5 w-5 text-gray-400"
                          viewBox="0 0 20 20"
                          fill="currentColor"
                        >
                          <path
                            fillRule="evenodd"
                            d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </div>
                    </div>
                    <div className="mt-2 sm:flex sm:justify-between">
                      <div className="sm:flex">
                        <p className="flex items-center text-sm text-gray-500">
                          Created {formatDate(doc.createdAt)}
                        </p>
                      </div>
                      {doc.reviewedBy && (
                        <div className="mt-2 flex items-center text-sm text-gray-500 sm:mt-0">
                          <span>Reviewed by {doc.reviewedBy}</span>
                          {doc.reviewedAt && (
                            <span className="ml-2">
                              on {formatDate(doc.reviewedAt)}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
