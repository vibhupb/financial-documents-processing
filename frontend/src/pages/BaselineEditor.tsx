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
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [descValue, setDescValue] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadPhase, setUploadPhase] = useState<UploadPhase>('idle');
  const [uploadFileNames, setUploadFileNames] = useState<string[]>([]);
  const [uploadError, setUploadError] = useState('');
  const [extractedCount, setExtractedCount] = useState(0);
  const [uploadProgress, setUploadProgress] = useState('');
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
  const updateBaselineMutation = useMutation({
    mutationFn: (body: { name?: string; description?: string }) =>
      api.updateBaseline(baselineId!, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['baseline', baselineId] });
      setEditingName(false);
    },
  });
  const handleReferenceUpload = async (files: FileList) => {
    if (!baselineId || files.length === 0) return;
    const fileArray = Array.from(files);
    setUploadFileNames(fileArray.map(f => f.name));
    setUploadError('');
    try {
      // Step 1: Upload all files to S3
      setUploadPhase('uploading');
      const documentKeys: string[] = [];
      for (let i = 0; i < fileArray.length; i++) {
        const file = fileArray[i];
        setUploadProgress(`Uploading ${i + 1}/${fileArray.length}: ${file.name}`);
        const contentType = file.type || 'application/pdf';
        const { uploadUrl, fields, documentKey } = await api.uploadBaselineReference(
          baselineId, file.name, contentType
        );
        const formData = new FormData();
        Object.entries(fields).forEach(([key, value]) => formData.append(key, value));
        formData.append('file', file);
        const uploadResp = await fetch(uploadUrl, { method: 'POST', body: formData });
        if (!uploadResp.ok) {
          throw new Error(`Upload failed for ${file.name}: ${uploadResp.status}`);
        }
        documentKeys.push(documentKey);
      }

      // Step 2: Trigger PageIndex tree building for PDF files
      const pdfKeys = documentKeys.filter(k => k.toLowerCase().endsWith('.pdf'));
      if (pdfKeys.length > 0) {
        setUploadPhase('generating');
        setUploadProgress(`Building document structure for ${pdfKeys.length} PDF(s)...`);
        for (const key of pdfKeys) {
          await api.buildDocumentTree(key, 'baseline', baselineId!, key);
        }

        // Wait for trees to be built (poll generatingStatus)
        let treeAttempts = 0;
        const maxTreeAttempts = 60; // 5 min max
        while (treeAttempts < maxTreeAttempts) {
          await new Promise(resolve => setTimeout(resolve, 5000));
          treeAttempts++;
          setUploadProgress(
            `Building document structure... (${treeAttempts * 5}s)`
          );
          const updated = await api.getBaseline(baselineId!);
          if (updated?.baseline?.generatingStatus === 'tree_ready') {
            break;
          }
        }
      }

      // Step 3: Trigger async requirement extraction
      setUploadPhase('generating');
      setUploadProgress(`Extracting requirements from ${documentKeys.length} document(s) using Sonnet 4.6...`);
      await api.generateRequirementsMulti(baselineId!, documentKeys);

      // Step 4: Poll baseline until requirements appear
      const startReqs = data?.baseline?.requirements?.length || 0;
      let attempts = 0;
      const maxAttempts = 60;
      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        attempts++;
        setUploadProgress(
          `Extracting requirements... (${attempts * 5}s)`
        );
        const updated = await api.getBaseline(baselineId!);
        const newReqs = updated?.baseline?.requirements?.length || 0;
        const genStatus = updated?.baseline?.generatingStatus;
        if (genStatus === 'complete' || newReqs > startReqs) {
          setExtractedCount(newReqs - startReqs);
          break;
        }
        if (genStatus === 'error') {
          throw new Error('Requirement extraction failed');
        }
      }

      // Step 5: Refresh and show success
      setUploadPhase('success');
      queryClient.invalidateQueries({ queryKey: ['baseline', baselineId] });
      setTimeout(() => setUploadPhase('idle'), 4000);
    } catch (err: any) {
      setUploadPhase('error');
      setUploadError(err.message || 'Failed to process reference documents');
    }
  };

  const baseline = data?.baseline;
  if (isLoading || !baseline) return <div className="p-8">Loading...</div>;
  const reqs = baseline.requirements || [];
  return (
    <div className="h-full overflow-auto p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex-1 min-w-0">
          {editingName && baseline.status === 'draft' ? (
            <div className="space-y-2">
              <input
                autoFocus
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                className="text-2xl font-bold w-full border border-gray-300 rounded-lg px-3 py-1 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="Baseline name"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    updateBaselineMutation.mutate({ name: nameValue, description: descValue });
                  }
                  if (e.key === 'Escape') setEditingName(false);
                }}
              />
              <input
                value={descValue}
                onChange={(e) => setDescValue(e.target.value)}
                className="text-sm w-full border border-gray-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="Description (optional)"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    updateBaselineMutation.mutate({ name: nameValue, description: descValue });
                  }
                  if (e.key === 'Escape') setEditingName(false);
                }}
              />
              <div className="flex gap-2">
                <button
                  onClick={() => updateBaselineMutation.mutate({ name: nameValue, description: descValue })}
                  disabled={!nameValue.trim()}
                  className="btn-primary text-xs flex items-center gap-1 disabled:opacity-50"
                >
                  <Save className="w-3 h-3" /> Save
                </button>
                <button
                  onClick={() => setEditingName(false)}
                  className="text-xs text-gray-500 hover:text-gray-700"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div
              className={baseline.status === 'draft' ? 'cursor-pointer group' : ''}
              onClick={() => {
                if (baseline.status === 'draft') {
                  setNameValue(baseline.name);
                  setDescValue(baseline.description || '');
                  setEditingName(true);
                }
              }}
            >
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Shield className="w-6 h-6" /> {baseline.name}
                {baseline.status === 'draft' && (
                  <Pencil className="w-4 h-4 text-gray-300 group-hover:text-gray-500 transition-colors" />
                )}
              </h1>
              <p className="text-sm text-gray-500 mt-1">{baseline.description || 'Click to add description'}</p>
            </div>
          )}
        </div>
        <div className="flex gap-2 flex-shrink-0 ml-4">
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
            multiple
            accept=".pdf,.docx,.pptx,.xlsx,.xls"
            className="hidden"
            onChange={(e) => {
              const files = e.target.files;
              if (files && files.length > 0) handleReferenceUpload(files);
              e.target.value = '';
            }}
          />
          {uploadPhase === 'idle' && (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full border-2 border-dashed border-gray-300 rounded-lg p-6 flex flex-col items-center gap-2 text-gray-500 hover:border-primary-400 hover:text-primary-600 transition-colors cursor-pointer"
            >
              <Upload className="w-8 h-8" />
              <span className="text-sm font-medium">Upload reference documents (PDF, DOCX, PPTX, XLSX)</span>
              <span className="text-xs text-gray-400">Select one or more reference documents to extract requirements</span>
            </button>
          )}
          {uploadPhase === 'uploading' && (
            <div className="w-full border-2 border-dashed border-blue-300 rounded-lg p-6 flex items-center gap-3 bg-blue-50">
              <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
              <div>
                <p className="text-sm font-medium text-blue-700">{uploadProgress}</p>
                <p className="text-xs text-blue-500">{uploadFileNames.length} file{uploadFileNames.length !== 1 ? 's' : ''} selected</p>
              </div>
            </div>
          )}
          {uploadPhase === 'generating' && (
            <div className="w-full border-2 border-dashed border-amber-300 rounded-lg p-6 flex items-center gap-3 bg-amber-50">
              <Loader2 className="w-5 h-5 text-amber-500 animate-spin" />
              <div>
                <p className="text-sm font-medium text-amber-700">{uploadProgress}</p>
                <p className="text-xs text-amber-500">Using Claude Sonnet 4.6 for comprehensive requirement extraction</p>
              </div>
            </div>
          )}
          {uploadPhase === 'success' && (
            <div className="w-full border-2 border-dashed border-green-300 rounded-lg p-6 flex items-center gap-3 bg-green-50">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <p className="text-sm font-medium text-green-700">
                {extractedCount} requirement{extractedCount !== 1 ? 's' : ''} extracted from {uploadFileNames.length} document{uploadFileNames.length !== 1 ? 's' : ''}
              </p>
            </div>
          )}
          {uploadPhase === 'error' && (
            <div className="w-full border-2 border-dashed border-red-300 rounded-lg p-6 flex items-center justify-between bg-red-50">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-600" />
                <div>
                  <p className="text-sm font-medium text-red-700">Failed to process documents</p>
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
