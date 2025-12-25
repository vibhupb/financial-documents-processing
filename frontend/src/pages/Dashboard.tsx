import { useQuery } from '@tanstack/react-query';
import { FileText, CheckCircle, Clock, AlertCircle, TrendingUp, DollarSign } from 'lucide-react';
import { Link } from 'react-router-dom';
import { format } from 'date-fns';
import { api } from '../services/api';
import MetricCard from '../components/MetricCard';
import StatusBadge from '../components/StatusBadge';

export default function Dashboard() {
  const { data: metrics, isLoading, error } = useQuery({
    queryKey: ['metrics'],
    queryFn: api.getMetrics,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card text-center py-12">
        <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900">Failed to load metrics</h3>
        <p className="mt-2 text-gray-500">Please try again later</p>
      </div>
    );
  }

  const statusCounts = metrics?.statusCounts || {};
  const processedCount = statusCounts['PROCESSED'] || 0;
  const pendingCount = statusCounts['PENDING'] || 0;
  const failedCount = statusCounts['FAILED'] || 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-gray-500">
          Monitor your document processing pipeline
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Total Documents"
          value={metrics?.totalDocuments || 0}
          icon={<FileText className="w-6 h-6" />}
        />
        <MetricCard
          title="Processed"
          value={processedCount}
          icon={<CheckCircle className="w-6 h-6" />}
        />
        <MetricCard
          title="Pending"
          value={pendingCount}
          icon={<Clock className="w-6 h-6" />}
        />
        <MetricCard
          title="Failed"
          value={failedCount}
          icon={<AlertCircle className="w-6 h-6" />}
        />
      </div>


      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Recent Documents</h2>
            <Link to="/documents" className="text-sm text-primary-600 hover:text-primary-700">
              View all
            </Link>
          </div>
          <div className="space-y-4">
            {metrics?.recentDocuments?.length ? (
              metrics.recentDocuments.map((doc) => (
                <Link
                  key={doc.documentId}
                  to={`/documents/${doc.documentId}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                      <FileText className="w-5 h-5 text-gray-500" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {doc.documentId.slice(0, 8)}...
                      </p>
                      <p className="text-xs text-gray-500">
                        {doc.createdAt
                          ? format(new Date(doc.createdAt), 'MMM d, yyyy h:mm a')
                          : 'Unknown date'}
                      </p>
                    </div>
                  </div>
                  <StatusBadge status={doc.status} />
                </Link>
              ))
            ) : (
              <p className="text-gray-500 text-center py-8">No documents yet</p>
            )}
          </div>
        </div>

        {/* Processing Pipeline */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Processing Pipeline</h2>
          <div className="space-y-4">
            <PipelineStage
              name="Router (Classification)"
              description="Claude 3 Haiku classifies document types"
              cost="~$0.01/doc"
              icon={<TrendingUp className="w-5 h-5" />}
            />
            <PipelineStage
              name="Surgeon (Extraction)"
              description="Textract extracts targeted pages only"
              cost="~$0.03/doc"
              icon={<FileText className="w-5 h-5" />}
            />
            <PipelineStage
              name="Closer (Normalization)"
              description="Claude 3.5 Sonnet normalizes data"
              cost="~$0.02/doc"
              icon={<CheckCircle className="w-5 h-5" />}
            />
          </div>
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Total per document:</span>
              <span className="font-semibold text-green-600">~$0.06</span>
            </div>
            <div className="flex justify-between text-sm mt-1">
              <span className="text-gray-500">Brute-force cost:</span>
              <span className="font-semibold text-red-600">~$4.55</span>
            </div>
          </div>
        </div>
      </div>

      {/* Savings Note - Small footer */}
      {processedCount > 0 && (
        <div className="text-center text-xs text-gray-400 pt-4 border-t border-gray-100">
          <DollarSign className="w-3 h-3 inline-block mr-1" />
          Router pattern savings: ~${(processedCount * 4.49).toFixed(2)} estimated
          ({processedCount} docs × $4.49/doc vs brute-force)
        </div>
      )}
    </div>
  );
}

interface PipelineStageProps {
  name: string;
  description: string;
  cost: string;
  icon: React.ReactNode;
}

function PipelineStage({ name, description, cost, icon }: PipelineStageProps) {
  return (
    <div className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
      <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center text-primary-600 shadow-sm">
        {icon}
      </div>
      <div className="flex-1">
        <p className="text-sm font-medium text-gray-900">{name}</p>
        <p className="text-xs text-gray-500">{description}</p>
      </div>
      <span className="text-xs font-medium text-gray-400">{cost}</span>
    </div>
  );
}
