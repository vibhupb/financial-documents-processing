import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { Shield, Plus } from 'lucide-react';

const statusColors: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-700',
  published: 'bg-green-100 text-green-700',
  archived: 'bg-gray-100 text-gray-500',
};

export default function Baselines() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const { data, isLoading } = useQuery({
    queryKey: ['baselines', statusFilter],
    queryFn: () => api.listBaselines({ status: statusFilter || undefined }),
  });
  const createMutation = useMutation({
    mutationFn: (body: { name: string; description: string }) =>
      api.createBaseline(body),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['baselines'] });
      navigate(`/baselines/${result.baselineId}`);
    },
  });
  const baselines = data?.baselines || [];
  return (
    <div className="h-full overflow-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="w-6 h-6" /> Compliance Baselines
        </h1>
        <button onClick={() => createMutation.mutate({
          name: 'New Baseline', description: '' })}
          className="btn-primary flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Create Baseline
        </button>
      </div>
      {/* Status filter tabs */}
      <div className="flex gap-2 mb-4">
        {['', 'draft', 'published', 'archived'].map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 rounded text-sm ${statusFilter === s
              ? 'bg-primary-100 text-primary-700' : 'text-gray-500 hover:bg-gray-100'}`}>
            {s || 'All'}
          </button>))}
      </div>
      {isLoading ? <div className="animate-spin h-8 w-8 border-b-2 border-primary-600 rounded-full mx-auto" />
       : <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {baselines.map((bl: any) => (
          <Link key={bl.baselineId} to={`/baselines/${bl.baselineId}`}
            className="border rounded-lg p-4 hover:shadow-md transition-shadow bg-white">
            <div className="flex items-start justify-between">
              <h3 className="font-semibold text-gray-900">{bl.name}</h3>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                statusColors[bl.status] || 'bg-gray-100'}`}>{bl.status}</span>
            </div>
            <p className="text-sm text-gray-500 mt-1">{bl.description || 'No description'}</p>
            <div className="flex items-center gap-3 mt-3 text-xs text-gray-400">
              <span>{(bl.requirements || []).length} requirements</span>
              <span>{(bl.pluginIds || []).join(', ') || 'Standalone'}</span>
            </div>
          </Link>))}
      </div>}
    </div>);
}
