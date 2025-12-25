import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { FileText, Search, Filter, ChevronRight, RefreshCw } from 'lucide-react';
import { format } from 'date-fns';
import clsx from 'clsx';
import { api } from '../services/api';
import StatusBadge from '../components/StatusBadge';

const statusFilters: Array<{ value: string; label: string }> = [
  { value: '', label: 'All Status' },
  { value: 'PROCESSED', label: 'Processed' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'FAILED', label: 'Failed' },
];

export default function Documents() {
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['documents', statusFilter],
    queryFn: () => api.listDocuments({ status: statusFilter || undefined, limit: 50 }),
    refetchInterval: 30000,
  });

  const filteredDocuments = data?.documents?.filter((doc) =>
    searchQuery
      ? doc.documentId.toLowerCase().includes(searchQuery.toLowerCase())
      : true
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
          <p className="mt-1 text-gray-500">
            {data?.count || 0} documents processed
          </p>
        </div>
        <Link to="/upload" className="btn-primary">
          Upload Document
        </Link>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by document ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10"
            />
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-5 h-5 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input w-40"
            >
              {statusFilters.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </select>
          </div>

          {/* Refresh */}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={clsx('w-4 h-4', isFetching && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {/* Documents List */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-500">Failed to load documents</p>
          </div>
        ) : filteredDocuments?.length ? (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Document ID
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredDocuments.map((doc) => (
                <tr key={doc.documentId} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center">
                        <FileText className="w-4 h-4 text-gray-500" />
                      </div>
                      <span className="font-mono text-sm text-gray-900">
                        {doc.documentId.slice(0, 12)}...
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {doc.documentType || 'Loan Package'}
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={doc.status} />
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {doc.createdAt
                      ? format(new Date(doc.createdAt), 'MMM d, yyyy h:mm a')
                      : '-'}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      to={`/documents/${doc.documentId}`}
                      className="text-primary-600 hover:text-primary-700"
                    >
                      <ChevronRight className="w-5 h-5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No documents found</p>
            <Link to="/upload" className="mt-4 inline-block text-primary-600 hover:text-primary-700">
              Upload your first document
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
