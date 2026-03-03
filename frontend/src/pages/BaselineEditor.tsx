import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { Shield, Plus, Trash2, Save, Send, Pencil } from 'lucide-react';

const criticalityColors: Record<string, string> = {
  'must-have': 'bg-red-100 text-red-700',
  'should-have': 'bg-yellow-100 text-yellow-700',
  'nice-to-have': 'bg-blue-100 text-blue-700',
};

export default function BaselineEditor() {
  const { baselineId } = useParams<{ baselineId: string }>();
  const queryClient = useQueryClient();
  const [editingReq, setEditingReq] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const { data, isLoading } = useQuery({
    queryKey: ['baseline', baselineId],
    queryFn: () => api.getBaseline(baselineId!),
  });
  const addReqMutation = useMutation({
    mutationFn: () => api.addRequirement(baselineId!, {
      text: 'New requirement', category: 'General', criticality: 'should-have' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['baseline', baselineId] }),
  });
  const updateReqMutation = useMutation({
    mutationFn: ({ reqId, body }: { reqId: string; body: any }) =>
      api.updateRequirement(baselineId!, reqId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['baseline', baselineId] });
      setEditingReq(null);
    },
  });
  const deleteReqMutation = useMutation({
    mutationFn: (reqId: string) => api.deleteRequirement(baselineId!, reqId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['baseline', baselineId] }),
  });
  const publishMutation = useMutation({
    mutationFn: () => api.publishBaseline(baselineId!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['baseline', baselineId] }),
  });
  const baseline = data?.baseline;
  if (isLoading || !baseline) return <div className="p-8">Loading...</div>;
  const reqs = baseline.requirements || [];
  return (
    <div className="h-full overflow-auto p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="w-6 h-6" /> {baseline.name}</h1>
          <p className="text-sm text-gray-500 mt-1">{baseline.description}</p>
        </div>
        <div className="flex gap-2">
          {baseline.status === 'draft' && (
            <button onClick={() => publishMutation.mutate()}
              disabled={reqs.length === 0}
              className="btn-primary flex items-center gap-1.5 disabled:opacity-50">
              <Send className="w-4 h-4" /> Publish
            </button>)}
        </div>
      </div>
      {/* Requirements list */}
      <div className="space-y-2">
        {reqs.map((req: any) => (
          <div key={req.requirementId}
            className="border rounded-lg p-3 bg-white flex items-start gap-3">
            <div className="flex-1">
              {editingReq === req.requirementId ? (
                <div className="flex gap-2">
                  <input value={editText} onChange={(e) => setEditText(e.target.value)}
                    className="flex-1 border rounded px-2 py-1 text-sm" />
                  <button onClick={() => updateReqMutation.mutate({
                    reqId: req.requirementId, body: { text: editText }})}
                    className="text-green-600"><Save className="w-4 h-4" /></button>
                </div>
              ) : (
                <p className="text-sm text-gray-900">{req.text}</p>)}
              <div className="flex gap-2 mt-1">
                <span className={`px-2 py-0.5 rounded text-xs ${
                  criticalityColors[req.criticality] || 'bg-gray-100'}`}>
                  {req.criticality}</span>
                <span className="text-xs text-gray-400">{req.category}</span>
              </div>
            </div>
            <button onClick={() => { setEditingReq(req.requirementId); setEditText(req.text); }}
              className="text-gray-400 hover:text-gray-600"><Pencil className="w-4 h-4" /></button>
            <button onClick={() => deleteReqMutation.mutate(req.requirementId)}
              className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
          </div>))}
      </div>
      <button onClick={() => addReqMutation.mutate()}
        className="mt-4 flex items-center gap-1.5 text-sm text-primary-600 hover:text-primary-800">
        <Plus className="w-4 h-4" /> Add Requirement
      </button>
    </div>);
}
