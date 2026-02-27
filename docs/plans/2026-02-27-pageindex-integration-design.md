# PageIndex Integration — Document Understanding + Tree-Assisted Extraction

**Date**: 2026-02-27
**Status**: Design
**Author**: AI-assisted design session

---

## 1. Problem Statement

The current extraction pipeline uses keyword-density matching to identify which pages belong to which sections in large unstructured documents. This approach has known limitations:

- Keyword matching misses pages without explicit keywords (MCS loan package: 6/19 pages found)
- Requires band-aid fallbacks (uncovered pages fallback for docs ≤50 pages)
- No document understanding capability — users can only view extracted fields, not browse/query the document
- No way to defer extraction and explore a document first

## 2. Goals

1. **Always build a PageIndex tree** for unstructured documents (has_sections=True) — improves extraction accuracy via structural page targeting
2. **Add document understanding** — users can browse a hierarchical TOC, read section summaries, and ask questions
3. **Make extraction deferrable** — user can choose to extract immediately or later; PageIndex tree is cached for when extraction runs
4. **Restore raw JSON view** — lost during frontend upgrades
5. **Collapse cost panel** — move to bottom, collapsed by default, FYI only

## 3. Scope

### In Scope
- New `doc-processor-pageindex` Lambda for tree building (Claude Haiku 4.5 via Bedrock)
- Step Functions pipeline changes for PageIndex step
- DynamoDB schema additions (pageIndexTree field)
- Frontend view tabs: Summary | Extracted Values | Raw JSON
- Upload flow: processing mode toggle
- New API endpoints: `/documents/{id}/tree`, `/documents/{id}/extract`, `/documents/{id}/ask`
- Plugin contract: new `page_index` config block

### Out of Scope
- Vector database / embeddings
- Multi-document cross-referencing
- Real-time streaming of tree building progress
- Sonnet model upgrade (Haiku 4.5 for now, configurable per-plugin for future)

## 4. Architecture Overview

```
UPLOAD → Trigger → Step Functions
                        │
                    ┌───▼───┐
                    │Router │ Classify document type
                    └───┬───┘
                        │
          ┌─────────────┴──────────────────┐
          ▼                                 ▼
   UNSTRUCTURED (Tier 2)            STRUCTURED (Tier 1)
   has_sections=True                target_all_pages=True
   credit_agreement, loan_*,       bsa, w2, drivers_license
   commercial_invoice
          │                                 │
   ┌──────▼──────┐                  ┌───────▼───────┐
   │ PageIndex   │                  │ Textract      │
   │ Tree Build  │                  │ (all pages)   │
   │ (NEW STEP)  │                  │ (unchanged)   │
   └──────┬──────┘                  └───────┬───────┘
          │                                 │
          ▼                                 ▼
   Store tree in DynamoDB           Normalize → Done
          │
   [processingMode?]
    │                │
    ▼                ▼
  "extract"       "understand"
  or "both"       (defer extraction)
    │                │
    ▼                ▼
  Tree-assisted    Mark INDEXED
  Map extraction   (complete)
    │
    ▼
  Normalize → Done
```

## 5. Backend: New Lambda — `doc-processor-pageindex`

### Purpose
Build a hierarchical tree index from document text using Claude Haiku 4.5 via Bedrock. Adapted from VectifyAI/PageIndex (MIT license), replacing OpenAI with Bedrock.

### Location
```
lambda/pageindex/
├── handler.py          # Lambda entry point
├── tree_builder.py     # Core tree-building logic (adapted from PageIndex)
├── llm_client.py       # Bedrock converse wrapper (replaces OpenAI calls)
└── token_counter.py    # Approximate token counting (replaces tiktoken)
```

### Processing Pipeline (per document)

```
1. Extract text from each page (PyPDF2 + PyMuPDF fallback)
2. Scan first 20 pages for Table of Contents (TOC)
3. Route to one of three modes:
   a. TOC with page numbers → parse TOC, map to physical pages
   b. TOC without page numbers → parse TOC, locate sections in body
   c. No TOC → generate hierarchical structure from text batches
4. Verify section→page mappings (concurrent LLM calls)
5. Recursively split large nodes (>10 pages or >20K tokens)
6. Generate per-node summaries (concurrent LLM calls)
7. Return tree JSON
```

### LLM Client Abstraction

Replace PageIndex's three OpenAI functions with Bedrock equivalents:

| PageIndex Original | Bedrock Replacement | Usage |
|---|---|---|
| `ChatGPT_API()` (sync) | `bedrock_converse()` | TOC detection, extraction, transformation |
| `ChatGPT_API_with_finish_reason()` | `bedrock_converse_with_stop()` | Long TOC generation (checks max_tokens) |
| `ChatGPT_API_async()` | `bedrock_converse_threaded()` | Concurrent verification + summaries |

```python
# llm_client.py
import boto3, json
from concurrent.futures import ThreadPoolExecutor

bedrock = boto3.client('bedrock-runtime')
MODEL_ID = 'us.anthropic.claude-haiku-4-5-20251001-v1:0'

def bedrock_converse(prompt: str, model: str = MODEL_ID) -> str:
    response = bedrock.converse(
        modelId=model,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 4096},
    )
    return response["output"]["message"]["content"][0]["text"]

def bedrock_converse_with_stop(prompt: str, model: str = MODEL_ID) -> tuple[str, str]:
    response = bedrock.converse(
        modelId=model,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 4096},
    )
    content = response["output"]["message"]["content"][0]["text"]
    stop = response["stopReason"]  # "end_turn" or "max_tokens"
    finished = "finished" if stop != "max_tokens" else "max_output_reached"
    return content, finished

def bedrock_converse_threaded(prompts: list[str], model: str = MODEL_ID, max_workers: int = 10) -> list[str]:
    """Run multiple LLM calls concurrently using ThreadPoolExecutor."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(lambda p: bedrock_converse(p, model), prompts))
```

### Token Counting

Replace `tiktoken` with character-based approximation (Claude: ~4 chars/token):

```python
# token_counter.py
def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(text) // 4  # ~4 chars per token for Claude
```

### Output Format (stored in DynamoDB)

```json
{
  "doc_name": "credit-agreement.pdf",
  "doc_description": "Credit agreement between United Production Partners and JPMorgan Chase",
  "structure": [
    {
      "title": "Article I - Definitions",
      "node_id": "0000",
      "start_index": 1,
      "end_index": 25,
      "summary": "Defines key terms including Applicable Rate, Borrowing Base, Commitment...",
      "nodes": [
        {
          "title": "Section 1.01 - Defined Terms",
          "node_id": "0001",
          "start_index": 1,
          "end_index": 20,
          "summary": "Alphabetical list of defined terms..."
        }
      ]
    }
  ],
  "total_pages": 151,
  "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "build_cost": 0.22,
  "build_duration_seconds": 45
}
```

### Lambda Configuration

| Setting | Value | Rationale |
|---|---|---|
| Memory | 2048 MB | CPU-bound PDF text extraction + concurrent LLM calls |
| Timeout | 10 minutes | Large docs (300+ pages) need multiple LLM rounds |
| Layers | PyPDF + Plugins | Reuses existing PDF extraction layer |
| Env vars | `BEDROCK_MODEL_ID`, `TABLE_NAME`, `BUCKET_NAME` | Standard config |

## 6. Backend: Step Functions Changes

### New State: `BuildPageIndex`

Inserted between `ClassifyDocument` and `ExtractionRouteChoice`. Only runs for unstructured documents.

```
ClassifyDocument
      │
      ▼
PageIndexRouteChoice (NEW)
  │ has_sections=True          │ target_all_pages=True
  ▼                            ▼
BuildPageIndex (NEW)     ExtractionRouteChoice (existing)
  │                            │
  ▼                            ▼
ExtractionModeChoice (NEW)   (existing pipeline unchanged)
  │ "extract"/"both"    │ "understand"
  ▼                      ▼
ExtractionRouteChoice   ProcessingComplete
  │                     (status=INDEXED)
  ▼
(existing Map/Legacy pipeline)
```

### Choice Logic

**PageIndexRouteChoice**: Checks `$.classification.has_sections`
- `true` → `BuildPageIndex`
- `false` → `ExtractionRouteChoice` (existing flow, unchanged)

**ExtractionModeChoice**: Checks `$.processingMode`
- `"extract"` or `"both"` or absent (default) → `ExtractionRouteChoice`
- `"understand"` → `ProcessingComplete` with status `INDEXED`

### State Definitions (CDK)

```typescript
// New Lambda
const pageIndexLambda = new lambda.Function(this, 'PageIndexLambda', {
  functionName: 'doc-processor-pageindex',
  runtime: lambda.Runtime.PYTHON_3_13,
  handler: 'handler.lambda_handler',
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/pageindex')),
  timeout: cdk.Duration.minutes(10),
  memorySize: 2048,
  layers: [pypdfLayer, pluginsLayer],
  environment: {
    BEDROCK_MODEL_ID: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
    TABLE_NAME: documentTable.tableName,
    BUCKET_NAME: documentBucket.bucketName,
  },
});

// New Step Functions states
const buildPageIndex = new tasks.LambdaInvoke(this, 'BuildPageIndex', {
  lambdaFunction: pageIndexLambda,
  resultSelector: {
    'pageIndexTree.$': '$.Payload.pageIndexTree',
    'pageIndexCost.$': '$.Payload.pageIndexCost',
  },
  resultPath: '$.pageIndex',
});

const pageIndexRouteChoice = new sfn.Choice(this, 'PageIndexRouteChoice', {
  comment: 'Route unstructured docs through PageIndex tree building',
});

const extractionModeChoice = new sfn.Choice(this, 'ExtractionModeChoice', {
  comment: 'Extract immediately or defer (understand-only mode)',
});

// Wiring
pageIndexRouteChoice
  .when(
    sfn.Condition.booleanEquals('$.classification.has_sections', true),
    buildPageIndex
  )
  .otherwise(extractionRouteChoice);

buildPageIndex.next(extractionModeChoice);

extractionModeChoice
  .when(
    sfn.Condition.stringEquals('$.processingMode', 'understand'),
    processingComplete  // Skip extraction, tree is stored
  )
  .otherwise(extractionRouteChoice);

// Updated definition
const definition = classifyDocument.next(pageIndexRouteChoice);
```

## 7. Backend: DynamoDB Schema Changes

### `financial-documents` Table — New Fields

| Field | Type | When Set | Purpose |
|---|---|---|---|
| `pageIndexTree` | Map (JSON) | After PageIndex build | Cached tree structure |
| `processingMode` | String | At upload | `"extract"`, `"understand"`, `"both"` |
| `status` additions | String | Pipeline stages | New value: `INDEXED` (tree built, no extraction) |

### Status Flow

```
PENDING → PROCESSING → CLASSIFYING → INDEXING (new) → EXTRACTING → COMPLETED
                                          │
                                          └→ INDEXED (if understand-only, extraction deferred)
                                                │
                                          (user triggers extraction later)
                                                │
                                                └→ EXTRACTING → COMPLETED
```

### DynamoDB Item (after PageIndex, before extraction)

```json
{
  "documentId": "uuid",
  "documentType": "credit_agreement",
  "status": "INDEXED",
  "processingMode": "understand",
  "pageIndexTree": {
    "doc_name": "credit-agreement.pdf",
    "doc_description": "...",
    "structure": [{ "title": "...", "node_id": "0000", ... }],
    "total_pages": 151,
    "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "build_cost": 0.22,
    "build_duration_seconds": 45
  },
  "extractedData": null,
  "processingCost": {
    "router": 0.023,
    "pageIndex": 0.22,
    "total": 0.243
  }
}
```

## 8. Backend: Tree-Assisted Extraction

When extraction runs on a document that already has a cached `pageIndexTree`, the router's `build_extraction_plan()` uses tree node page ranges instead of keyword-density matching.

### Mapping Logic

```python
def build_extraction_plan_from_tree(plugin, page_index_tree):
    """Map plugin sections to PageIndex tree nodes by title similarity."""
    sections_config = plugin["sections"]
    tree_nodes = flatten_tree(page_index_tree["structure"])  # flat list of all nodes
    plan = []

    for section_id, section_config in sections_config.items():
        # Match section keywords against tree node titles
        best_nodes = match_section_to_nodes(
            section_config["classification_hints"]["keywords"],
            tree_nodes
        )
        if best_nodes:
            pages = set()
            for node in best_nodes:
                pages.update(range(node["start_index"], node["end_index"] + 1))
            plan.append({
                "sectionId": section_id,
                "sectionPages": sorted(pages),
                "sectionConfig": section_config,
                "pluginId": plugin["plugin_id"],
                "textractFeatures": section_config.get("textract_features", ["QUERIES"]),
                "queries": section_config.get("queries", []),
                "treeNodeIds": [n["node_id"] for n in best_nodes],  # audit trail
            })

    return plan
```

This eliminates:
- Keyword-density page scoring
- Uncovered pages fallback
- Position-based bonus rules (for extraction purposes — still used for signatures)

## 9. Backend: New API Endpoints

### `GET /documents/{id}/tree`

Returns the cached PageIndex tree for a document.

```json
// Response
{
  "documentId": "uuid",
  "pageIndexTree": { "structure": [...], "doc_description": "..." },
  "status": "INDEXED"
}
```

### `POST /documents/{id}/extract`

Triggers deferred extraction for an INDEXED document.

```python
# API handler logic
def trigger_extraction(document_id):
    doc = table.get_item(Key={"documentId": document_id, ...})
    if doc["status"] not in ("INDEXED", "COMPLETED"):
        return error(400, "Document not ready for extraction")

    # Start a new Step Functions execution that skips Router + PageIndex
    # and goes straight to extraction using cached tree
    sfn_input = {
        "documentId": document_id,
        "bucket": doc["bucket"],
        "key": doc["originalS3Key"],
        "pageIndexTree": doc["pageIndexTree"],
        "pluginId": doc["pluginId"],
        "processingMode": "extract",
        "skipClassification": True,  # Router already ran
        "skipPageIndex": True,       # Tree already built
    }
    sfn_client.start_execution(input=json.dumps(sfn_input))
    return {"status": "EXTRACTING", "documentId": document_id}
```

### `POST /documents/{id}/ask`

Q&A endpoint: LLM reasons over cached tree to answer user questions.

```python
def ask_document(document_id, question):
    doc = table.get_item(...)
    tree = doc["pageIndexTree"]
    page_texts = extract_page_texts(doc["bucket"], doc["originalS3Key"])

    # Step 1: LLM navigates tree to find relevant nodes
    nav_prompt = f"""You are given a query and a document's tree structure.
Find all nodes likely to contain the answer.

Query: {question}
Document tree: {json.dumps(tree['structure'])}

Return JSON: {{"thinking": "...", "node_list": ["0001", "0005"]}}"""

    node_ids = bedrock_converse(nav_prompt)  # returns node IDs

    # Step 2: Gather page text from selected nodes
    relevant_text = gather_node_text(tree, node_ids, page_texts)

    # Step 3: LLM generates answer from relevant pages
    answer_prompt = f"""Answer the question using ONLY the document text below.
Question: {question}
Document text: {relevant_text}

Cite specific page numbers in your answer."""

    answer = bedrock_converse(answer_prompt)
    return {"answer": answer, "sourceNodes": node_ids}
```

## 10. Plugin Contract Changes

### New `page_index` Config Block

Added to `DocumentPluginConfig` TypedDict:

```python
class PageIndexConfig(TypedDict, total=False):
    enabled: bool              # True for unstructured, False for structured forms
    model: str                 # Default: Haiku 4.5; upgradeable to Sonnet per-plugin
    max_page_num_each_node: int  # Default: 10
    max_token_num_each_node: int # Default: 20000
    toc_check_page_num: int    # Pages to scan for TOC. Default: 20
    generate_summaries: bool   # Default: True
    generate_description: bool # Default: True

class DocumentPluginConfig(TypedDict, total=False):
    # ... existing fields ...
    page_index: PageIndexConfig  # NEW
```

### Plugin Examples

**Unstructured (credit_agreement.py):**
```python
"page_index": {
    "enabled": True,
    "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "max_page_num_each_node": 10,
    "max_token_num_each_node": 20000,
    "toc_check_page_num": 20,
    "generate_summaries": True,
    "generate_description": True,
},
```

**Structured form (w2.py):**
```python
"page_index": {
    "enabled": False,  # No tree needed for 1-2 page forms
},
```

### Auto-Derive Rule

If `page_index` is not specified in plugin config:
- `has_sections: True` → `page_index.enabled = True` (default)
- `target_all_pages: True` → `page_index.enabled = False` (default)

## 11. Frontend: View Tabs (Right Panel)

### Current Layout

```
┌──────────────────────────────────────────────────┐
│  [PDF Only] [Split View] [Data Only]             │  ← layout toggle
├────────────────────┬─────────────────────────────┤
│                    │  Extracted Data              │
│   PDF Viewer       │  ├── Validation Summary      │
│   (left panel)     │  ├── Signature Validation    │
│                    │  ├── Processing Metrics       │  ← expanded by default
│                    │  ├── Sections (collapsible)   │
│                    │  └── Validation Notes         │
└────────────────────┴─────────────────────────────┘
```

### New Layout

```
┌──────────────────────────────────────────────────┐
│  [PDF Only] [Split View] [Data Only]             │  ← layout toggle (unchanged)
├────────────────────┬─────────────────────────────┤
│                    │ [Summary] [Extracted] [JSON] │  ← NEW view tabs
│                    ├─────────────────────────────┤
│   PDF Viewer       │                             │
│   (left panel)     │  (active tab content)       │
│                    │                             │
│                    │                             │
│                    ├─────────────────────────────┤
│                    │ ▸ Processing Cost    $0.58   │  ← collapsed by default
└────────────────────┴─────────────────────────────┘
```

### Tab: Summary (NEW)

Shows the PageIndex tree as a navigable document outline with section summaries.

```
┌─────────────────────────────────────────┐
│ 📄 Document Understanding               │
│                                         │
│ "Credit agreement between United        │
│  Production Partners and JPMorgan..."   │
│                                         │
│ ▼ Article I - Definitions (pp. 1-25)    │
│   │ Defines key terms including...      │
│   ├── Section 1.01 - Defined Terms      │
│   └── Section 1.02 - Classification     │
│ ▶ Article II - Commitments (pp. 26-40)  │
│ ▶ Article III - Rates (pp. 41-55)       │
│ ▶ ...                                   │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ Ask a question about this document  │ │
│ │ ____________________________________│ │
│ │                              [Ask]  │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ (Q&A responses appear here)             │
└─────────────────────────────────────────┘
```

**Behavior:**
- Clicking a tree node navigates the PDF viewer to that section's start page
- Expandable/collapsible tree nodes with summaries
- Q&A input at bottom calls `POST /documents/{id}/ask`
- If tree not yet built (structured forms), tab shows "Not available for this document type"

### Tab: Extracted Values (EXISTING, modified)

Current `ExtractedValuesPanel` content — validation summary, signature validation, section data.

**If extraction hasn't run yet** (status=INDEXED):
```
┌─────────────────────────────────────────┐
│ 📊 Extraction Not Yet Run               │
│                                         │
│ This document has been indexed but       │
│ field extraction has not been performed. │
│                                         │
│        [▶ Run Extraction Now]           │
│                                         │
│ Extraction uses the document's tree     │
│ structure for precise page targeting.    │
└─────────────────────────────────────────┘
```

Clicking "Run Extraction Now" calls `POST /documents/{id}/extract` and polls for completion.

### Tab: Raw JSON (NEW — restored feature)

Displays the raw `extractedData` JSON with syntax highlighting.

```
┌─────────────────────────────────────────┐
│ { } Raw JSON                    [Copy]  │
├─────────────────────────────────────────┤
│ {                                       │
│   "loanData": {                         │
│     "agreementInfo": {                  │
│       "instrumentType": "Credit...",    │
│       "effectiveDate": "2026-01-15",    │
│       ...                               │
│     },                                  │
│     "definitions": { ... },             │
│     ...                                 │
│   },                                    │
│   "validation": { ... },                │
│   "audit": { ... }                      │
│ }                                       │
└─────────────────────────────────────────┘
```

**Features:**
- Syntax-highlighted JSON (use lightweight CSS-based highlighting, no heavy library)
- Copy-to-clipboard button
- If no extracted data: shows `pageIndexTree` JSON instead
- Collapsible nested objects

### Processing Metrics Panel Changes

- **Default state**: Collapsed (change `useState(true)` → `useState(false)`)
- **Position**: Bottom of right panel, below all tabs
- **Always visible** regardless of active tab (Summary/Extracted/JSON)

## 12. Frontend: Upload Flow Change

### Current Upload
User uploads file → presigned URL → S3 → pipeline starts automatically.

### New Upload
Add a processing mode toggle on the upload confirmation dialog:

```
┌─────────────────────────────────────────┐
│ Upload: credit-agreement.pdf            │
│                                         │
│ Processing mode:                        │
│ ○ Extract fields (default)              │
│   Index + extract structured data       │
│ ○ Understand first                      │
│   Index only, extract later if needed   │
│                                         │
│           [Cancel]  [Upload]            │
└─────────────────────────────────────────┘
```

The `processingMode` ("extract" or "understand") is passed as S3 object metadata, read by the trigger Lambda, and forwarded to Step Functions input.

**Note**: For structured forms (BSA, W2, etc.), this toggle is hidden — they always extract.

## 13. Frontend: TypeScript Types

### New Types

```typescript
// PageIndex tree types
interface PageIndexNode {
  title: string;
  node_id: string;
  start_index: number;
  end_index: number;
  summary?: string;
  nodes?: PageIndexNode[];
}

interface PageIndexTree {
  doc_name: string;
  doc_description?: string;
  structure: PageIndexNode[];
  total_pages: number;
  model: string;
  build_cost: number;
  build_duration_seconds: number;
}

// Updated Document interface
interface Document {
  // ... existing fields ...
  pageIndexTree?: PageIndexTree;       // NEW
  processingMode?: 'extract' | 'understand' | 'both';  // NEW
}

// Q&A types
interface AskRequest {
  question: string;
}

interface AskResponse {
  answer: string;
  sourceNodes: string[];
  sourcePages: number[];
}

// View tab type
type DataViewTab = 'summary' | 'extracted' | 'json';
```

## 14. New React Components

| Component | Purpose | Location |
|---|---|---|
| `DocumentTreeView.tsx` | Renders PageIndex tree as expandable TOC | `frontend/src/components/` |
| `DocumentQA.tsx` | Q&A input + response display | `frontend/src/components/` |
| `RawJsonView.tsx` | Syntax-highlighted JSON viewer with copy | `frontend/src/components/` |
| `DataViewTabs.tsx` | Tab bar: Summary / Extracted / JSON | `frontend/src/components/` |
| `ExtractionTrigger.tsx` | "Run Extraction Now" button + polling | `frontend/src/components/` |

## 15. Cost Analysis

### Per-Document Cost (with PageIndex)

**Credit Agreement (150 pages, with TOC):**

| Stage | Service | Details | Cost |
|---|---|---|---|
| Router | Claude Haiku 4.5 | ~20K input + 500 output tokens | ~$0.023 |
| **PageIndex** | **Claude Haiku 4.5** | **~200K input + 30K output tokens** | **~$0.35** |
| Textract | Tables + Queries | ~30 pages × $0.02/page | ~$0.60 |
| Normalizer | Claude Haiku 4.5 | ~6K input + 1.4K output tokens | ~$0.013 |
| Step Functions | Standard | ~15 transitions | ~$0.0004 |
| Lambda | Compute | 5 invocations + ~80 GB-seconds | ~$0.001 |
| **Total (extract)** | | | **~$0.99** |
| **Total (understand only)** | | PageIndex + Router only | **~$0.37** |

**Loan Agreement (20 pages, no TOC):**

| Stage | Service | Details | Cost |
|---|---|---|---|
| Router | Claude Haiku 4.5 | ~5K input + 300 output tokens | ~$0.008 |
| **PageIndex** | **Claude Haiku 4.5** | **~40K input + 8K output tokens** | **~$0.08** |
| Textract | Queries | ~15 pages × $0.02/page | ~$0.30 |
| Normalizer | Claude Haiku 4.5 | ~4K input + 1K output tokens | ~$0.009 |
| **Total (extract)** | | | **~$0.40** |

**Structured forms (BSA, W2, DL): No change** — PageIndex skipped.

### Monthly Cost Comparison

| Volume | Current (no PageIndex) | With PageIndex (extract all) | With PageIndex (50% understand-only) |
|---|---|---|---|
| 100 docs/month | $42 | $75 | $58 |
| 1,000 docs/month | $420 | $750 | $585 |
| 10,000 docs/month | $4,200 | $7,500 | $5,850 |

### Cost Justification

- Better extraction accuracy (tree-assisted page targeting eliminates keyword guessing)
- Document understanding capability (browsable TOC, summaries, Q&A)
- Deferred extraction saves money when users only need to understand a document
- Tree is built once and cached — Q&A queries use cached tree (cheap)

## 16. File Change Manifest

### New Files

| File | Purpose |
|---|---|
| `lambda/pageindex/handler.py` | PageIndex Lambda entry point |
| `lambda/pageindex/tree_builder.py` | Core tree-building logic (adapted from PageIndex) |
| `lambda/pageindex/llm_client.py` | Bedrock converse wrapper |
| `lambda/pageindex/token_counter.py` | Approximate token counting |
| `frontend/src/components/DocumentTreeView.tsx` | Tree TOC component |
| `frontend/src/components/DocumentQA.tsx` | Q&A input/response component |
| `frontend/src/components/RawJsonView.tsx` | Raw JSON viewer |
| `frontend/src/components/DataViewTabs.tsx` | Tab switcher component |
| `frontend/src/components/ExtractionTrigger.tsx` | Deferred extraction trigger |

### Modified Files

| File | Changes |
|---|---|
| `lib/stacks/document-processing-stack.ts` | New Lambda, Step Functions states, IAM |
| `lambda/layers/plugins/python/document_plugins/contract.py` | Add `PageIndexConfig` TypedDict |
| `lambda/router/handler.py` | `build_extraction_plan_from_tree()` function |
| `lambda/trigger/handler.py` | Read `processingMode` from S3 metadata |
| `lambda/api/handler.py` | New endpoints: `/tree`, `/extract`, `/ask` |
| `lambda/normalizer/handler.py` | Accept `pageIndexCost` in cost calculation |
| `frontend/src/types/index.ts` | New TypeScript interfaces |
| `frontend/src/components/DocumentViewer.tsx` | Integrate DataViewTabs |
| `frontend/src/components/ExtractedValuesPanel.tsx` | Handle INDEXED state |
| `frontend/src/components/ProcessingMetricsPanel.tsx` | Collapsed by default, add PageIndex cost row |
| `frontend/src/services/api.ts` | New API client functions |
| `frontend/src/pages/DocumentDetail.tsx` | Handle INDEXED status, view tabs |
| Plugin files: `credit_agreement.py`, `loan_agreement.py`, etc. | Add `page_index` config block |

### Unchanged Files

- `lambda/extractor/handler.py` — receives extraction plan as before, no changes
- `frontend/src/components/PDFViewer.tsx` — unchanged
- `frontend/src/components/GenericDataFields.tsx` — unchanged
- `frontend/src/components/BSAProfileFields.tsx` — unchanged
- Structured form plugins: `bsa_profile.py`, `w2.py`, `drivers_license.py` — add `page_index.enabled: False` only

## 17. Implementation Phases

### Phase 1: Core PageIndex Lambda (Backend)
1. Create `lambda/pageindex/` with tree builder adapted from VectifyAI/PageIndex
2. Implement Bedrock LLM client (replaces OpenAI)
3. Implement approximate token counting (replaces tiktoken)
4. Unit test tree building against sample credit agreement PDF
5. Add `PageIndexConfig` to plugin contract

### Phase 2: Step Functions Integration (Backend)
1. Add PageIndex Lambda to CDK stack
2. Add `PageIndexRouteChoice` and `ExtractionModeChoice` states
3. Wire up new states in state machine definition
4. Update trigger Lambda to read `processingMode` from S3 metadata
5. Update normalizer to include PageIndex cost in total

### Phase 3: Tree-Assisted Extraction (Backend)
1. Implement `build_extraction_plan_from_tree()` in router
2. Add tree→section mapping logic (title similarity matching)
3. Test extraction plan quality vs keyword-density baseline
4. Add `pageIndexTree` to DynamoDB document record

### Phase 4: New API Endpoints (Backend)
1. `GET /documents/{id}/tree` — return cached tree
2. `POST /documents/{id}/extract` — trigger deferred extraction
3. `POST /documents/{id}/ask` — Q&A over cached tree

### Phase 5: Frontend View Tabs (Frontend)
1. Create `DataViewTabs` component
2. Create `DocumentTreeView` — expandable tree with page navigation
3. Create `RawJsonView` — syntax-highlighted JSON with copy
4. Create `ExtractionTrigger` — deferred extraction button
5. Integrate tabs into `DocumentViewer.tsx`
6. Collapse `ProcessingMetricsPanel` by default

### Phase 6: Frontend Q&A + Upload (Frontend)
1. Create `DocumentQA` component
2. Add processing mode toggle to upload flow
3. Add new API client functions in `api.ts`
4. Update TypeScript types

### Phase 7: Testing + Deploy
1. End-to-end test: upload credit agreement → tree built → browse summary → trigger extraction → view extracted values → view raw JSON
2. End-to-end test: upload BSA profile → no tree built → direct extraction → view extracted values
3. Cost validation: compare actual PageIndex costs vs estimates
4. Deploy backend → deploy frontend

---

*Design document generated 2026-02-27. Ready for implementation planning.*
