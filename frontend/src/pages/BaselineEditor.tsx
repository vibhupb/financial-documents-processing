import { useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { Shield, Plus, Trash2, Save, Send, Pencil, Upload, Loader2, CheckCircle, AlertCircle } from 'lucide-react';

const criticalityColors: Record<string, string> = {
  'must-have': 'bg-red-100 text-red-700',
  'should-have': 'bg-yellow-100 text-yellow-700',
  'nice-to-have': 'bg-blue-100 text-blue-700',
};

type UploadPhase = 'idle' | 'uploading' | 'generating' | 'success' | 'error';

export default function BaselineEditor() {
  const { baselineId } = useParams<{ baselineId: string }>();
  const queryClient = useQueryClient();
  const [editingReq, setEditingReq] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadPhase, setUploadPhase] = useState<UploadPhase>('idle');
  const [uploadFileName, setUploadFileName] = useState('');
  const [uploadError, setUploadError] = useState('');
  const [extractedCount, setExtractedCount] = useState(0);
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
  const handleReferenceUpload = async (file: File) => {
    if (!baselineId) return;
    setUploadFileName(file.name);
    setUploadError('');
    try {
      // Step 1: Get presigned URL
      setUploadPhase('uploading');
      const contentType = file.type || 'application/pdf';
      const { uploadUrl, fields, documentKey } = await api.uploadBaselineReference(
        baselineId, file.name, contentType
      );

      // Step 2: Upload file to S3
      const formData = new FormData();
      Object.entries(fields).forEach(([key, value]) => formData.append(key, value));
      formData.append('file', file);
      const uploadResp = await fetch(uploadUrl, { method: 'POST', body: formData });
      if (!uploadResp.ok) {
        throw new Error(`Upload failed: ${uploadResp.status}`);
      }

      // Step 3: Generate requirements from the uploaded document
      setUploadPhase('generating');
      const ext = file.name.split('.').pop()?.toLowerCase();
      const formatMap: Record<string, string> = { pdf: 'pdf', docx: 'docx', pptx: 'pptx' };
      const sourceFormat = formatMap[ext || ''] || 'pdf';
      const result = await api.generateRequirements(baselineId, documentKey, sourceFormat);
      setExtractedCount(result.requirementCount);

      // Step 4: Refresh baseline data
      setUploadPhase('success');
      queryClient.invalidateQueries({ queryKey: ['baseline', baselineId] });
      setTimeout(() => setUploadPhase('idle'), 4000);
    } catch (err: any) {
      setUploadPhase('error');
      setUploadError(err.message || 'Failed to process reference document');
    }
  };

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
      {/* Generate from Document */}
      {baseline.status === 'draft' && (
        <div className="mb-6">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.pptx"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleReferenceUpload(file);
              e.target.value = '';
            }}
          />
          {uploadPhase === 'idle' && (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full border-2 border-dashed border-gray-300 rounded-lg p-6 flex flex-col items-center gap-2 text-gray-500 hover:border-primary-400 hover:text-primary-600 transition-colors cursor-pointer"
            >
              <Upload className="w-8 h-8" />
              <span className="text-sm font-medium">Upload compliance document (PDF, DOCX, PPTX)</span>
              <span className="text-xs text-gray-400">Auto-extract requirements from a reference document</span>
            </button>
          )}
          {uploadPhase === 'uploading' && (
            <div className="w-full border-2 border-dashed border-blue-300 rounded-lg p-6 flex items-center gap-3 bg-blue-50">
              <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
              <div>
                <p className="text-sm font-medium text-blue-700">Uploading {uploadFileName}...</p>
                <p className="text-xs text-blue-500">Sending file to S3</p>
              </div>
            </div>
          )}
          {uploadPhase === 'generating' && (
            <div className="w-full border-2 border-dashed border-amber-300 rounded-lg p-6 flex items-center gap-3 bg-amber-50">
              <Loader2 className="w-5 h-5 text-amber-500 animate-spin" />
              <div>
                <p className="text-sm font-medium text-amber-700">Extracting requirements from {uploadFileName}...</p>
                <p className="text-xs text-amber-500">Parsing document and generating requirements via LLM</p>
              </div>
            </div>
          )}
          {uploadPhase === 'success' && (
            <div className="w-full border-2 border-dashed border-green-300 rounded-lg p-6 flex items-center gap-3 bg-green-50">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <p className="text-sm font-medium text-green-700">
                {extractedCount} requirement{extractedCount !== 1 ? 's' : ''} extracted from {uploadFileName}
              </p>
            </div>
          )}
          {uploadPhase === 'error' && (
            <div className="w-full border-2 border-dashed border-red-300 rounded-lg p-6 flex items-center justify-between bg-red-50">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-600" />
                <div>
                  <p className="text-sm font-medium text-red-700">Failed to process {uploadFileName}</p>
                  <p className="text-xs text-red-500">{uploadError}</p>
                </div>
              </div>
              <button
                onClick={() => setUploadPhase('idle')}
                className="text-sm text-red-600 hover:text-red-800 underline"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      )}

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
