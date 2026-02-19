import type {
  Document,
  Metrics,
  UploadResponse,
  AuditFile,
  ProcessingStatusResponse,
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
    fetchApi<ProcessingStatusResponse>(`/documents/${documentId}/status`),

  // Get presigned URL for viewing the PDF
  getDocumentPdfUrl: (documentId: string) =>
    fetchApi<{ documentId: string; pdfUrl: string; expiresIn: number }>(
      `/documents/${documentId}/pdf`
    ),

  // Upload
  createUploadUrl: (filename: string) =>
    fetchApi<UploadResponse>('/upload', {
      method: 'POST',
      body: JSON.stringify({ filename }),
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

  // Metrics
  getMetrics: () => fetchApi<Metrics>('/metrics'),

  // Plugin registry + config builder
  getPlugins: () => fetchApi<{ plugins: Record<string, any>; count: number }>('/plugins'),
  getPluginConfig: (pluginId: string) => fetchApi<any>(`/plugins/${pluginId}`),
  createPluginConfig: (data: any) => fetchApi<any>('/plugins', { method: 'POST', body: JSON.stringify(data) }),
  updatePluginConfig: (pluginId: string, data: any) => fetchApi<any>(`/plugins/${pluginId}`, { method: 'PUT', body: JSON.stringify(data) }),
  publishPlugin: (pluginId: string) => fetchApi<any>(`/plugins/${pluginId}/publish`, { method: 'POST' }),
  deletePlugin: (pluginId: string) => fetchApi<any>(`/plugins/${pluginId}`, { method: 'DELETE' }),

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
};
