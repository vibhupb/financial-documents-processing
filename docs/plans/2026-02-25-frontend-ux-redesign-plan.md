# Frontend UX Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace 9-route dashboard with a 5-route work-queue-first UI featuring real-time pipeline tracking, inline review actions, and unified upload.

**Architecture:** Consolidate Dashboard, Documents, Upload, Review, and ReviewDocument pages into a single Work Queue page (`/`) and an enhanced Document Detail page (`/documents/:id`). Backend Lambdas append processing events to DynamoDB; enriched status endpoint feeds the live pipeline tracker.

**Tech Stack:** React 18, TypeScript, TanStack Query, Tailwind CSS, react-dropzone, lucide-react, date-fns

---

## Task 1: Backend — Processing Events in DynamoDB

Each Lambda (router, extractor, normalizer) must append timestamped events to a `processingEvents` list attribute on the DynamoDB document record. The API status endpoint reads these back.

**Files:**
- Modify: `lambda/router/handler.py`
- Modify: `lambda/extractor/handler.py`
- Modify: `lambda/normalizer/handler.py`
- Modify: `lambda/api/handler.py`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/services/api.ts`

### Step 1: Create helper function for appending events

Add to each Lambda a helper that appends events to the DynamoDB record. Each Lambda already has a `dynamodb` resource and `TABLE_NAME`. Add this pattern near the top of each handler:

```python
import datetime

def append_processing_event(document_id: str, document_type: str, stage: str, message: str):
    """Append a timestamped event to the document's processingEvents list."""
    try:
        table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "financial-documents"))
        table.update_item(
            Key={"documentId": document_id, "documentType": document_type},
            UpdateExpression="SET processingEvents = list_append(if_not_exists(processingEvents, :empty), :event)",
            ExpressionAttributeValues={
                ":event": [{
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "stage": stage,
                    "message": message,
                }],
                ":empty": [],
            },
        )
    except Exception:
        pass  # Non-critical — don't fail processing if event logging fails
```

### Step 2: Add events to Router Lambda

In `lambda/router/handler.py`, add calls after key milestones in `lambda_handler()`:

- After classification completes: `append_processing_event(doc_id, doc_type, "router", f"Classified as {doc_type} (confidence: {confidence}%)")`
- After page targeting: `append_processing_event(doc_id, doc_type, "router", f"Targeted {targeted_pages}/{total_pages} pages across {len(sections)} sections")`
- After extraction plan built: `append_processing_event(doc_id, doc_type, "router", f"Extraction plan: {', '.join(section_names)}")`

Find the exact insertion points:
- Classification result is where `document_type` is determined from Bedrock response
- Page targeting is where `extractionPlan` is assembled
- The function returns the Step Functions payload at the end

### Step 3: Add events to Extractor Lambda

In `lambda/extractor/handler.py`, add calls in `extract_section_generic()`:

- On entry: `append_processing_event(doc_id, doc_type, "extractor", f"Processing section: {section_name} ({len(pages)} pages)")`
- On completion: `append_processing_event(doc_id, doc_type, "extractor", f"Extracted {field_count} fields from {section_name}")`

The `document_id` and `document_type` are available from the Step Functions input passed to the Lambda.

### Step 4: Add events to Normalizer Lambda

In `lambda/normalizer/handler.py`, add calls:

- On entry: `append_processing_event(doc_id, doc_type, "normalizer", "Normalizing extracted data...")`
- On completion: `append_processing_event(doc_id, doc_type, "normalizer", f"Normalized {field_count} fields, validation: {confidence}")`

### Step 5: Enrich the status endpoint

In `lambda/api/handler.py`, replace `get_processing_status()` (lines 369-399). The current implementation queries Step Functions `describe_execution`. Replace it to read from DynamoDB instead:

```python
def get_processing_status(document_id: str) -> dict[str, Any]:
    """Get processing status with stage details and events from DynamoDB."""
    table = dynamodb.Table(TABLE_NAME)

    # Try to find the document (we don't know the type, scan by documentId)
    response = table.query(
        KeyConditionExpression=Key("documentId").eq(document_id),
        Limit=1,
    )
    items = response.get("Items", [])
    if not items:
        return {"documentId": document_id, "status": "NOT_FOUND"}

    doc = items[0]
    status = doc.get("status", "PENDING")
    events = doc.get("processingEvents", [])

    # Build stage info from status enum
    stages = _build_stages(status, doc, events)

    result = {
        "documentId": document_id,
        "status": status,
        "documentType": doc.get("documentType"),
        "stages": stages,
        "events": events,
        "startedAt": doc.get("createdAt"),
        "completedAt": doc.get("updatedAt"),
    }
    return result


def _build_stages(status: str, doc: dict, events: list) -> dict:
    """Derive stage statuses from document status and events."""
    stage_order = ["PENDING", "CLASSIFIED", "EXTRACTING", "EXTRACTED", "NORMALIZING", "PROCESSED"]
    current_idx = stage_order.index(status) if status in stage_order else -1

    def stage_status(complete_at_idx: int, active_at_idx: int) -> str:
        if status == "FAILED":
            # Find which stage failed based on events
            return "FAILED" if current_idx <= active_at_idx else ("COMPLETED" if current_idx > complete_at_idx else "PENDING")
        if current_idx > complete_at_idx:
            return "COMPLETED"
        if current_idx >= active_at_idx:
            return "IN_PROGRESS"
        return "PENDING"

    classification = doc.get("classification", {})
    extraction_plan = doc.get("extractionPlan", [])

    stages = {
        "classification": {
            "status": stage_status(1, 0),
            "result": {
                "documentType": doc.get("documentType"),
                "confidence": classification.get("confidence"),
                "targetedPages": classification.get("targetedPages"),
                "totalPages": doc.get("totalPages"),
                "sections": [s.get("sectionId", "") for s in extraction_plan] if extraction_plan else [],
            } if current_idx >= 1 else None,
        },
        "extraction": {
            "status": stage_status(3, 2),
            "progress": {
                "completed": len([e for e in events if e.get("stage") == "extractor" and "Extracted" in e.get("message", "")]),
                "total": len(extraction_plan) if extraction_plan else None,
                "currentSection": next(
                    (e.get("message", "").split(": ", 1)[-1] for e in reversed(events) if e.get("stage") == "extractor" and "Processing" in e.get("message", "")),
                    None,
                ),
            } if current_idx >= 2 else None,
        },
        "normalization": {
            "status": stage_status(5, 4),
        },
    }
    return stages
```

### Step 6: Update `GET /documents` to include latest event

In the `list_documents()` function in `lambda/api/handler.py`, add `latestEvent` to each document in the response. This is the last entry from `processingEvents`:

```python
# In the document serialization loop:
events = doc.get("processingEvents", [])
if events:
    item["latestEvent"] = events[-1]
```

### Step 7: Update TypeScript types

In `frontend/src/types/index.ts`, add:

```typescript
interface ProcessingEvent {
  ts: string;
  stage: 'trigger' | 'router' | 'extractor' | 'normalizer';
  message: string;
}

interface StageInfo {
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';
  elapsed?: number;
  result?: {
    documentType?: string;
    confidence?: number;
    targetedPages?: number;
    totalPages?: number;
    sections?: string[];
  };
  progress?: {
    completed: number;
    total: number | null;
    currentSection: string | null;
  };
}

interface EnrichedStatusResponse {
  documentId: string;
  status: ProcessingStatus;
  documentType?: string;
  stages: {
    classification: StageInfo;
    extraction: StageInfo;
    normalization: StageInfo;
  };
  events: ProcessingEvent[];
  startedAt?: string;
  completedAt?: string;
}
```

Add `latestEvent?: ProcessingEvent` to the existing `Document` interface.

### Step 8: Update api.ts

Ensure `getProcessingStatus` returns the new `EnrichedStatusResponse` type:

```typescript
getProcessingStatus: (documentId: string) =>
  fetchApi<EnrichedStatusResponse>(`/documents/${documentId}/status`),
```

### Step 9: Deploy backend and verify

```bash
./scripts/deploy-backend.sh
```

Upload a test document and verify `GET /documents/{id}/status` returns stages + events.

### Step 10: Commit

```bash
git add lambda/router/handler.py lambda/extractor/handler.py lambda/normalizer/handler.py lambda/api/handler.py frontend/src/types/index.ts frontend/src/services/api.ts
git commit -m "feat: add processing events to DynamoDB and enrich status endpoint"
```

---

## Task 2: Frontend — New Components (UploadBar, MetricsStrip, PipelineTracker, LiveResultsStream)

Build the new UI components before wiring them into pages.

**Files:**
- Create: `frontend/src/components/UploadBar.tsx`
- Create: `frontend/src/components/MetricsStrip.tsx`
- Create: `frontend/src/components/PipelineTracker.tsx`
- Create: `frontend/src/components/LiveResultsStream.tsx`
- Create: `frontend/src/components/InlineReviewActions.tsx`
- Create: `frontend/src/components/UnknownTypePrompt.tsx`

### Step 1: UploadBar component

Slim horizontal drop zone using react-dropzone. Reuse upload logic from current `Upload.tsx`.

```typescript
// frontend/src/components/UploadBar.tsx
import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { api } from '../services/api';

type UploadPhase = 'idle' | 'uploading' | 'success' | 'error';

export default function UploadBar() {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<UploadPhase>('idle');
  const [fileName, setFileName] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const urlResponse = await api.createUploadUrl(file.name);
      await api.uploadFile(urlResponse.uploadUrl, urlResponse.fields, file);
      return urlResponse;
    },
    onSuccess: () => {
      setPhase('success');
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['metrics'] });
      // Auto-reset after 3 seconds
      setTimeout(() => setPhase('idle'), 3000);
    },
    onError: (err: Error) => {
      setPhase('error');
      setErrorMsg(err.message);
      setTimeout(() => setPhase('idle'), 5000);
    },
  });

  const onDrop = useCallback((files: File[]) => {
    const file = files[0];
    if (file) {
      setFileName(file.name);
      setPhase('uploading');
      setErrorMsg('');
      uploadMutation.mutate(file);
    }
  }, [uploadMutation]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
    disabled: phase === 'uploading',
  });

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-lg px-4 py-3 text-center cursor-pointer transition-all ${
        isDragActive ? 'border-blue-500 bg-blue-50' :
        phase === 'uploading' ? 'border-blue-300 bg-blue-50' :
        phase === 'success' ? 'border-green-300 bg-green-50' :
        phase === 'error' ? 'border-red-300 bg-red-50' :
        'border-gray-300 hover:border-gray-400'
      }`}
    >
      <input {...getInputProps()} />
      <div className="flex items-center justify-center gap-2 text-sm">
        {phase === 'idle' && (
          <>
            <Upload className="w-4 h-4 text-gray-400" />
            <span className="text-gray-500">
              {isDragActive ? 'Drop PDF here...' : 'Drop PDF here or click to upload'}
            </span>
          </>
        )}
        {phase === 'uploading' && (
          <>
            <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
            <span className="text-blue-600">Uploading {fileName}...</span>
          </>
        )}
        {phase === 'success' && (
          <>
            <CheckCircle className="w-4 h-4 text-green-500" />
            <span className="text-green-600">{fileName} uploaded — processing started</span>
          </>
        )}
        {phase === 'error' && (
          <>
            <AlertCircle className="w-4 h-4 text-red-500" />
            <span className="text-red-600">Upload failed: {errorMsg}</span>
          </>
        )}
      </div>
    </div>
  );
}
```

### Step 2: MetricsStrip component

Collapsible row of clickable metric pills. State persisted to localStorage.

```typescript
// frontend/src/components/MetricsStrip.tsx
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { api } from '../services/api';

interface MetricsStripProps {
  onFilterChange: (status: string) => void;
  activeFilter: string;
}

export default function MetricsStrip({ onFilterChange, activeFilter }: MetricsStripProps) {
  const [expanded, setExpanded] = useState(() => {
    return localStorage.getItem('metricsStrip') !== 'collapsed';
  });

  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: api.getMetrics,
    refetchInterval: 10000,
  });

  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    localStorage.setItem('metricsStrip', next ? 'expanded' : 'collapsed');
  };

  const counts = metrics?.statusCounts || {};
  const pills = [
    { label: 'Total', value: metrics?.totalDocuments || 0, filter: '' },
    { label: 'Processed', value: counts.PROCESSED || 0, filter: 'PROCESSED', color: 'bg-green-100 text-green-700' },
    { label: 'Needs Review', value: counts.PENDING_REVIEW || 0, filter: 'PENDING_REVIEW', color: 'bg-amber-100 text-amber-700' },
    { label: 'Failed', value: counts.FAILED || 0, filter: 'FAILED', color: 'bg-red-100 text-red-700' },
  ];

  return (
    <div className="mb-4">
      <button onClick={toggle} className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 mb-1">
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        Metrics
      </button>
      {expanded && (
        <div className="flex gap-2 flex-wrap">
          {pills.map((pill) => (
            <button
              key={pill.label}
              onClick={() => onFilterChange(pill.filter)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-all ${
                activeFilter === pill.filter
                  ? 'ring-2 ring-blue-500 ring-offset-1'
                  : ''
              } ${pill.color || 'bg-gray-100 text-gray-700'}`}
            >
              {pill.label}: {pill.value}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

### Step 3: PipelineTracker component

Horizontal 3-stage stepper with progress details.

```typescript
// frontend/src/components/PipelineTracker.tsx
import { CheckCircle, Circle, Loader2, XCircle } from 'lucide-react';
import type { StageInfo } from '../types';

interface PipelineTrackerProps {
  stages: {
    classification: StageInfo;
    extraction: StageInfo;
    normalization: StageInfo;
  };
}

const STAGE_META = [
  { key: 'classification' as const, label: 'Classification', color: 'blue' },
  { key: 'extraction' as const, label: 'Extraction', color: 'green' },
  { key: 'normalization' as const, label: 'Normalization', color: 'purple' },
];

function StageIcon({ status }: { status: string }) {
  switch (status) {
    case 'COMPLETED': return <CheckCircle className="w-6 h-6 text-green-500" />;
    case 'IN_PROGRESS': return <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />;
    case 'FAILED': return <XCircle className="w-6 h-6 text-red-500" />;
    default: return <Circle className="w-6 h-6 text-gray-300" />;
  }
}

function StageDetail({ stage, info }: { stage: typeof STAGE_META[number]; info: StageInfo }) {
  if (info.status === 'COMPLETED' && info.elapsed) {
    return <span className="text-xs text-gray-500">{info.elapsed.toFixed(1)}s</span>;
  }
  if (info.status === 'IN_PROGRESS') {
    if (info.progress?.total) {
      return <span className="text-xs text-blue-600">{info.progress.completed}/{info.progress.total} sections</span>;
    }
    if (info.result?.documentType) {
      return <span className="text-xs text-blue-600">{info.result.documentType}</span>;
    }
    return <span className="text-xs text-blue-600">Processing...</span>;
  }
  return null;
}

export default function PipelineTracker({ stages }: PipelineTrackerProps) {
  return (
    <div className="flex items-center justify-between py-6 px-4">
      {STAGE_META.map((stage, i) => {
        const info = stages[stage.key];
        return (
          <div key={stage.key} className="flex items-center flex-1">
            <div className="flex flex-col items-center gap-1">
              <StageIcon status={info.status} />
              <span className="text-sm font-medium text-gray-700">{stage.label}</span>
              <StageDetail stage={stage} info={info} />
            </div>
            {i < STAGE_META.length - 1 && (
              <div className={`flex-1 h-0.5 mx-4 ${
                info.status === 'COMPLETED' ? 'bg-green-400' : 'bg-gray-200'
              }`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
```

### Step 4: LiveResultsStream component

Scrolling event log, auto-scrolls to bottom.

```typescript
// frontend/src/components/LiveResultsStream.tsx
import { useEffect, useRef } from 'react';
import type { ProcessingEvent } from '../types';

interface LiveResultsStreamProps {
  events: ProcessingEvent[];
  startedAt?: string;
}

const STAGE_COLORS: Record<string, string> = {
  trigger: 'text-gray-500',
  router: 'text-blue-600',
  extractor: 'text-green-600',
  normalizer: 'text-purple-600',
};

function formatElapsed(eventTs: string, startedAt: string): string {
  const elapsed = (new Date(eventTs).getTime() - new Date(startedAt).getTime()) / 1000;
  const mins = Math.floor(elapsed / 60);
  const secs = Math.floor(elapsed % 60);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export default function LiveResultsStream({ events, startedAt }: LiveResultsStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  if (!events.length) {
    return (
      <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm text-gray-400">
        Waiting for processing events...
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm max-h-64 overflow-y-auto">
      {events.map((event, i) => (
        <div key={i} className="flex gap-2 py-0.5">
          <span className="text-gray-500 shrink-0">
            [{startedAt ? formatElapsed(event.ts, startedAt) : event.ts.split('T')[1]?.slice(0, 8)}]
          </span>
          <span className={`capitalize shrink-0 ${STAGE_COLORS[event.stage] || 'text-gray-400'}`}>
            {event.stage}:
          </span>
          <span className="text-gray-200">{event.message}</span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
```

### Step 5: InlineReviewActions component

Approve/reject/reprocess buttons for both the Work Queue rows and Document Detail page.

```typescript
// frontend/src/components/InlineReviewActions.tsx
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, X, RotateCw, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

interface InlineReviewActionsProps {
  documentId: string;
  status: string;
  reviewStatus?: string;
  compact?: boolean;          // true = icon-only for table rows
  onActionComplete?: () => void;
}

export default function InlineReviewActions({
  documentId, status, reviewStatus, compact = false, onActionComplete,
}: InlineReviewActionsProps) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['documents'] });
    queryClient.invalidateQueries({ queryKey: ['document', documentId] });
    queryClient.invalidateQueries({ queryKey: ['metrics'] });
    onActionComplete?.();
  };

  const approveMutation = useMutation({
    mutationFn: () => api.approveDocument(documentId, {
      reviewedBy: user?.email || 'reviewer',
      notes: '',
    }),
    onSuccess: invalidate,
  });

  const rejectMutation = useMutation({
    mutationFn: () => api.rejectDocument(documentId, {
      reviewedBy: user?.email || 'reviewer',
      notes: rejectReason,
      reprocess: false,
    }),
    onSuccess: () => { setShowReject(false); setRejectReason(''); invalidate(); },
  });

  const reprocessMutation = useMutation({
    mutationFn: () => api.reprocessDocument(documentId),
    onSuccess: invalidate,
  });

  const isLoading = approveMutation.isPending || rejectMutation.isPending || reprocessMutation.isPending;

  // Show reprocess for FAILED documents
  if (status === 'FAILED') {
    return (
      <button
        onClick={(e) => { e.stopPropagation(); reprocessMutation.mutate(); }}
        disabled={isLoading}
        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-orange-700 bg-orange-50 rounded hover:bg-orange-100"
      >
        {reprocessMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCw className="w-3 h-3" />}
        {!compact && 'Reprocess'}
      </button>
    );
  }

  // Show approve/reject for PENDING_REVIEW documents
  if (reviewStatus !== 'PENDING_REVIEW') return null;

  return (
    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={() => approveMutation.mutate()}
        disabled={isLoading}
        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-green-700 bg-green-50 rounded hover:bg-green-100"
      >
        {approveMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
        {!compact && 'Approve'}
      </button>

      {!showReject ? (
        <button
          onClick={() => setShowReject(true)}
          disabled={isLoading}
          className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-700 bg-red-50 rounded hover:bg-red-100"
        >
          <X className="w-3 h-3" />
          {!compact && 'Reject'}
        </button>
      ) : (
        <div className="flex items-center gap-1">
          <input
            type="text"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Reason..."
            className="text-xs border rounded px-2 py-1 w-32"
            autoFocus
          />
          <button
            onClick={() => rejectMutation.mutate()}
            disabled={isLoading || !rejectReason.trim()}
            className="text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
          >
            {rejectMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Send'}
          </button>
          <button onClick={() => setShowReject(false)} className="text-xs text-gray-500 hover:text-gray-700">
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
```

### Step 6: UnknownTypePrompt component

```typescript
// frontend/src/components/UnknownTypePrompt.tsx
import { useNavigate } from 'react-router-dom';
import { Puzzle, RotateCw } from 'lucide-react';

interface UnknownTypePromptProps {
  documentId: string;
  bestGuess?: string;
  confidence?: number;
}

export default function UnknownTypePrompt({ documentId, bestGuess, confidence }: UnknownTypePromptProps) {
  const navigate = useNavigate();

  return (
    <div className="border-2 border-dashed border-amber-300 rounded-lg p-6 bg-amber-50 text-center">
      <h3 className="text-lg font-semibold text-amber-800 mb-2">Unknown Document Type</h3>
      <p className="text-sm text-amber-700 mb-1">
        This document doesn't match any configured type.
      </p>
      {bestGuess && (
        <p className="text-xs text-amber-600 mb-4">
          Best guess: "{bestGuess}" at {((confidence || 0) * 100).toFixed(0)}% confidence
        </p>
      )}
      <div className="flex justify-center gap-3 mt-4">
        <button
          onClick={() => navigate(`/config/new?sampleDoc=${documentId}`)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          <Puzzle className="w-4 h-4" />
          Set Up New Plugin
        </button>
        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm font-medium"
        >
          <RotateCw className="w-4 h-4" />
          Retry Classification
        </button>
      </div>
    </div>
  );
}
```

### Step 7: Commit

```bash
git add frontend/src/components/UploadBar.tsx frontend/src/components/MetricsStrip.tsx frontend/src/components/PipelineTracker.tsx frontend/src/components/LiveResultsStream.tsx frontend/src/components/InlineReviewActions.tsx frontend/src/components/UnknownTypePrompt.tsx
git commit -m "feat: add new UI components for work queue redesign"
```

---

## Task 3: Frontend — Work Queue Page

Replace Dashboard, Documents, Upload, and Review with a single Work Queue page.

**Files:**
- Create: `frontend/src/pages/WorkQueue.tsx`
- Modify: `frontend/src/App.tsx`

### Step 1: Create WorkQueue page

```typescript
// frontend/src/pages/WorkQueue.tsx
import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Search, SlidersHorizontal, ChevronRight } from 'lucide-react';
import { format } from 'date-fns';
import { api } from '../services/api';
import UploadBar from '../components/UploadBar';
import MetricsStrip from '../components/MetricsStrip';
import StatusBadge from '../components/StatusBadge';
import InlineReviewActions from '../components/InlineReviewActions';
import type { Document } from '../types';

// Smart sort: Failed -> Processing -> Pending Review -> Completed
function needsAttentionSort(a: Document, b: Document): number {
  const priority: Record<string, number> = {
    FAILED: 0,
    PENDING: 1, CLASSIFIED: 1, EXTRACTING: 1, EXTRACTED: 1, NORMALIZING: 1, REPROCESSING: 1,
    PENDING_REVIEW: 2,
    PROCESSED: 3, APPROVED: 4, REJECTED: 5, SKIPPED: 6,
  };
  const pa = priority[a.reviewStatus || a.status] ?? priority[a.status] ?? 9;
  const pb = priority[b.reviewStatus || b.status] ?? priority[b.status] ?? 9;
  if (pa !== pb) return pa - pb;
  // Within same priority: processing = oldest first, others = newest first
  if (pa <= 1) return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
  return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
}

type SortMode = 'attention' | 'newest' | 'oldest' | 'cost';

export default function WorkQueue() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('attention');

  const { data, isLoading } = useQuery({
    queryKey: ['documents', statusFilter],
    queryFn: () => api.listDocuments({ status: statusFilter || undefined, limit: 100 }),
    refetchInterval: (query) => {
      const docs = query.state.data?.documents || [];
      const hasProcessing = docs.some((d: Document) =>
        ['PENDING', 'CLASSIFIED', 'EXTRACTING', 'EXTRACTED', 'NORMALIZING', 'REPROCESSING'].includes(d.status)
      );
      return hasProcessing ? 5000 : 15000;
    },
  });

  const { data: pluginsData } = useQuery({
    queryKey: ['plugins'],
    queryFn: api.getPlugins,
    staleTime: 60000,
  });

  const documents = useMemo(() => {
    let docs = data?.documents || [];

    // Search filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      docs = docs.filter((d) =>
        d.documentId.toLowerCase().includes(q) ||
        (d.fileName || '').toLowerCase().includes(q)
      );
    }

    // Type filter
    if (typeFilter) {
      docs = docs.filter((d) => d.documentType === typeFilter);
    }

    // Sort
    switch (sortMode) {
      case 'attention': return [...docs].sort(needsAttentionSort);
      case 'newest': return [...docs].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
      case 'oldest': return [...docs].sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());
      case 'cost': return [...docs].sort((a, b) => (b.processingCost?.totalCost || 0) - (a.processingCost?.totalCost || 0));
      default: return docs;
    }
  }, [data?.documents, searchQuery, typeFilter, sortMode]);

  const pluginTypes = Object.entries(pluginsData?.plugins || {}).map(([id, p]: [string, any]) => ({
    id: id.toUpperCase(),
    name: p.name,
  }));

  const isProcessing = (status: string) =>
    ['PENDING', 'CLASSIFIED', 'EXTRACTING', 'EXTRACTED', 'NORMALIZING', 'REPROCESSING'].includes(status);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Work Queue</h1>

      {/* Upload Bar */}
      <UploadBar />

      {/* Metrics Strip */}
      <div className="mt-4">
        <MetricsStrip onFilterChange={setStatusFilter} activeFilter={statusFilter} />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by ID or filename..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="PENDING">Processing</option>
          <option value="PENDING_REVIEW">Needs Review</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
          <option value="FAILED">Failed</option>
        </select>

        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
        >
          <option value="">All Types</option>
          {pluginTypes.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>

        <select
          value={sortMode}
          onChange={(e) => setSortMode(e.target.value as SortMode)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
        >
          <option value="attention">Needs Attention</option>
          <option value="newest">Newest First</option>
          <option value="oldest">Oldest First</option>
          <option value="cost">Highest Cost</option>
        </select>
      </div>

      {/* Document List */}
      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Loading documents...</div>
      ) : documents.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg font-medium">No documents yet</p>
          <p className="text-sm mt-1">Drop a PDF above to get started</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
                <th className="px-4 py-3">Document</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Cost</th>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {documents.map((doc) => (
                <tr
                  key={doc.documentId}
                  onClick={() => navigate(`/documents/${doc.documentId}`)}
                  className={`cursor-pointer hover:bg-gray-50 transition-colors ${
                    doc.reviewStatus === 'PENDING_REVIEW' ? 'border-l-4 border-l-amber-400' :
                    doc.status === 'FAILED' ? 'border-l-4 border-l-red-400' :
                    isProcessing(doc.status) ? 'border-l-4 border-l-blue-400' :
                    'border-l-4 border-l-transparent'
                  }`}
                >
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-gray-900">
                      {doc.fileName || doc.documentId.slice(0, 8) + '...'}
                    </div>
                    <div className="text-xs text-gray-500">{doc.documentId.slice(0, 8)}</div>
                    {isProcessing(doc.status) && doc.latestEvent && (
                      <div className="flex items-center gap-1 mt-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                        <span className="text-xs text-blue-600 truncate max-w-48">
                          {doc.latestEvent.message}
                        </span>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {doc.documentType?.replace(/_/g, ' ') || '-'}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={doc.reviewStatus || doc.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {doc.processingCost?.totalCost ? `$${doc.processingCost.totalCost.toFixed(2)}` : '-'}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {format(new Date(doc.createdAt), 'MMM d, h:mm a')}
                  </td>
                  <td className="px-4 py-3 text-right">
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
        </div>
      )}
    </div>
  );
}
```

### Step 2: Update App.tsx routing

Replace the current 9 routes with 5. Remove imports for deleted pages.

In `frontend/src/App.tsx`:
- Remove imports: `Dashboard`, `Documents`, `Upload`, `Review`, `ReviewDocument`
- Add import: `WorkQueue`
- Replace routes:
  - `/` → `<WorkQueue />`
  - `/documents/:documentId` → `<DocumentDetail />` (keep)
  - `/config` → `<PluginList />` (keep)
  - `/config/new` → `<PluginWizard />` (keep)
  - `/login` → `<Login />` (keep)
- Remove routes: `/documents`, `/upload`, `/review`, `/review/:documentId`

### Step 3: Update Layout sidebar

In `frontend/src/components/Layout.tsx`, update the nav items:

- Remove: Dashboard, Documents, Upload, Review links
- Add: "Work Queue" link to `/` with badge for attention count
- Keep: Plugin Studio link to `/config`

The sidebar badge should show the count of failed + pending review documents. Fetch from the metrics query (already cached by MetricsStrip).

### Step 4: Commit

```bash
git add frontend/src/pages/WorkQueue.tsx frontend/src/App.tsx frontend/src/components/Layout.tsx
git commit -m "feat: add Work Queue page, update routing and sidebar"
```

---

## Task 4: Frontend — Rebuild Document Detail Page

Replace the current DocumentDetail with processing view (pipeline tracker + live stream) and review view (PDF + data + review actions).

**Files:**
- Modify: `frontend/src/pages/DocumentDetail.tsx`
- Modify: `frontend/src/components/DocumentViewer.tsx`

### Step 1: Rewrite DocumentDetail.tsx

The page should have three modes:

**Mode A — Processing View** (status PENDING through NORMALIZING):
- Top bar with document info and back arrow
- `PipelineTracker` component showing 3 stages
- `LiveResultsStream` component showing events
- Auto-transitions to Mode B on completion

**Mode B — Review/Completed View** (status PROCESSED, PENDING_REVIEW, APPROVED, REJECTED):
- Top bar with document info, status badge, cost, time
- `DocumentViewer` component (existing split PDF + data)
- Sticky bottom bar with `InlineReviewActions` + "Next in Queue" button (for PENDING_REVIEW)

**Mode C — Unknown Type** (status FAILED with unknown type classification):
- Shows pipeline tracker up to Classification
- `UnknownTypePrompt` component

Key changes from current implementation:
- Use the enriched `getProcessingStatus` endpoint for stages + events
- Poll every 3s during processing (current: 5s)
- Fetch PDF URL when status first reaches PROCESSED (existing logic, keep)
- Add "Next in Queue" navigation: query `listDocuments({ status: 'PENDING_REVIEW' })`, find next after current

### Step 2: Update DocumentViewer to accept review actions

In `frontend/src/components/DocumentViewer.tsx`, add an optional `reviewBar` prop:

```typescript
interface DocumentViewerProps {
  document: Document;
  pdfUrl: string;
  className?: string;
  reviewBar?: React.ReactNode;  // Rendered as sticky bar at bottom
}
```

Render `reviewBar` as a fixed-bottom bar inside the viewer when provided.

### Step 3: Commit

```bash
git add frontend/src/pages/DocumentDetail.tsx frontend/src/components/DocumentViewer.tsx
git commit -m "feat: rebuild Document Detail with pipeline tracker and review actions"
```

---

## Task 5: Frontend — Update Plugin Studio

Minor updates to Plugin Studio for card grid and integration with unknown-type flow.

**Files:**
- Modify: `frontend/src/pages/PluginList.tsx`
- Modify: `frontend/src/pages/PluginWizard.tsx`

### Step 1: Update PluginList to card grid

Replace the current table layout in `PluginList.tsx` with a responsive card grid. Each card shows: plugin name + version, section/query counts, cost budget, PII flag, status badge (PUBLISHED/DRAFT/Built-in), and aggregate stats if available.

Use CSS grid: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4`

### Step 2: Update PluginWizard for sampleDoc parameter

In `PluginWizard.tsx`, read `sampleDoc` query parameter from URL:

```typescript
const [searchParams] = useSearchParams();
const sampleDocId = searchParams.get('sampleDoc');
```

If `sampleDoc` is present:
- Auto-fetch the document's S3 key from `getDocument(sampleDocId)`
- Skip the "upload sample" step and jump to "AI Analysis"
- Show "Publish & Reprocess" button on the final step instead of just "Publish"
- After publish, call `reprocessDocument(sampleDocId)` and navigate to `/documents/${sampleDocId}`

### Step 3: Commit

```bash
git add frontend/src/pages/PluginList.tsx frontend/src/pages/PluginWizard.tsx
git commit -m "feat: update Plugin Studio with card grid and sampleDoc flow"
```

---

## Task 6: Cleanup — Remove Deprecated Pages

Delete the old pages that are no longer routed.

**Files:**
- Delete: `frontend/src/pages/Dashboard.tsx`
- Delete: `frontend/src/pages/Documents.tsx`
- Delete: `frontend/src/pages/Upload.tsx`
- Delete: `frontend/src/pages/Review.tsx`
- Delete: `frontend/src/pages/ReviewDocument.tsx`
- Delete: `frontend/src/components/MetricCard.tsx` (only used by Dashboard)

### Step 1: Verify no imports reference deleted files

```bash
cd frontend && grep -r "Dashboard\|Documents\|Upload\|Review\|MetricCard" src/ --include='*.tsx' --include='*.ts' | grep -v node_modules | grep import
```

Should only show WorkQueue and DocumentDetail imports. Fix any remaining references.

### Step 2: Delete files

```bash
rm frontend/src/pages/Dashboard.tsx
rm frontend/src/pages/Documents.tsx
rm frontend/src/pages/Upload.tsx
rm frontend/src/pages/Review.tsx
rm frontend/src/pages/ReviewDocument.tsx
rm frontend/src/components/MetricCard.tsx
```

### Step 3: Build and verify

```bash
cd frontend && npm run build
```

Must complete with zero errors.

### Step 4: Commit

```bash
git add -u frontend/src/
git commit -m "refactor: remove deprecated Dashboard, Documents, Upload, Review pages"
```

---

## Task 7: Deploy and End-to-End Verification

### Step 1: Deploy backend (Lambda changes for processing events)

```bash
./scripts/deploy-backend.sh
```

### Step 2: Deploy frontend

```bash
./scripts/deploy-frontend.sh
```

### Step 3: Clean test data

```bash
./scripts/cleanup.sh --force
```

### Step 4: End-to-end test

1. Open CloudFront URL — should land on Work Queue (empty state)
2. Drop a test PDF on the upload bar — should show uploading, then PENDING row
3. Click the processing row — should show PipelineTracker + LiveResultsStream
4. Watch events stream in — classification, extraction sections, normalization
5. On completion — auto-transition to Review view with PDF + extracted data
6. Click "Approve" — should update status to APPROVED
7. Back to Work Queue — row shows APPROVED badge
8. Upload another doc — verify polling detects it at 5s intervals

### Step 5: Final commit

```bash
git add -A
git commit -m "feat: complete frontend UX redesign — work queue-first architecture"
```
