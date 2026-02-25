# Frontend UX Redesign — Work Queue-First Architecture

**Date:** 2026-02-25
**Status:** Design Approved
**Author:** Vibhu + Claude

---

## Problem Statement

The current frontend has 9 routes and 6+ pages that create confusion and gaps:

1. **Documents vs Review confusion** — Two separate list views for the same data at different lifecycle stages. Users ask "why are there two lists?"
2. **No real-time processing visibility** — 30s polling, faked progress bars, no indication of which pipeline stage a document is in
3. **Stale data everywhere** — Review page is manual-refresh only, Dashboard is 30s behind reality
4. **Dead-end flows** — After upload, user must manually navigate. After review, no "next document" button. Upload and work queues are disconnected pages
5. **Unused Dashboard** — Metrics page that nobody lands on to do actual work

## Design Principles

- **Work queue IS the app** — The landing page is the unified document list with upload built in
- **Full processing transparency** — Show intermediate results as they arrive (classification result, pages targeted, sections extracted)
- **One click to act** — Approve, reject, reprocess without leaving the list. Deep-dive is one click away
- **No stale data** — Aggressive polling while work is in-flight, relaxed when idle

## User Personas

Both roles are exercised by the same user during testing/setup. Role-based visibility applies later via Cognito groups.

- **Analyst** — Uploads documents, creates plugin configs for new document types, monitors processing
- **Reviewer** — Reviews extraction quality, approves/rejects, handles failures

## Navigation & Routing

### Current (9 routes)

```
/            → Dashboard
/documents   → Document list
/documents/:id → Document detail
/upload      → Upload page
/review      → Review queue
/review/:id  → Review document
/config      → Plugin list
/config/new  → Plugin wizard
/login       → Login
```

### New (5 routes)

```
/              → Work Queue (the app)
/documents/:id → Document Detail
/config        → Plugin Studio
/config/new    → Plugin Wizard
/login         → Login
```

### Sidebar

- Logo + "FinDocs"
- **Work Queue** — badge showing count of items needing attention (failed + pending review)
- **Plugin Studio** — admin only
- User info + role indicator + Sign Out

---

## Page 1: Work Queue (`/`)

The single most important page. Replaces Dashboard, Documents, Upload, and Review. Three zones stacked vertically.

### Zone 1 — Upload Bar (top, always visible)

- Slim horizontal drop zone: "Drop PDF here or click to upload"
- Single line, not a big box. Unobtrusive but always accessible
- On file drop: expands briefly to show upload progress, then collapses. New document appears at top of list with PENDING status
- No separate success screen — the document row IS the confirmation

### Zone 2 — Metrics Strip (collapsible, below upload bar)

- Single row of 4 compact pills: `Total: 142` | `Processed: 130` | `Needs Review: 8` | `Failed: 4`
- Click any pill to apply that status filter to the list below
- Collapsed by default after first visit (remembered in localStorage)
- Auto-refreshes every 10s

### Zone 3 — Document List (main content)

**Columns:**

| Document | Type | Status | Confidence | Cost | Time | Actions |
|----------|------|--------|------------|------|------|---------|

**Smart sort order** (default: "Needs Attention"):

1. Failed (newest first)
2. Processing (oldest first — longest-running on top)
3. Pending Review (oldest first — longest-waiting on top)
4. Approved/Completed (newest first)

**Filters** (horizontal bar above table):

- Search — by document ID or filename
- Status dropdown — All / Processing / Needs Review / Approved / Rejected / Failed
- Document Type dropdown — populated from `GET /plugins`
- Sort — Needs Attention (default) / Newest / Oldest / Cost (high to low)

**Row behavior:**

- Processing documents show animated progress indicator inline (pulsing dot + current stage text: "Extracting section 3/7...")
- Pending Review rows have subtle highlight/accent border
- Failed rows show red accent
- Click any row to navigate to Document Detail

**Inline quick actions** (right side of each row):

- Pending Review: `Approve` / `Reject` buttons (approve is one-click, reject opens small popover for reason)
- Failed: `Reprocess` button
- Processing: no actions (watch the progress)
- Approved/Completed: no actions

### Polling Strategy

- 5s refresh while any document is in Processing state (fetches only processing rows, merges into cache)
- 15s refresh when nothing is processing
- Inline quick actions use optimistic updates via TanStack Query

---

## Page 2: Document Detail (`/documents/:id`)

Two distinct modes depending on document state.

### Mode A: Processing View

Shown when status is PENDING through NORMALIZING.

**Top bar:** Document filename, ID (truncated), document type (if classified), back arrow to Work Queue

**Live Pipeline Tracker** — horizontal stepper with 3 stages:

```
[1. Classification] ———> [2. Extraction] ———> [3. Normalization]
     ✓ Complete (2.3s)      ● Active (12/47)       ○ Pending
```

Each stage shows:
- Icon + label + status (pending / active / complete / failed)
- Active stage shows progress detail: "Extracting page 12 of 47"
- Completed stages show elapsed time
- Failed stage shows error message inline

**Live Results Stream** — scrolling log below the stepper:

```
[00:00] Trigger: Document received, SHA-256: a3f8c2...
[00:02] Router: Classified as "Credit Agreement" (confidence: 97%)
[00:02] Router: Identified 7 sections across 156 pages
[00:03] Router: Targeted 42 pages for extraction (73% cost savings)
[00:05] Extractor: Processing section 1/7 — "Agreement Info" (pages 1-8)
[00:12] Extractor: Processing section 2/7 — "Interest Rates" (pages 9-15)
...
[00:34] Normalizer: Structuring extracted data into 68 fields
[00:38] Complete: 68 fields extracted, cost $0.42, validation confidence HIGH
```

- Auto-scrolls to bottom as new entries appear
- Color-coded by stage (blue for router, green for extractor, purple for normalizer)
- Polls `GET /documents/:id/status` every 3s
- On completion: automatically transitions to Review/Completed View with brief success flash

### Mode B: Review/Completed View

Shown when status is PROCESSED, PENDING_REVIEW, APPROVED, or REJECTED.

**Top bar:** Document filename, ID, type badge, status badge, processing cost, processing time

**Split layout** with three toggle modes: PDF-only | Split 50/50 | Data-only

**Left panel — PDF Viewer:**
- Page navigation, zoom
- Click field on right panel jumps PDF to source page

**Right panel — Extracted Data:**
- Section headers matching plugin sections (e.g., "Agreement Info", "Interest Rates", "Covenants")
- Each field: label, value, source page number, confidence indicator (high/medium/low dot)
- PII fields show lock icon + masked value (role-based)
- Expandable/collapsible sections (first section expanded, rest collapsed by default)

**Right panel — bottom sticky bar** (for PENDING_REVIEW status):
- Reviewer name (pre-filled from auth context)
- `Approve` button (green) — one click
- `Reject` button (red) — expands inline for rejection reason
- `Next in Queue →` button — navigates to next PENDING_REVIEW document without returning to Work Queue

**Processing Metrics** — collapsible panel at bottom:
- Cost breakdown: Router / Textract / Normalizer / Lambda / Step Functions (actual values, not estimates)
- Time breakdown per stage
- Pages processed vs total pages
- Plugin version used

### Mode C: Unknown Type Detected

If Router classifies as "UNKNOWN" or confidence is below threshold, the Processing View shows Classification completing, then displays an inline CTA:

```
┌──────────────────────────────────────────────────────────┐
│  Unknown Document Type                                   │
│                                                          │
│  This document doesn't match any configured type.        │
│  Would you like to set up extraction for it?             │
│                                                          │
│  [Set Up New Plugin] — uses this doc as sample           │
│  [Retry Classification] — if you think it's a known type │
└──────────────────────────────────────────────────────────┘
```

- "Set Up New Plugin" opens Plugin Wizard as a full-screen drawer, pre-loaded with this document's S3 key and PyPDF text
- On wizard completion + publish: auto-triggers reprocessing of this document
- Drawer closes, Processing View resumes from Extraction stage

---

## Page 3: Plugin Studio (`/config`)

Admin-only page for managing document type configurations.

**Header:** "Plugin Studio" + `Create New Plugin` button

**Plugin list** — card grid (not table):

```
┌──────────────────────────────────┐
│  Credit Agreement          v1.2  │
│  ─────────────────────────────── │
│  7 sections · 42 queries         │
│  Cost budget: $0.40 · PII: No   │
│  Status: PUBLISHED               │
│                                  │
│  Docs processed: 87              │
│  Avg confidence: HIGH            │
│  Avg cost: $0.38                 │
│                                  │
│  [Edit Draft]  [View Schema]     │
└──────────────────────────────────┘
```

Each card: plugin name + version, section/query counts, cost budget, PII flag, status (PUBLISHED/DRAFT), aggregate stats from processed documents, actions.

Built-in plugins (6 file-based types) show a `Built-in` badge. Edit Draft creates a DynamoDB override copy.

**Plugin Wizard** (`/config/new` or edit mode) — existing 4-step flow:
1. Upload Sample — drag-drop PDF, runs analysis
2. AI Analysis — detected fields, text, page count
3. Edit Config — keywords, sections, queries, fields, PII markers
4. Publish — save as DRAFT or PUBLISH. If triggered from unknown-type flow, also shows "Publish & Reprocess Document"

---

## Data Flow & Polling Strategy

### Tiered Polling

| Context | Interval | Endpoint |
|---------|----------|----------|
| Work Queue — has processing docs | 5s | `GET /documents?status=PROCESSING` (merge into cache) |
| Work Queue — nothing processing | 15s | `GET /documents` (full list) |
| Document Detail — processing | 3s | `GET /documents/:id/status` (lightweight) |
| Document Detail — completed | None | Single fetch |
| Plugin Studio | None | Single fetch on mount |

### TanStack Query Cache

- `documents` list query is single source of truth
- Document Detail reads from cache first (instant render), then fetches fresh
- Back navigation preserves scroll position and cache
- Inline quick actions use optimistic updates — UI updates immediately, rolls back on API error

### Status Endpoint Enhancement

`GET /documents/:id/status` must return richer data:

```json
{
  "status": "EXTRACTING",
  "stages": {
    "classification": {
      "status": "COMPLETED",
      "elapsed": 2.3,
      "result": {
        "documentType": "credit_agreement",
        "confidence": 0.97,
        "targetedPages": 42,
        "totalPages": 156,
        "sections": ["agreement_info", "rates", "terms"]
      }
    },
    "extraction": {
      "status": "IN_PROGRESS",
      "elapsed": 12.1,
      "progress": { "completed": 3, "total": 7, "currentSection": "Interest Rates" }
    },
    "normalization": {
      "status": "PENDING"
    }
  },
  "events": [
    { "ts": "2026-02-25T14:00:02Z", "stage": "router", "message": "Classified as credit_agreement (97%)" },
    { "ts": "2026-02-25T14:00:03Z", "stage": "router", "message": "Targeted 42/156 pages across 7 sections" },
    { "ts": "2026-02-25T14:00:05Z", "stage": "extractor", "message": "Processing section 1/7: Agreement Info (pages 1-8)" }
  ]
}
```

### Backend Changes Required

**Lambda changes:**
- Router, Extractor, Normalizer each append timestamped entries to a `processingEvents` list attribute in the DynamoDB document record
- No new tables, no Step Functions API calls, no CloudWatch log parsing

**API changes:**
- Enrich `GET /documents/:id/status` to return `stages` and `events` from DynamoDB
- `GET /documents` returns latest event message for processing documents (for inline status text in Work Queue rows)

**No backend changes needed for:**
- Work Queue list (existing `GET /documents` with status filter)
- Inline approve/reject (existing `POST /review/:id/approve` and `/reject`)
- Plugin wizard (existing endpoints)
- Metrics (existing `GET /metrics`)

---

## Component Inventory

### Kept As-Is
- `PDFViewer.tsx`
- `GenericDataFields.tsx`
- `BSAProfileFields.tsx`
- `BooleanFlag.tsx`
- `PIIIndicator.tsx`
- `StatusBadge.tsx`

### Modified
- `ExtractedValuesPanel.tsx` — add section grouping from plugin config, confidence indicators, page references
- `DocumentViewer.tsx` — add review actions sticky bar, "Next in Queue" navigation
- `ProcessingMetricsPanel.tsx` — show actual vs estimated values

### New Components
- `WorkQueue.tsx` — main page (upload bar + metrics strip + document list)
- `UploadBar.tsx` — slim inline upload zone
- `MetricsStrip.tsx` — collapsible pill-style metrics
- `PipelineTracker.tsx` — horizontal stepper for processing stages
- `LiveResultsStream.tsx` — scrolling log of processing events
- `UnknownTypePrompt.tsx` — CTA when classification fails
- `InlineReviewActions.tsx` — approve/reject/reprocess buttons for list rows and detail page

### Pages Removed
- `Dashboard.tsx` — replaced by Work Queue
- `Documents.tsx` — replaced by Work Queue
- `Upload.tsx` — merged into Work Queue upload bar
- `Review.tsx` — merged into Work Queue
- `ReviewDocument.tsx` — merged into Document Detail

---

## Navigation Flow

```
Work Queue (/)
  |-- Drop file -> row appears as PENDING -> auto-updates as it processes
  |-- Click row -> Document Detail (/documents/:id)
  |     |-- Processing? -> Pipeline tracker + live stream -> auto-transitions on complete
  |     |-- Pending Review? -> PDF + data + approve/reject bar + "Next in Queue"
  |     |-- Unknown type? -> CTA -> Plugin Wizard drawer -> reprocess
  |     |-- Back -> Work Queue (scroll preserved)
  |-- Metrics pills -> filter list by status

Plugin Studio (/config)
  |-- View all plugins as cards
  |-- Create/Edit -> Plugin Wizard (/config/new)
```

---

## Out of Scope

- WebSocket/SSE for true real-time (polling is sufficient for current scale)
- Batch operations (select multiple, bulk approve)
- Field-level corrections in UI (API exists but deferred)
- Audit trail viewer (API exists but deferred)
- Export/download of extracted data
- Dark mode
- Mobile-responsive layout
