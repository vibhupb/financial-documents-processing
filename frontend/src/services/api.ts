import type {
  Document,
  Metrics,
  UploadResponse,
  AuditFile,
  EnrichedStatusResponse,
  ReviewQueueResponse,
  ReviewDocumentResponse,
  ApproveRejectRequest,
  CorrectFieldsRequest,
  ReviewActionResponse,
  ReviewStatus,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

export const api = {
  // Documents
  listDocuments: (params?: { status?: string; limit?: number; lastKey?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.lastKey) searchParams.set('lastKey', params.lastKey);

    const query = searchParams.toString();
    return fetchApi<{ documents: Document[]; count: number; lastKey?: string }>(
      `/documents${query ? `?${query}` : ''}`
    );
  },

  getDocument: (documentId: string) =>
    fetchApi<{ document: Document } | { error: string; documentId: string }>(`/documents/${documentId}`),

  getDocumentAudit: (documentId: string) =>
    fetchApi<{ documentId: string; auditFiles: AuditFile[] }>(`/documents/${documentId}/audit`),

  getProcessingStatus: (documentId: string) =>
    fetchApi<EnrichedStatusResponse>(`/documents/${documentId}/status`),

  // Get presigned URL for viewing the PDF
  getDocumentPdfUrl: (documentId: string) =>
    fetchApi<{ documentId: string; pdfUrl: string; expiresIn: number }>(
      `/documents/${documentId}/pdf`
    ),

  // Upload
  createUploadUrl: (filename: string, processingMode: string = 'extract', baselineIds?: string[], pluginId?: string) =>
    fetchApi<UploadResponse>('/upload', {
      method: 'POST',
      body: JSON.stringify({
        filename,
        processingMode,
        ...(baselineIds?.length ? { baselineIds } : {}),
        ...(pluginId ? { pluginId } : {}),
      }),
    }),

  uploadFile: async (uploadUrl: string, fields: Record<string, string>, file: File) => {
    // Use FormData for presigned POST upload
    const formData = new FormData();

    // Add all the presigned POST fields first (order matters!)
    Object.entries(fields).forEach(([key, value]) => {
      formData.append(key, value);
    });

    // Add the file last (must be after the fields)
    formData.append('file', file);

    const response = await fetch(uploadUrl, {
      method: 'POST',
      body: formData,
      // Don't set Content-Type header - browser sets it automatically with boundary
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Upload failed:', response.status, errorText);
      throw new Error(`Upload failed: ${response.status}`);
    }

    return true;
  },

  // PageIndex
  getDocumentTree: (documentId: string) =>
    fetchApi<{ documentId: string; pageIndexTree: any; status: string }>(
      `/documents/${documentId}/tree`
    ),

  triggerExtraction: (documentId: string) =>
    fetchApi<{ documentId: string; status: string; executionArn?: string }>(
      `/documents/${documentId}/extract`,
      { method: 'POST' }
    ),

  askDocument: (documentId: string, question: string) =>
    fetchApi<{ answer: string; sourceNodes: string[]; sourcePages: number[]; question: string }>(
      `/documents/${documentId}/ask`,
      { method: 'POST', body: JSON.stringify({ question }) }
    ),

  // Metrics
  getMetrics: () => fetchApi<Metrics>('/metrics'),

  // Plugin registry + config builder
  getPlugins: () => fetchApi<{ plugins: Record<string, any>; count: number }>('/plugins'),
  getPluginConfig: (pluginId: string) => fetchApi<any>(`/plugins/${pluginId}`),
  createPluginConfig: (data: any) => fetchApi<any>('/plugins', { method: 'POST', body: JSON.stringify(data) }),
  updatePluginConfig: (pluginId: string, data: any) => fetchApi<any>(`/plugins/${pluginId}`, { method: 'PUT', body: JSON.stringify(data) }),
  publishPlugin: (pluginId: string) => fetchApi<any>(`/plugins/${pluginId}/publish`, { method: 'POST' }),
  deletePlugin: (pluginId: string) => fetchApi<any>(`/plugins/${pluginId}`, { method: 'DELETE' }),
  analyzeSample: (data: { s3Key: string; bucket: string }) =>
    fetchApi<any>('/plugins/analyze', { method: 'POST', body: JSON.stringify(data) }),
  generatePluginConfig: (data: { text: string; formFields: any; name: string; pageCount: number }) =>
    fetchApi<any>('/plugins/generate', { method: 'POST', body: JSON.stringify(data) }),
  refinePluginConfig: (data: { config: any; instruction: string }) =>
    fetchApi<any>('/plugins/refine', { method: 'POST', body: JSON.stringify(data) }),
  testPlugin: (pluginId: string) =>
    fetchApi<any>(`/plugins/${pluginId}/test`, { method: 'POST' }),

  // Review workflow
  listReviewQueue: (params?: { status?: ReviewStatus; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.limit) searchParams.set('limit', String(params.limit));

    const query = searchParams.toString();
    return fetchApi<ReviewQueueResponse>(`/review${query ? `?${query}` : ''}`);
  },

  getDocumentForReview: (documentId: string) =>
    fetchApi<ReviewDocumentResponse>(`/review/${documentId}`),

  approveDocument: (documentId: string, data: ApproveRejectRequest) =>
    fetchApi<ReviewActionResponse>(`/review/${documentId}/approve`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  rejectDocument: (documentId: string, data: ApproveRejectRequest) =>
    fetchApi<ReviewActionResponse>(`/review/${documentId}/reject`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  correctDocumentFields: (documentId: string, data: CorrectFieldsRequest) =>
    fetchApi<ReviewActionResponse>(`/documents/${documentId}/fields`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  reprocessDocument: (documentId: string) =>
    fetchApi<{ documentId: string; executionArn: string; status: string; message: string }>(
      `/documents/${documentId}/reprocess`,
      { method: 'POST', body: JSON.stringify({ force: true }) }
    ),

  // Compliance Baselines
  listBaselines: (params?: { status?: string }) =>
    fetchApi<{ baselines: any[] }>(`/baselines${params?.status ? `?status=${params.status}` : ''}`),

  createBaseline: (body: { name: string; description: string; pluginIds?: string[] }) =>
    fetchApi<any>('/baselines', { method: 'POST', body: JSON.stringify(body) }),

  getBaseline: (baselineId: string) =>
    fetchApi<{ baseline: any }>(`/baselines/${baselineId}`),

  updateBaseline: (baselineId: string, body: any) =>
    fetchApi<any>(`/baselines/${baselineId}`, { method: 'PUT', body: JSON.stringify(body) }),

  publishBaseline: (baselineId: string) =>
    fetchApi<any>(`/baselines/${baselineId}/publish`, { method: 'POST' }),

  addRequirement: (baselineId: string, body: any) =>
    fetchApi<any>(`/baselines/${baselineId}/requirements`, { method: 'POST', body: JSON.stringify(body) }),

  updateRequirement: (baselineId: string, reqId: string, body: any) =>
    fetchApi<any>(`/baselines/${baselineId}/requirements/${reqId}`, { method: 'PUT', body: JSON.stringify(body) }),

  deleteRequirement: (baselineId: string, reqId: string) =>
    fetchApi<any>(`/baselines/${baselineId}/requirements/${reqId}`, { method: 'DELETE' }),

  // Compliance Reports
  getComplianceReports: (documentId: string) =>
    fetchApi<{ reports: any[] }>(`/documents/${documentId}/compliance`),

  submitComplianceReview: (documentId: string, reportId: string, body: any) =>
    fetchApi<any>(`/documents/${documentId}/compliance/${reportId}/review`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // Baseline reference document upload
  uploadBaselineReference: (baselineId: string, filename: string, contentType: string = 'application/pdf') =>
    fetchApi<{ uploadUrl: string; fields: Record<string, string>; documentKey: string; baselineId: string }>(
      `/baselines/${baselineId}/upload-reference`,
      { method: 'POST', body: JSON.stringify({ filename, contentType }) }
    ),

  generateRequirements: (baselineId: string, documentKey: string, sourceFormat?: string) =>
    fetchApi<{ baselineId: string; requirementCount: number; categories: string[]; requirements: any[] }>(
      `/baselines/${baselineId}/generate-requirements`,
      { method: 'POST', body: JSON.stringify({ documentKey, sourceFormat }) }
    ),

  generateRequirementsMulti: (baselineId: string, documentKeys: string[]) =>
    fetchApi<{ baselineId: string; requirementCount: number; totalRequirements: number; categories: string[]; requirements: any[]; documentsProcessed: number }>(
      `/baselines/${baselineId}/generate-requirements`,
      { method: 'POST', body: JSON.stringify({ documentKeys }) }
    ),

  // PageIndex tree building (used by Plugin Builder for section detection)
  buildDocumentTree: (s3Key: string, entityType: string, entityId: string, entityDocKey?: string) =>
    fetchApi<{ status: string; message: string }>('/documents/build-tree', {
      method: 'POST',
      body: JSON.stringify({ s3Key, entityType, entityId, entityDocKey: entityDocKey || s3Key }),
    }),
};
