# PageIndex Unification — Design Document

**Date**: 2026-03-09
**Status**: Proposed
**Author**: Claude Opus 4.6 + vibhupb

## Problem

PageIndex (pseudo-RAG via hierarchical document tree) is only used in the Step Functions extraction pipeline. Other document consumers bypass it entirely, leading to:

- **Compliance policy builder**: Raw text[:120K] truncated for large reference docs
- **Compliance evaluation**: Tree navigation works but `page_range` field is missing
- **Plugin builder**: Raw Textract text with no structural understanding
- **Large documents**: Exceed LLM context limits, lose content silently

## Vision

Every document entering the system gets a PageIndex tree. All consumers use tree-assisted retrieval instead of raw text dumps.

```
ANY document ──→ PageIndex tree (common ingestion) ──→ DynamoDB/S3
                         │
         ┌───────────────┼───────────────┬──────────────┐
     Extraction      Compliance       Compliance      Plugin
     (targeted       Policy Builder   Evaluation      Builder
      sections)      (per-section     (tree-guided    (field
                      requirement      page finding)   detection
                      extraction)                      per section)
```

## Current State

| Consumer | Uses PageIndex? | Current approach |
|----------|----------------|-----------------|
| Document extraction | Yes (Step Functions) | Tree → targeted section extraction |
| Compliance evaluation | Partial (tree nav for pages) | Tree structure passed but `page_range` is null |
| Compliance policy builder | No | `content.text[:120_000]` → single LLM call |
| Plugin builder | No | Raw Textract text → single LLM call |
| Q&A | Yes | Tree-assisted retrieval |

## Design

### 1. Shared PageIndex Builder (Lambda-invocable)

The existing PageIndex Lambda already works standalone — it reads a PDF from S3 and writes the tree to DynamoDB. The missing piece is a clean invocation API outside Step Functions.

**New API endpoint**: `POST /documents/build-tree`

```json
{
  "s3Key": "references/bl-xxx/doc.pdf",
  "entityId": "bl-xxx",           // baseline ID, plugin ID, or document ID
  "entityType": "baseline",        // "baseline" | "plugin" | "document"
  "options": {
    "generateSummaries": true,
    "generateDescription": true
  }
}
```

**Storage**: Trees stored in a new DynamoDB field pattern:
- Documents: `pageIndexTree` on `financial-documents` table (existing)
- Baselines: `referenceTree` on `compliance-baselines` table (new)
- Plugins: `sampleTree` on `document-plugin-configs` table (new)

The PageIndex Lambda is invoked **asynchronously** (fire-and-forget) since tree building takes 30-300s depending on document size.

### 2. Compliance Policy Builder Integration

**Current flow**:
```
Reference PDFs → PyPDF text → text[:120K] → Sonnet 4.6 → requirements
```

**New flow**:
```
Reference PDFs → PageIndex tree (per doc) → for each section:
    section text → Sonnet 4.6 → section requirements
→ merge all requirements → deduplicate
```

Benefits:
- No truncation — each section processed within token limits
- Better requirement quality — LLM sees focused section content
- Section-aware categories — requirements tagged with source section
- Works for 500+ page regulatory documents

**Implementation**:
1. After S3 upload, invoke PageIndex Lambda for each reference doc
2. Poll until tree is built (or use DynamoDB stream trigger)
3. Compliance-ingest iterates tree sections, extracts text per section
4. Each section → separate LLM call for requirement extraction
5. Merge + deduplicate across sections and documents

### 3. Compliance Evaluation Fix

**Current bug**: `_navigate_tree_for_batch` passes `n.get("page_range")` which is always `None`. Tree stores `start_index`/`end_index`.

**Fix**: Change to `n.get("start_index")` and `n.get("end_index")` to provide actual page ranges to the LLM for better page targeting.

### 4. Plugin Builder Integration

**Current flow**:
```
Sample PDFs → Textract → raw text → AI config generation
```

**New flow**:
```
Sample PDFs → PageIndex tree (per sample) → section structure informs:
    - Section definitions (from tree node titles)
    - Field detection per section (targeted Textract)
    - Classification keywords (from tree section names)
```

Benefits:
- Plugin sections derived from actual document structure
- Fields detected per section rather than entire document
- More accurate keyword extraction from section titles

### 5. Tree Storage Strategy

| Entity | Table | Field | Size handling |
|--------|-------|-------|--------------|
| Documents | financial-documents | pageIndexTree / pageIndexTreeS3Key | Existing |
| Baselines | compliance-baselines | referenceTree (map: docKey → tree) | S3 for >350KB |
| Plugins | document-plugin-configs | sampleTree (map: docKey → tree) | S3 for >350KB |

## Implementation Plan

### Phase 1: Foundation (compliance-evaluate fix + shared invocation)
1. Fix `page_range` bug in compliance-evaluate tree navigation
2. Add `POST /documents/build-tree` API endpoint
3. PageIndex Lambda: accept `entityType`/`entityId` for flexible storage

### Phase 2: Compliance Policy Builder
4. After reference doc upload, trigger PageIndex build
5. Frontend: show tree building progress on BaselineEditor
6. Compliance-ingest: iterate tree sections for targeted extraction
7. Per-section requirement extraction with Sonnet 4.6

### Phase 3: Plugin Builder
8. After sample PDF upload, trigger PageIndex build
9. Use tree sections to suggest plugin section definitions
10. Per-section field detection via targeted Textract

### Phase 4: Polish
11. Shared tree viewer component for baseline/plugin reference docs
12. Section-level requirement source references
13. Tree-assisted compliance evaluation improvements

## Cost Impact

PageIndex tree building: ~$0.11/100-page doc (Haiku 4.5)

| Scenario | Before | After |
|----------|--------|-------|
| Compliance ingest (50-page ref doc) | 1 Sonnet call ~$0.06 | Tree $0.05 + 8 section Sonnet calls ~$0.10 |
| Compliance ingest (200-page ref doc) | 1 Sonnet call (TRUNCATED) | Tree $0.22 + 15 section calls ~$0.20 |
| Plugin builder (3 samples, 20p each) | 3 Textract calls | 3 trees $0.07 + section-targeted Textract |

The cost increase is modest and the quality improvement is significant — especially for large documents that currently get truncated.

## Risk Mitigation

- **Latency**: Tree building is async — users see progress, not blocking
- **Failure**: If tree build fails, fall back to current raw text approach
- **Cost**: PageIndex uses Haiku (cheap); only requirement extraction uses Sonnet
- **Complexity**: Shared tree builder keeps implementation DRY across consumers
