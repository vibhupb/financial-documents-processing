---
paths:
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
  - "frontend/**/*.css"
---
# Frontend React Development

## Code Style (TypeScript)
- Use strict TypeScript settings
- Prefer `const` over `let`
- Use meaningful variable names
- Document complex logic with comments
- Use TanStack Query for data fetching in React

## Key Patterns
- **GenericDataFields**: Schema-driven renderer for any document type — no per-type UI code needed
- **PDF Viewing**: react-pdf for in-browser rendering with presigned S3 URLs
- **Auth**: Cognito context via `useAuth` hook (`REQUIRE_AUTH=false` default)
- **Styling**: Tailwind CSS utility-first

## Frontend Testing
Tests use vitest with jsdom. **MUST run from `frontend/` directory** (not project root):
```bash
cd frontend && npx vitest run
```
If tests fail with "document is not defined", you're running from the wrong directory.

## Component Architecture
- `DocumentViewer.tsx` — PDF + extracted data viewer
- `DataViewTabs.tsx` — Tab switcher (Summary/Extracted/JSON/Compliance)
- `ComplianceTab.tsx` — Compliance results with evidence + page-jump
- `ComplianceScoreGauge.tsx` — SVG donut chart
- `VerdictBadge.tsx` — Color-coded PASS/FAIL/PARTIAL/NOT_FOUND
- `ReviewerOverride.tsx` — Inline reviewer override form
- `ExtractionTrigger.tsx` — Deferred extraction trigger button
- `UploadBar.tsx` — Drop zone + Upload Mode Dialog (processing mode, plugin selector, baseline checkboxes)
- `PipelineTracker.tsx` — 3-4 stage pipeline (Classification/Extraction/Normalization + optional Compliance)
- `LiveResultsStream.tsx` — Real-time processing log with color-coded stages (router/extractor/normalizer/compliance/indexing)
- `BaselineEditor.tsx` — Baseline CRUD with inline-editable name/description + reference doc upload

## Processing Mode & Tab Visibility
- `processingMode` on Document type: `'extract' | 'understand' | 'both'`
- `DataViewTabs` filters visible tabs based on mode:
  - `extract` → Summary, Extracted, JSON (no Compliance)
  - `understand` → Summary, Compliance (no Extracted, no JSON)
  - `both` / undefined → All tabs
- `DocumentViewer` reads `document.processingMode` and passes to DataViewTabs + sets default tab

## Troubleshooting
- **Frontend Not Showing Data**: Check `extractedData` vs `data` access; verify API response matches TS types
- **CORS Errors**: Check `CORS_ORIGIN` env var; ensure presigned URLs use regional S3 endpoint
- **After Deploy**: Hard refresh (Cmd+Shift+R) after CloudFront invalidation
