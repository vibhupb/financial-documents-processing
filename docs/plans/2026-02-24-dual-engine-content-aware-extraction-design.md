# Dual Engine Content-Aware Extraction with Confidence-Gated Re-extraction

**Date:** 2026-02-24
**Status:** Approved
**Priority:** P0 — Accuracy-first architecture evolution

## Problem Statement

The current plugin architecture processes all pages with a single extraction method (Textract) regardless of content type. This causes:
- Charts and graphs return no useful data from Textract
- Complex nested tables get flattened, losing hierarchy
- Handwritten annotations are missed
- No confidence signal — extraction either works or silently returns partial/wrong data

Financial documents (credit agreements, loan packages, mortgage docs) contain mixed content: dense legal text, nested fee tables, rate charts, signature pages, and handwritten notes — each needing a different extraction approach.

## Design Overview

### Architecture: Dual Engine + Content Detection + Confidence Gate

```
S3 Upload --> Trigger --> Step Functions:

  1. ROUTER (existing, enhanced)
     Claude Haiku: classify doc type, target pages

  2. CONTENT ANALYZER (new Lambda)
     Per-page: detect content types (form/table/chart/handwritten/dense_text/mixed)
     Output: enriched extraction plan with method per page

  3. PRIMARY EXTRACTION (Map State, enhanced)
     Per-section, per-page optimal method:
       Form pages ----------> Textract FORMS
       Table pages ----------> Textract TABLES
       Chart pages ----------> Claude Vision
       Handwritten pages ----> Claude Vision (300 DPI)
       Dense text ------------> PyPDF + Textract QUERIES
       Mixed pages ----------> Textract + Vision (both)

  4. CONFIDENCE SCORER (new Lambda)
     Field-level confidence from multiple signals:
       - Textract confidence scores (0-100)
       - Schema validation (type, format, range)
       - Required field presence
       - Value format plausibility
     Output: scored fields + list of low-confidence fields

  5. RE-EXTRACTION (conditional, Map State)
     Only runs if low-confidence fields exist
     Uses ALTERNATE method for flagged pages:
       Textract was primary --> Vision re-extract
       Vision was primary ----> Textract verify

  6. MERGER (new Lambda)
     Field-level merge: prefer higher confidence value
     Log both values for audit trail
     Flag disagreements for human review

  7. NORMALIZER (existing, enhanced)
     Claude 3.5 Haiku: normalize merged results to schema
     Receives confidence metadata for context
```

### New Lambda Functions

| Lambda | Purpose | Input | Output |
|--------|---------|-------|--------|
| Content Analyzer | Detect content type per page | Page images + PyPDF text | Enriched extraction plan |
| Confidence Scorer | Score extracted fields | Extraction results + schema | Confidence report + re-extraction list |
| Merger | Combine primary + secondary results | Two extraction results + confidence report | Merged fields + audit trail |

### Modified Lambda Functions

| Lambda | Changes |
|--------|---------|
| Router | Passes content analysis hints to Content Analyzer |
| Extractor | New Vision extraction path alongside Textract |
| Normalizer | Receives confidence metadata, disagreement flags |

## Natural Language Plugin Definition (AI Plugin Compiler)

### Authoring Experience: UI-Driven Wizard

The Plugin Builder wizard (/config/new) is the primary authoring experience. No YAML, JSON Schema, or Textract query authoring required.

**Wizard Flow:**

1. **Upload sample document** — User uploads a representative PDF + enters name/description
2. **AI analyzes sample** — Content Analyzer runs per-page detection, AI suggests sections and fields based on document structure. User checks/unchecks fields, marks PII fields, adds custom fields.
3. **Review generated config** — AI Plugin Compiler generates full DocumentPluginConfig from the sample analysis + user selections. User can review/edit schema, prompt, classification keywords inline.
4. **Test against sample** — System runs full extraction pipeline. Shows extracted values with confidence scores, side-by-side with PDF. Highlights fields that triggered re-extraction.
5. **Publish** — Save as draft or publish to registry.

### AI Plugin Compiler

A single API endpoint that calls Claude Haiku to generate:

1. `classification.keywords` — from document description + sample text
2. `classification.distinguishing_rules` — how to differentiate from similar doc types
3. `sections` — with Textract queries, features, page targeting strategy
4. `output_schema` — JSON Schema with proper types, nesting, enums
5. `normalization prompt` — field mapping rules, defaults, validation
6. `cost_budget` — estimated from page count and extraction features

The compiler also incorporates Content Analyzer results to set per-section extraction methods (textract/vision/both/auto).

### File-Based Escape Hatch

Developers can still create `types/{doc}.py` + `prompts/{doc}.txt` for version-controlled, code-reviewed plugins. File-based plugins always win over DynamoDB plugins on collision.

## Content Analyzer Design

### Hybrid Detection (Heuristic + LLM)

**Step 1: Fast heuristic analysis (free, <50ms per page)**

Analyzes PyPDF-extracted text for:
- Form field patterns (key-value pairs, "Name: ___")
- Table structure markers (column alignment, grid patterns)
- Text density (chars per page)
- Numeric token ratio
- Line count and formatting

Clear cases resolved by heuristic alone:
- High form fields + moderate density = FORM
- High table structure markers = TABLE
- Very low text density = CHART_OR_IMAGE (visual content)
- High text density + few form fields = DENSE_TEXT

**Step 2: LLM classification for ambiguous pages (~$0.003/page)**

Sends page image to Claude Haiku for content type classification. Only triggered for pages where heuristic is inconclusive.

### Content Type to Extraction Method Mapping

| Content Type | Primary Method | Textract Features | Vision | DPI |
|--------------|---------------|-------------------|--------|-----|
| FORM | Textract | FORMS, QUERIES | -- | 200 |
| TABLE | Textract | TABLES | -- | 200 |
| CHART | Vision | -- | Claude 3.5 Haiku | 300 |
| HANDWRITTEN | Vision | -- | Claude 3.5 Haiku | 300 |
| DENSE_TEXT | Textract | QUERIES | -- | 150 |
| MIXED | Both | FORMS, TABLES | Claude 3.5 Haiku | 200 |

## Confidence Scorer Design

### Field-Level Scoring

Weighted composite score from multiple signals:

| Signal | Weight | Source |
|--------|--------|--------|
| Textract field confidence | 0.30 | Textract API response (0-100) |
| Vision self-reported confidence | 0.25 | LLM response (0.0-1.0) |
| Schema validation pass | 0.20 | Type checking, format regex, enum match |
| Required field present | 0.15 | Plugin output_schema required fields |
| Value format plausibility | 0.10 | SSN pattern, date format, currency range |

### Thresholds

- **High confidence (>= 0.85):** Accept field value, no re-extraction
- **Medium confidence (0.70-0.84):** Accept but flag for review
- **Low confidence (< 0.70):** Trigger re-extraction with alternate method

### Re-extraction Decision

```
If any field scores < 0.70:
  reextractionNeeded: true
  For each low-confidence field:
    If primary was Textract --> schedule Vision re-extraction for those pages
    If primary was Vision --> schedule Textract re-extraction for those pages
```

## Merger Design

### Field-Level Merge Strategy

- Both methods agree --> accept value, mark "confirmed"
- Only primary has value --> accept primary
- Secondary higher confidence --> upgrade to secondary value, log both
- Disagreement --> flag for human review, surface both values in Review Queue

### Audit Trail

Every merge decision is logged to S3 audit trail:
- Primary value + confidence
- Secondary value + confidence (if re-extracted)
- Merge decision (accepted/upgraded/flagged)
- Method used (textract/vision/both)

## Realistic Example: 85-Page Credit Agreement

```
Content Analysis:
  Pages 1-5:    DENSE_TEXT  (agreement preamble, definitions)
  Pages 6-12:   MIXED       (rate terms with embedded fee tables)
  Pages 13-25:  TABLE       (fee schedules, nested 3-level tables)
  Pages 26-40:  DENSE_TEXT  (covenants, representations)
  Pages 41-55:  TABLE       (lender commitment tables, waterfall)
  Pages 56-60:  CHART       (rate comparison graphs, payment curves)
  Pages 61-80:  DENSE_TEXT  (exhibits, legal boilerplate)
  Pages 81-85:  FORM        (signature pages)

Extraction routing:
  Sections 1,4: Textract QUERIES (keyword_density page targeting)
  Sections 2:   Textract + Vision (mixed content)
  Sections 3,5: Textract TABLES (primary) + Vision for complex nesting
  Section 6:    Vision ONLY (charts -- Textract returns nothing useful)
  Section 7:    Textract FORMS (signature pages)

Confidence results:
  Agreement Info:      0.94  (clean text extraction)
  Fee Schedules:       0.72 --> re-extraction triggered
    Prepayment premium: Textract got 3 of 5 tiers, Vision got all 5
  Rate Charts:         0.88  (Vision extracted trend data from graphs)
  Lender Commitments:  0.61 --> re-extraction triggered
    Nested waterfall: Textract flattened nesting, Vision preserved hierarchy
```

## Cost Impact

| Scenario | Current | New (clean) | New (re-extraction) |
|----------|---------|-------------|---------------------|
| W-2 (1 page, form) | $0.10 | $0.11 | $0.18 |
| BSA Profile (5 pages, forms) | $0.13 | $0.14 | $0.25 |
| Credit Agreement (20 pages) | $0.40 | $0.42 | $0.75 |
| Credit Agreement (85 pages, complex) | $1.20 | $1.25 | $2.10 |
| Loan Package (300 pages) | $0.34 | $0.37 | $0.60 |

Cost increase is 5-10% for clean documents. Re-extraction adds 50-100% but only triggers for low-confidence fields -- exactly the documents that would have had extraction errors before.

## Blue/Green Compatibility

The existing ExtractionRouteChoice still works. Documents processed before this change follow the legacy path. New documents with enrichedPlan follow the new path. No migration needed.

## Step Functions State Machine

```
Router --> Content Analyzer --> Map: Primary Extraction --> Confidence Scorer
  --> Choice: Re-extract?
      No --> Normalizer --> DynamoDB + S3
      Yes --> Map: Secondary Extraction --> Merger --> Normalizer --> DynamoDB + S3
```

## Implementation Phases

Phase 1: AI Plugin Compiler + enhanced wizard UI
Phase 2: Content Analyzer Lambda + heuristic detection
Phase 3: Vision extraction path in Extractor Lambda
Phase 4: Confidence Scorer Lambda
Phase 5: Re-extraction conditional + Merger Lambda
Phase 6: Step Functions state machine updates
Phase 7: Frontend confidence display + review queue enhancements
Phase 8: Testing with real financial documents across all content types
