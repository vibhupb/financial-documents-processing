# Compliance Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Compliance Engine that evaluates uploaded financial documents against admin-curated requirement baselines, producing per-requirement verdicts with evidence citations and reviewer override capability.

**Architecture:** Extends existing Step Functions pipeline with a parallel compliance branch. Admin flow: upload reference doc → parse → LLM extracts requirements → admin curates → publish baseline. User flow: document upload triggers compliance evaluation alongside extraction, batching 5-8 requirements per LLM call using the existing Q&A pattern (tree navigation → page extraction → LLM evaluate). Three new DynamoDB tables, three new Lambdas, one new Lambda layer, and frontend pages for baseline management + compliance results tab.

**Tech Stack:** AWS CDK (TypeScript), Python 3.13 Lambdas, DynamoDB, Bedrock Claude Haiku 4.5, python-docx, python-pptx, Pillow, React + TypeScript + TanStack Query, Tailwind CSS

---

## Phase 1: Data Layer & Infrastructure

### Task 1: Add DynamoDB tables for compliance

**File:** `lib/stacks/document-processing-stack.ts`

**Test first:**
```bash
npx cdk synth --quiet 2>&1 | tail -5   # Baseline: must pass before changes
```

**Implementation** -- add after the existing `ReviewStatusIndex` GSI block (~line 115):

```typescript
// ==========================================
// Compliance Engine -- DynamoDB Tables
// ==========================================

const complianceBaselinesTable = new dynamodb.Table(this, 'ComplianceBaselinesTable', {
  tableName: 'compliance-baselines',
  partitionKey: { name: 'baselineId', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  pointInTimeRecovery: true,
  encryption: dynamodb.TableEncryption.AWS_MANAGED,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
});
complianceBaselinesTable.addGlobalSecondaryIndex({
  indexName: 'pluginId-index',
  partitionKey: { name: 'pluginId', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'status', type: dynamodb.AttributeType.STRING },
  projectionType: dynamodb.ProjectionType.ALL,
});

const complianceReportsTable = new dynamodb.Table(this, 'ComplianceReportsTable', {
  tableName: 'compliance-reports',
  partitionKey: { name: 'reportId', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'documentId', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  pointInTimeRecovery: true,
  encryption: dynamodb.TableEncryption.AWS_MANAGED,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
});
complianceReportsTable.addGlobalSecondaryIndex({
  indexName: 'documentId-index',
  partitionKey: { name: 'documentId', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'evaluatedAt', type: dynamodb.AttributeType.STRING },
  projectionType: dynamodb.ProjectionType.ALL,
});
complianceReportsTable.addGlobalSecondaryIndex({
  indexName: 'baselineId-index',
  partitionKey: { name: 'baselineId', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'evaluatedAt', type: dynamodb.AttributeType.STRING },
  projectionType: dynamodb.ProjectionType.ALL,
});

const complianceFeedbackTable = new dynamodb.Table(this, 'ComplianceFeedbackTable', {
  tableName: 'compliance-feedback',
  partitionKey: { name: 'feedbackId', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'baselineId', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  pointInTimeRecovery: true,
  encryption: dynamodb.TableEncryption.AWS_MANAGED,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
});
complianceFeedbackTable.addGlobalSecondaryIndex({
  indexName: 'requirementId-index',
  partitionKey: { name: 'requirementId', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
  projectionType: dynamodb.ProjectionType.ALL,
});
```

**Verify:**
```bash
npx cdk synth --quiet 2>&1 | tail -5          # Must pass
npx cdk synth | grep -c "AWS::DynamoDB::Table" # Expect original count + 3
```

**Done when:** `cdk synth` succeeds and CloudFormation template contains `compliance-baselines`, `compliance-reports`, and `compliance-feedback` tables each with their GSIs.

### Task 2: Add compliance Lambda functions + layer to CDK

**File:** `lib/stacks/document-processing-stack.ts`
**Test first:** `npx cdk synth --quiet 2>&1 | tail -5` (must pass after Task 1)

**Implementation** -- add layer after PluginsLayer (~line 133), Lambdas after PageIndex (~line 260):

```typescript
// Compliance Parsers Layer
const complianceParsersLayer = new lambda.LayerVersion(this, 'ComplianceParsersLayer', {
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/layers/compliance-parsers')),
  compatibleRuntimes: [lambda.Runtime.PYTHON_3_13],
  description: 'python-docx, python-pptx, Pillow for reference doc parsing',
});

// compliance-ingest: parse reference docs, extract requirements (2GB, 300s)
const complianceIngestLambda = new lambda.Function(this, 'ComplianceIngestLambda', {
  functionName: 'doc-processor-compliance-ingest',
  runtime: lambda.Runtime.PYTHON_3_13, handler: 'handler.lambda_handler',
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/compliance-ingest')),
  layers: [pypdfLayer, complianceParsersLayer], memorySize: 2048,
  timeout: cdk.Duration.seconds(300),
  environment: { BUCKET_NAME: documentBucket.bucketName,
    BASELINES_TABLE: complianceBaselinesTable.tableName,
    BEDROCK_MODEL_ID: 'us.anthropic.claude-haiku-4-5-20251001-v1:0' },
  tracing: lambda.Tracing.ACTIVE,
});
documentBucket.grantRead(complianceIngestLambda);
complianceBaselinesTable.grantReadWriteData(complianceIngestLambda);
complianceIngestLambda.addToRolePolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW, resources: ['*'],
  actions: ['bedrock:InvokeModel', 'textract:AnalyzeDocument', 'textract:DetectDocumentText'],
}));

// compliance-evaluate: evaluate documents against baselines (2GB, 300s)
const complianceEvaluateLambda = new lambda.Function(this, 'ComplianceEvaluateLambda', {
  functionName: 'doc-processor-compliance-evaluate',
  runtime: lambda.Runtime.PYTHON_3_13, handler: 'handler.lambda_handler',
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/compliance-evaluate')),
  layers: [pypdfLayer, pluginsLayer], memorySize: 2048,
  timeout: cdk.Duration.seconds(300),
  environment: { BUCKET_NAME: documentBucket.bucketName,
    TABLE_NAME: documentTable.tableName,
    BASELINES_TABLE: complianceBaselinesTable.tableName,
    REPORTS_TABLE: complianceReportsTable.tableName,
    FEEDBACK_TABLE: complianceFeedbackTable.tableName,
    BEDROCK_MODEL_ID: 'us.anthropic.claude-haiku-4-5-20251001-v1:0' },
  tracing: lambda.Tracing.ACTIVE,
});
documentBucket.grantRead(complianceEvaluateLambda);
documentTable.grantReadData(complianceEvaluateLambda);
complianceBaselinesTable.grantReadData(complianceEvaluateLambda);
complianceReportsTable.grantReadWriteData(complianceEvaluateLambda);
complianceFeedbackTable.grantReadData(complianceEvaluateLambda);
complianceEvaluateLambda.addToRolePolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW, actions: ['bedrock:InvokeModel'], resources: ['*'],
}));

// compliance-api: CRUD for baselines/reports/feedback (512MB, 30s)
const complianceApiLambda = new lambda.Function(this, 'ComplianceApiLambda', {
  functionName: 'doc-processor-compliance-api',
  runtime: lambda.Runtime.PYTHON_3_13, handler: 'handler.lambda_handler',
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/compliance-api')),
  memorySize: 512, timeout: cdk.Duration.seconds(30),
  environment: { BUCKET_NAME: documentBucket.bucketName, CORS_ORIGIN: '*',
    BASELINES_TABLE: complianceBaselinesTable.tableName,
    REPORTS_TABLE: complianceReportsTable.tableName,
    FEEDBACK_TABLE: complianceFeedbackTable.tableName },
  tracing: lambda.Tracing.ACTIVE,
});
documentBucket.grantReadWrite(complianceApiLambda);
[complianceBaselinesTable, complianceReportsTable, complianceFeedbackTable]
  .forEach(t => t.grantReadWriteData(complianceApiLambda));
```

Also add `BASELINES_TABLE`, `REPORTS_TABLE`, `FEEDBACK_TABLE` env vars to `apiLambda`.

**Verify:** `npx cdk synth | grep "doc-processor-compliance" | wc -l` (expect 3)
**Done when:** `cdk synth` succeeds with 3 new Lambdas, 1 new Layer, and IAM grants.

### Task 3: Add Step Functions compliance parallel branch

**File:** `lib/stacks/document-processing-stack.ts`
**Test first:** `npx cdk synth --quiet 2>&1 | tail -5`

**Implementation** -- modify Step Functions (~line 855-960). Add after `mapExtraction`:

```typescript
// Compliance evaluation state (non-blocking)
const evaluateCompliance = new tasks.LambdaInvoke(this, 'EvaluateCompliance', {
  lambdaFunction: complianceEvaluateLambda,
  outputPath: '$.Payload', retryOnServiceExceptions: true,
});
const complianceFailed = new sfn.Pass(this, 'ComplianceFailed', {
  result: sfn.Result.fromObject({ complianceReport: { status: 'error', overallScore: -1 } }),
});
evaluateCompliance.addCatch(complianceFailed, { resultPath: '$.complianceError' });

// Parallel: extraction + compliance run side-by-side
const extractionAndCompliance = new sfn.Parallel(this, 'ExtractionAndCompliance', {
  comment: 'Run extraction and compliance evaluation in parallel',
  resultPath: '$.parallelResults',
});
extractionAndCompliance.branch(mapExtraction.next(normalizeData));  // Branch 0
extractionAndCompliance.branch(evaluateCompliance);                 // Branch 1
extractionAndCompliance.next(processingComplete);
extractionAndCompliance.addCatch(handleError, { resultPath: '$.error' });
```

Update `extractionRouteChoice` to point to `extractionAndCompliance` (was `mapExtraction`):

```typescript
extractionRouteChoice
  .when(sfn.Condition.and(
    sfn.Condition.isPresent('$.extractionPlan'),
    sfn.Condition.isPresent('$.extractionPlan[0]')),
    extractionAndCompliance)  // Changed from mapExtraction
  .otherwise(legacyDocumentTypeChoice);
```

Legacy paths stay unchanged (bypass compliance for backward compat).

**Key design:** Compliance is non-blocking via `addCatch`. If no baselines match the
`pluginId`, the Lambda returns `{status: "no_baselines"}` immediately (< 100ms).
Results stored in `$.parallelResults[0]` (extraction) and `[1]` (compliance).

**Verify:** `npx cdk synth | grep -c "EvaluateCompliance"` (expect >= 1)

**Done when:** State machine contains `EvaluateCompliance` and `ExtractionAndCompliance`.

---

## Phase 2: Backend — Reference Document Ingestion

### Task 4: Build compliance-parsers Lambda layer

**Files:** `lambda/layers/compliance-parsers/requirements.txt`, `build.sh`, `.gitignore`

**Test first:**
```bash
bash lambda/layers/compliance-parsers/build.sh
python3 -c "import sys; sys.path.insert(0,'lambda/layers/compliance-parsers/python'); import docx; import pptx; from PIL import Image; print('OK')"
```

**Implementation:**

Create `lambda/layers/compliance-parsers/requirements.txt`:
```
python-docx>=1.1.0
python-pptx>=0.6.23
Pillow>=10.4.0
```

Create `lambda/layers/compliance-parsers/build.sh` (mirror `lambda/layers/pypdf/build.sh`):
```bash
#!/bin/bash
set -e
LAYER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$LAYER_DIR/python"
echo "Building Compliance Parsers Lambda Layer for Python 3.13..."
rm -rf "$PACKAGE_DIR" && mkdir -p "$PACKAGE_DIR"
pip3 install -r "$LAYER_DIR/requirements.txt" \
    -t "$PACKAGE_DIR" --platform manylinux2014_x86_64 \
    --implementation cp --python-version 3.13 --only-binary=:all: --upgrade
echo "Layer built: $(du -sh "$PACKAGE_DIR" | cut -f1)"
```

Create `lambda/layers/compliance-parsers/.gitignore`: `python/`

Run `chmod +x lambda/layers/compliance-parsers/build.sh`.

Also add to `scripts/deploy-backend.sh` (before `cdk deploy`):
```bash
echo "Building compliance-parsers layer..."
bash "$PROJECT_ROOT/lambda/layers/compliance-parsers/build.sh"
```

**Verify:** `build.sh` exits 0, layer size < 250MB, imports succeed.

**Done when:** Build script runs, all 3 Python imports work, `.gitignore` excludes `python/`.

### Task 5: Implement reference document parser (compliance-ingest Lambda)

**Files:** `lambda/compliance-ingest/parser.py`, `tests/test_compliance_parser.py`
**Test first** (`tests/test_compliance_parser.py`):
```python
import io, pytest; from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'compliance-ingest'))
from parser import parse_docx, parse_pptx, parse_pdf

def test_docx_text():
    from docx import Document
    doc = Document(); doc.add_paragraph("Must specify APR.")
    t = doc.add_table(rows=2, cols=2)
    t.cell(0,0).text,t.cell(0,1).text,t.cell(1,0).text,t.cell(1,1).text = "F","R","APR","Yes"
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    assert "APR" in parse_docx(buf.read()).text

def test_docx_images():
    from docx import Document; from PIL import Image
    doc = Document(); doc.add_paragraph("Chart:")
    ib = io.BytesIO(); Image.new('RGB',(10,10),'red').save(ib,format='PNG'); ib.seek(0)
    doc.add_picture(ib, width=914400)
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    assert len(parse_docx(buf.read()).images) >= 1

@patch("parser.pypdf")
def test_pdf(m):
    r = MagicMock(); r.pages=[MagicMock(extract_text=lambda:"P1")]
    m.PdfReader.return_value=r; assert "P1" in parse_pdf(b"x").text

def test_pptx():
    from pptx import Presentation
    prs = Presentation(); s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text="Compliance"; s.placeholders[1].text="APR"
    buf = io.BytesIO(); prs.save(buf); buf.seek(0)
    assert "Compliance" in parse_pptx(buf.read()).text
```
**Implementation** (`lambda/compliance-ingest/parser.py`):
```python
"""Parser for Word, PPT, PDF reference documents."""
from __future__ import annotations
import io; from dataclasses import dataclass, field

@dataclass
class ParsedContent:
    text: str = ""; tables: list = field(default_factory=list); images: list = field(default_factory=list)

def parse_docx(fb: bytes) -> ParsedContent:
    from docx import Document; doc = Document(io.BytesIO(fb))
    tables = [[[c.text for c in r.cells] for r in t.rows] for t in doc.tables]
    images = [rel.target_part.blob for rel in doc.part.rels.values() if "image" in rel.reltype]
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    for i, tbl in enumerate(tables): text += f"\n[Table {i+1}]\n" + "\n".join(" | ".join(r) for r in tbl)
    return ParsedContent(text=text, tables=tables, images=images)

def parse_pptx(fb: bytes) -> ParsedContent:
    from pptx import Presentation; prs = Presentation(io.BytesIO(fb))
    parts, images, tables = [], [], []
    for n, sl in enumerate(prs.slides, 1):
        parts.append(f"--- Slide {n} ---")
        for s in sl.shapes:
            if s.has_text_frame: parts.append(s.text_frame.text)
            if s.has_table: tables.append([[c.text for c in r.cells] for r in s.table.rows])
            if s.shape_type == 13: images.append(s.image.blob)
    return ParsedContent(text="\n".join(parts), tables=tables, images=images)

def parse_pdf(fb: bytes) -> ParsedContent:
    import pypdf; r = pypdf.PdfReader(io.BytesIO(fb))
    return ParsedContent(text="\n".join(f"--- Page {i+1} ---\n{p.extract_text() or ''}" for i,p in enumerate(r.pages)))
```
**Step 7: Add vision description for extracted images** (inspired by GAIK Vision Parser)

Create `lambda/compliance-ingest/image_describer.py`:
```python
"""Describe embedded images using Bedrock Claude Haiku 4.5 vision.

Adapted from GAIK toolkit's VisionRagParser pattern: classify image type
(chart/diagram/table/photo) and apply a type-specific prompt for concise,
structured descriptions that are injected back into parsed text.
"""
import base64, os, boto3
from botocore.config import Config

bedrock = boto3.client("bedrock-runtime", config=Config(max_pool_connections=10))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

VISION_PROMPTS = {
    "chart": (
        "This is a chart/graph from a financial regulatory document.\n"
        "1. State the title and axis labels if visible.\n"
        "2. List all data points or trends with exact numbers.\n"
        "3. Summarize the key insight in one sentence.\n"
        "Format: [Chart]: [Title] — key values and trend."),
    "diagram": (
        "This is a diagram/flowchart from a compliance document.\n"
        "1. List all nodes/boxes and their connections.\n"
        "2. Describe the flow direction and decision points.\n"
        "Format: [Diagram]: [Title] — nodes → connections → outcome."),
    "table": (
        "This is a table image from a financial document.\n"
        "Reproduce the table in markdown format with exact values.\n"
        "Format: [Table]: markdown table with headers and rows."),
    "default": (
        "Describe this image from a financial regulatory document.\n"
        "Extract all visible text, numbers, and structural information.\n"
        "Format: [Image]: concise factual description."),
}

def describe_images(images: list[bytes], context_hint: str = "") -> list[str]:
    """Send each image to Haiku vision, return text descriptions."""
    descriptions = []
    for img_bytes in images:
        b64 = base64.b64encode(img_bytes).decode()
        # First pass: classify image type
        classify_resp = bedrock.converse(modelId=MODEL_ID, messages=[{"role": "user", "content": [
            {"image": {"format": "png", "source": {"bytes": img_bytes}}},
            {"text": "Classify: is this a chart, diagram, table, or other? One word."}
        ]}], inferenceConfig={"temperature": 0, "maxTokens": 10})
        img_type = classify_resp["output"]["message"]["content"][0]["text"].strip().lower()
        prompt = VISION_PROMPTS.get(img_type, VISION_PROMPTS["default"])
        if context_hint:
            prompt += f"\n\nContext: this appears near text about: {context_hint[:200]}"
        # Second pass: describe with type-specific prompt
        resp = bedrock.converse(modelId=MODEL_ID, messages=[{"role": "user", "content": [
            {"image": {"format": "png", "source": {"bytes": img_bytes}}},
            {"text": prompt}
        ]}], inferenceConfig={"temperature": 0, "maxTokens": 512})
        descriptions.append(resp["output"]["message"]["content"][0]["text"])
    return descriptions
```

Update `parser.py` — after extracting images, call `describe_images()` and append
descriptions to `ParsedContent.text`:
```python
from image_describer import describe_images
# At end of parse_docx / parse_pptx:
if images:
    descs = describe_images(images, context_hint=text[:500])
    text += "\n\n[EMBEDDED IMAGE DESCRIPTIONS]\n" + "\n\n".join(descs)
```

**Cost impact:** ~$0.01 per image (Haiku vision, 2 calls × ~1K tokens). For a 50-page
reference doc with 10 images: ~$0.10 additional. Total ingestion: ~$0.48 (was ~$0.38).

**Run:** `uv run pytest tests/test_compliance_parser.py -v`
**Done when:** All 4 tests pass (docx text+tables, docx images, PDF text, PPTX text).

### Task 6: Implement LLM requirement extraction

**Files:** `lambda/compliance-ingest/extractor.py`, `handler.py`, `tests/test_compliance_extractor.py`  **Test first:**
```python
import json, pytest; from unittest.mock import patch
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'compliance-ingest'))
from extractor import extract_requirements, build_extraction_prompt; from parser import ParsedContent
_rv = lambda t: {"output":{"message":{"content":[{"text":t}]}},"usage":{"inputTokens":1,"outputTokens":1}}

def test_prompt(): assert "APR" in build_extraction_prompt(ParsedContent(text="Must specify APR."))

@patch("extractor.bedrock_client")
def test_parse(m):
    m.converse.return_value = _rv(json.dumps([{"text":"APR","category":"R","sourceReference":"S","evaluationHint":"H"}]))
    r = extract_requirements(ParsedContent(text="doc"))
    assert len(r)==1 and "requirementId" in r[0] and r[0]["criticality"]=="should-have"

@patch("extractor.bedrock_client")
def test_empty(m): m.converse.return_value=_rv("[]"); assert extract_requirements(ParsedContent(text="x"))==[]

@patch("extractor.bedrock_client")
def test_bad(m):
    m.converse.return_value=_rv("bad")
    with pytest.raises(ValueError): extract_requirements(ParsedContent(text="x"))
```
**Implementation** (`lambda/compliance-ingest/extractor.py`):
```python
"""Extract requirements from parsed docs via Bedrock Haiku 4.5."""
from __future__ import annotations
import json, os, re, uuid, boto3; from botocore.config import Config; from parser import ParsedContent

bedrock_client = boto3.client("bedrock-runtime", config=Config(max_pool_connections=10))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

def build_extraction_prompt(content: ParsedContent) -> str:
    return ("Extract all testable compliance requirements from this document.\n\n"
        "DOCUMENT:\n" + content.text[:80_000] + "\n\n"
        'For each: {"text","category","sourceReference","evaluationHint"}. JSON array only.')

def extract_requirements(content: ParsedContent) -> list[dict]:
    resp = bedrock_client.converse(modelId=MODEL_ID,
        messages=[{"role":"user","content":[{"text":build_extraction_prompt(content)}]}],
        inferenceConfig={"temperature":0,"maxTokens":4096})
    raw = re.sub(r"^```(?:json)?\s*|```$","",resp["output"]["message"]["content"][0]["text"].strip())
    try: items = json.loads(raw)
    except json.JSONDecodeError as e: raise ValueError(f"Failed to parse: {e}") from e
    return [{"requirementId":f"req-{uuid.uuid4().hex[:8]}","text":it["text"],
             "category":it.get("category","General"),"sourceReference":it.get("sourceReference",""),
             "evaluationHint":it.get("evaluationHint",""),"criticality":"should-have",
             "confidenceThreshold":0.8,"status":"active"} for it in items]
```
**Handler** (`lambda/compliance-ingest/handler.py`):
```python
"""Compliance Ingest Lambda -- parse docs, extract requirements, store draft baseline."""
from __future__ import annotations
import os; from datetime import datetime, timezone; import boto3
from parser import parse_docx, parse_pptx, parse_pdf; from extractor import extract_requirements
s3, dynamodb = boto3.client("s3"), boto3.resource("dynamodb")
bl_table = dynamodb.Table(os.environ.get("BASELINES_TABLE","compliance-baselines"))
BUCKET = os.environ.get("BUCKET_NAME","")
PARSERS = {"docx": parse_docx, "pptx": parse_pptx, "pdf": parse_pdf}

def lambda_handler(event, context):
    bid, key = event["baselineId"], event["sourceDocumentKey"]
    fmt = event.get("sourceFormat", key.rsplit(".",1)[-1].lower())
    if fmt not in PARSERS: raise ValueError(f"Unsupported: {fmt}")
    reqs = extract_requirements(PARSERS[fmt](s3.get_object(Bucket=BUCKET,Key=key)["Body"].read()))
    cats = sorted(set(r["category"] for r in reqs))
    bl_table.update_item(Key={"baselineId":bid},
        UpdateExpression="SET requirements=:r,categories=:c,sourceDocumentKey=:k,sourceFormat=:f,updatedAt=:n",
        ExpressionAttributeValues={":r":reqs,":c":cats,":k":key,":f":fmt,":n":datetime.now(timezone.utc).isoformat()})
    return {"baselineId": bid, "requirementCount": len(reqs), "categories": cats}
```
**Run:** `uv run pytest tests/test_compliance_extractor.py -v`  **Done when:** All 4 tests pass; handler stores requirements as draft baseline.

---

## Phase 3: Backend — Compliance Evaluation

### Task 7: Implement compliance evaluation Lambda

**File:** `lambda/compliance/evaluate.py`

**Test first** (`tests/test_compliance_evaluate.py`):
```python
"""Unit tests for compliance evaluation Lambda."""
import json, pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_tree():
    return {"structure": [{"title": "Section 3 — Rates", "page_range": [14, 16],
            "node_id": "n1", "nodes": []}], "total_pages": 30}

@pytest.fixture
def sample_baseline():
    return {"baselineId": "bl-1", "version": 1, "requirements": [
        {"requirementId": "req-001", "text": "Must specify APR",
         "category": "Rates", "criticality": "must-have",
         "evaluationHint": "Look for APR, annual percentage rate"},
        {"requirementId": "req-002", "text": "Must include signature page",
         "category": "Execution", "criticality": "must-have",
         "evaluationHint": "Look for signature lines"}]}

@patch("evaluate.bedrock_client")
@patch("evaluate.s3_client")
@patch("evaluate.baselines_table")
def test_evaluate_batches_requirements(mock_bl_table, mock_s3, mock_bedrock,
                                        mock_tree, sample_baseline):
    mock_bl_table.query.return_value = {"Items": [sample_baseline]}
    mock_bedrock.converse.return_value = {
        "output": {"message": {"content": [{"text": json.dumps([
            {"requirementId": "req-001", "verdict": "PASS", "confidence": 0.9,
             "evidence": "Page 15: APR is 6.75%", "pageReferences": [15]},
            {"requirementId": "req-002", "verdict": "FAIL", "confidence": 0.85,
             "evidence": "", "pageReferences": []}])}]}},
        "usage": {"inputTokens": 5000, "outputTokens": 1000}}
    result = evaluate_document("doc-123", "loan_package", mock_tree, b"pdf bytes")
    assert result["overallScore"] == 50  # 1 PASS out of 2
    assert len(result["results"]) == 2
```

**Implementation** (`lambda/compliance/evaluate.py`):
```python
"""Compliance evaluation Lambda — evaluates documents against baselines."""
import json, os, uuid, math
from datetime import datetime, timezone
import boto3
from botocore.config import Config

s3_client = boto3.client("s3")
bedrock_client = boto3.client("bedrock-runtime", config=Config(max_pool_connections=50))
dynamodb = boto3.resource("dynamodb")
baselines_table = dynamodb.Table(os.environ.get("BASELINES_TABLE", "compliance-baselines"))
reports_table = dynamodb.Table(os.environ.get("REPORTS_TABLE", "compliance-reports"))
BATCH_SIZE = int(os.environ.get("REQUIREMENT_BATCH_SIZE", "6"))
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

def lambda_handler(event, context):
    doc_id = event["documentId"]
    plugin_id = event.get("pluginId", "unknown")
    tree = event.get("pageIndexTree") or _load_tree_from_s3(event)
    pdf_bytes = _download_pdf(event)
    report = evaluate_document(doc_id, plugin_id, tree, pdf_bytes)
    _store_report(report)
    return {**event, "complianceReport": {"reportId": report["reportId"],
            "overallScore": report["overallScore"]}}

def evaluate_document(doc_id, plugin_id, tree, pdf_bytes):
    baselines = _find_baselines(plugin_id)
    if not baselines:
        return {"reportId": str(uuid.uuid4()), "documentId": doc_id,
                "overallScore": -1, "results": [], "status": "no_baselines"}
    all_results = []
    for baseline in baselines:
        reqs = baseline.get("requirements", [])
        batches = [reqs[i:i+BATCH_SIZE] for i in range(0, len(reqs), BATCH_SIZE)]
        for batch in batches:
            pages = _navigate_tree_for_batch(tree, batch)
            page_text = _extract_pages(pdf_bytes, pages)
            verdicts = _evaluate_batch(batch, page_text, doc_id, baseline["baselineId"])
            all_results.extend(verdicts)
    pass_count = sum(1 for r in all_results if r["verdict"] == "PASS")
    score = round(pass_count / len(all_results) * 100) if all_results else 0
    return {"reportId": str(uuid.uuid4()), "documentId": doc_id,
            "baselineId": baselines[0]["baselineId"],
            "baselineVersion": baselines[0].get("version", 1),
            "status": "completed", "overallScore": score,
            "results": all_results,
            "evaluatedAt": datetime.now(timezone.utc).isoformat()}

def _find_baselines(plugin_id):
    resp = baselines_table.query(
        IndexName="pluginId-index",
        KeyConditionExpression="pluginIds = :pid AND #s = :pub",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":pid": plugin_id, ":pub": "published"})
    return resp.get("Items", [])

def _navigate_tree_for_batch(tree, batch):
    """Use LLM to find relevant pages for a batch of requirements."""
    hints = "\n".join(f"- {r['text']} (hint: {r.get('evaluationHint','')})" for r in batch)
    compact = json.dumps([{"title": n["title"], "pages": n.get("page_range")}
                          for n in tree.get("structure", [])], indent=1)
    prompt = (f"Given these requirements:\n{hints}\n\n"
              f"And this document structure:\n{compact}\n\n"
              "Return a JSON array of page numbers (integers) to examine.")
    resp = bedrock_client.converse(modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 512})
    text = resp["output"]["message"]["content"][0]["text"]
    return _parse_page_list(text)

def _evaluate_batch(batch, page_text, doc_id, baseline_id):
    """Evaluate a batch of requirements against page content."""
    # Few-shot corrections injected here — see Task 8
    corrections_block = _get_corrections_block(baseline_id, batch)
    reqs_text = "\n".join(f"{i+1}. [{r['requirementId']}] {r['text']}\n"
        f"   Hint: {r.get('evaluationHint','')}" for i, r in enumerate(batch))
    prompt = (f"Evaluate these compliance requirements against the document.\n\n"
              f"{corrections_block}"
              f"REQUIREMENTS:\n{reqs_text}\n\nDOCUMENT CONTENT:\n{page_text}\n\n"
              "Respond with a JSON array: [{requirementId, verdict, confidence, "
              "evidence, evidenceCharStart, evidenceCharEnd, pageReferences}].\n"
              "IMPORTANT: 'evidence' must be an EXACT quote from the document "
              "(copy-paste, not paraphrased). 'evidenceCharStart' and "
              "'evidenceCharEnd' are the 0-based character offsets of the quote "
              "within the page text provided. Verdicts: PASS/FAIL/PARTIAL/NOT_FOUND.")
    resp = bedrock_client.converse(modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 2048})
    return json.loads(resp["output"]["message"]["content"][0]["text"])
```

**Run:** `uv run pytest tests/test_compliance_evaluate.py -v`

### Task 8: Integrate few-shot learning from feedback

**Files:** `lambda/compliance/evaluate.py` (modify `_get_corrections_block`), `tests/test_compliance_feedback.py`

**Test first** (`tests/test_compliance_feedback.py`):
```python
"""Unit tests for few-shot feedback injection."""
import json, pytest
from unittest.mock import patch, MagicMock

SAMPLE_FEEDBACK = [
    {"requirementId": "req-001", "originalVerdict": "FAIL",
     "correctedVerdict": "PASS",
     "reviewerNote": "APR was stated as 'annual interest rate' — treat as equivalent"},
    {"requirementId": "req-003", "originalVerdict": "PASS",
     "correctedVerdict": "PARTIAL",
     "reviewerNote": "Signature present but missing notarization"},
]

@patch("evaluate.feedback_table")
def test_corrections_block_includes_feedback(mock_fb_table):
    mock_fb_table.query.return_value = {"Items": SAMPLE_FEEDBACK}
    from evaluate import _get_corrections_block
    block = _get_corrections_block("bl-1", [{"requirementId": "req-001"}])
    assert "PRIOR CORRECTIONS" in block
    assert "annual interest rate" in block
    assert "treat as equivalent" in block

@patch("evaluate.feedback_table")
def test_corrections_block_empty_when_no_feedback(mock_fb_table):
    mock_fb_table.query.return_value = {"Items": []}
    from evaluate import _get_corrections_block
    block = _get_corrections_block("bl-1", [{"requirementId": "req-001"}])
    assert block == ""

@patch("evaluate.feedback_table")
def test_corrections_limited_to_5(mock_fb_table):
    items = [{"requirementId": f"req-{i:03d}", "originalVerdict": "FAIL",
              "correctedVerdict": "PASS", "reviewerNote": f"Note {i}"}
             for i in range(10)]
    mock_fb_table.query.return_value = {"Items": items}
    from evaluate import _get_corrections_block
    block = _get_corrections_block("bl-1", [{"requirementId": "req-001"}])
    # Should contain at most 5 correction entries
    assert block.count("was marked") <= 5
```

**Implementation** (add to `lambda/compliance/evaluate.py`):
```python
feedback_table = dynamodb.Table(
    os.environ.get("FEEDBACK_TABLE", "compliance-feedback"))
MAX_CORRECTIONS = int(os.environ.get("MAX_CORRECTIONS", "5"))

def _get_corrections_block(baseline_id: str, batch: list[dict]) -> str:
    """Query compliance-feedback table for recent reviewer corrections.

    Returns a formatted "PRIOR CORRECTIONS" block for prompt injection,
    or empty string if no feedback exists.
    """
    req_ids = {r["requirementId"] for r in batch}
    all_corrections = []
    for req_id in req_ids:
        try:
            resp = feedback_table.query(
                IndexName="requirementId-index",
                KeyConditionExpression="requirementId = :rid",
                ExpressionAttributeValues={":rid": req_id},
                ScanIndexForward=False,  # newest first
                Limit=3,  # up to 3 per requirement
            )
            all_corrections.extend(resp.get("Items", []))
        except Exception as e:
            print(f"[Compliance] Feedback query failed for {req_id}: {e}")
    if not all_corrections:
        return ""
    # Sort by createdAt descending, take top MAX_CORRECTIONS
    all_corrections.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    corrections = all_corrections[:MAX_CORRECTIONS]
    lines = ["PRIOR CORRECTIONS (learn from these reviewer corrections):"]
    for c in corrections:
        lines.append(
            f"- Requirement \"{c['requirementId']}\" was marked "
            f"{c['originalVerdict']} but reviewer corrected to "
            f"{c['correctedVerdict']}: {c.get('reviewerNote', '')}")
    return "\n".join(lines) + "\n\n"
```

**Key design:** Corrections are injected per-batch, not globally. Only feedback for
requirements in the current batch is included — avoids bloating the prompt for
unrelated requirements. Limited to 5 most recent corrections total.

**Run:** `uv run pytest tests/test_compliance_feedback.py -v`

---

## Phase 4: Backend — API Endpoints

### Task 9: Add baseline CRUD API endpoints

**File:** `lambda/api/handler.py` (add routes ~line 2149), `tests/test_api_baselines.py`

**Test first** (`tests/test_api_baselines.py`):
```python
"""Unit tests for baseline CRUD API routes."""
import json, pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

@patch("handler.dynamodb")
def test_list_baselines(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.scan.return_value = {"Items": [
        {"baselineId": "bl-1", "name": "OCC Reqs", "status": "published"}]}
    from handler import list_baselines
    result = list_baselines({"status": "published"})
    assert len(result["baselines"]) == 1
    assert result["baselines"][0]["status"] == "published"

@patch("handler.dynamodb")
def test_create_baseline(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    from handler import create_baseline
    result = create_baseline({"name": "Test", "description": "Desc",
                              "pluginIds": ["loan_package"]}, "user-1")
    assert "baselineId" in result
    table.put_item.assert_called_once()

@patch("handler.dynamodb")
def test_publish_baseline(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {"Item": {"baselineId": "bl-1",
        "status": "draft", "version": 1, "requirements": [{"requirementId": "r1"}]}}
    from handler import publish_baseline
    result = publish_baseline("bl-1")
    assert result["status"] == "published"
```

**Implementation** (add to `lambda/api/handler.py`):

1. Add table reference at module level (~line 30):
```python
BASELINES_TABLE = os.environ.get("BASELINES_TABLE", "compliance-baselines")
```

2. Add routes after the `/plugins/refine` block (~line 2149):
```python
        elif path == "/baselines" and http_method == "GET":
            return response(200, list_baselines(query_params))

        elif path == "/baselines" and http_method == "POST":
            return response(200, create_baseline(body or {}, user))

        elif path.startswith("/baselines/") and "/publish" in path and http_method == "POST":
            baseline_id = path.split("/")[2]
            return response(200, publish_baseline(baseline_id))

        elif path.startswith("/baselines/") and "/requirements" in path and http_method == "POST":
            baseline_id = path.split("/")[2]
            return response(200, add_requirement(baseline_id, body or {}))

        elif path.startswith("/baselines/") and "/requirements/" in path and http_method == "PUT":
            parts = path.split("/")
            return response(200, update_requirement(parts[2], parts[4], body or {}))

        elif path.startswith("/baselines/") and "/requirements/" in path and http_method == "DELETE":
            parts = path.split("/")
            return response(200, delete_requirement(parts[2], parts[4]))

        elif path.startswith("/baselines/") and http_method == "GET":
            baseline_id = path.split("/")[2]
            return response(200, get_baseline(baseline_id))

        elif path.startswith("/baselines/") and http_method == "PUT":
            baseline_id = path.split("/")[2]
            return response(200, update_baseline(baseline_id, body or {}))

        elif path.startswith("/baselines/") and http_method == "DELETE":
            baseline_id = path.split("/")[2]
            return response(200, archive_baseline(baseline_id))
```

3. Add handler functions:
```python
def list_baselines(params):
    bl_table = dynamodb.Table(BASELINES_TABLE)
    kwargs = {}
    status_filter = params.get("status")
    if status_filter:
        kwargs["FilterExpression"] = "#s = :s"
        kwargs["ExpressionAttributeNames"] = {"#s": "status"}
        kwargs["ExpressionAttributeValues"] = {":s": status_filter}
    resp = bl_table.scan(**kwargs)
    return {"baselines": resp.get("Items", [])}

def create_baseline(body, user):
    bl_table = dynamodb.Table(BASELINES_TABLE)
    baseline_id = f"bl-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    item = {"baselineId": baseline_id, "name": body["name"],
            "description": body.get("description", ""),
            "pluginIds": body.get("pluginIds", []),
            "status": "draft", "version": 0, "requirements": [],
            "categories": [], "createdBy": user or "anonymous",
            "createdAt": now, "updatedAt": now}
    bl_table.put_item(Item=item)
    return item

def publish_baseline(baseline_id):
    bl_table = dynamodb.Table(BASELINES_TABLE)
    resp = bl_table.get_item(Key={"baselineId": baseline_id})
    item = resp.get("Item")
    if not item:
        return {"error": "Baseline not found"}
    if not item.get("requirements"):
        return {"error": "Cannot publish baseline with no requirements"}
    now = datetime.now(timezone.utc).isoformat()
    bl_table.update_item(Key={"baselineId": baseline_id},
        UpdateExpression="SET #s = :s, version = version + :one, updatedAt = :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "published", ":one": 1, ":now": now})
    return {"baselineId": baseline_id, "status": "published",
            "version": item.get("version", 0) + 1}
```

**Run:** `uv run pytest tests/test_api_baselines.py -v`

### Task 10: Add compliance report + reviewer override API endpoints

**File:** `lambda/api/handler.py` (add routes), `tests/test_api_compliance_reports.py`

**Test first** (`tests/test_api_compliance_reports.py`):
```python
"""Unit tests for compliance report + reviewer override API."""
import json, pytest
from unittest.mock import patch, MagicMock

@patch("handler.dynamodb")
def test_get_compliance_reports(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.query.return_value = {"Items": [
        {"reportId": "rpt-1", "documentId": "doc-1", "overallScore": 85,
         "status": "completed", "results": []}]}
    from handler import get_compliance_reports
    result = get_compliance_reports("doc-1")
    assert len(result["reports"]) == 1
    assert result["reports"][0]["overallScore"] == 85

@patch("handler.dynamodb")
def test_submit_reviewer_override(mock_dynamo):
    reports_tbl = MagicMock()
    feedback_tbl = MagicMock()
    mock_dynamo.Table.side_effect = lambda name: (
        reports_tbl if "reports" in name else feedback_tbl)
    reports_tbl.get_item.return_value = {"Item": {
        "reportId": "rpt-1", "documentId": "doc-1", "baselineId": "bl-1",
        "results": [{"requirementId": "req-001", "verdict": "FAIL",
                      "confidence": 0.9}]}}
    from handler import submit_compliance_review
    result = submit_compliance_review("doc-1", "rpt-1", {
        "overrides": [{"requirementId": "req-001",
                        "correctedVerdict": "PASS",
                        "reviewerNote": "Rate was stated differently"}]},
        "reviewer-1")
    assert result["status"] == "reviewed"
    feedback_tbl.put_item.assert_called_once()
```

**Implementation** (add to `lambda/api/handler.py`):

1. Add table references:
```python
REPORTS_TABLE = os.environ.get("REPORTS_TABLE", "compliance-reports")
FEEDBACK_TABLE = os.environ.get("FEEDBACK_TABLE", "compliance-feedback")
```

2. Add routes (after baselines routes):
```python
        elif (path.startswith("/documents/") and "/compliance/" in path
              and "/review" in path and http_method == "POST"):
            parts = path.split("/")
            return response(200, submit_compliance_review(
                parts[2], parts[4], body or {}, user))

        elif (path.startswith("/documents/") and "/compliance/" in path
              and http_method == "GET"):
            parts = path.split("/")
            return response(200, get_compliance_report(parts[2], parts[4]))

        elif (path.startswith("/documents/") and "/compliance" in path
              and http_method == "GET"):
            return response(200, get_compliance_reports(_doc_id()))
```

**Important:** Place the `/compliance/:reportId/review` route BEFORE
`/compliance/:reportId` and `/compliance` to avoid prefix conflicts (same
pattern used throughout this handler — more specific paths first).

3. Add handler functions:
```python
def get_compliance_reports(document_id):
    rpt_table = dynamodb.Table(REPORTS_TABLE)
    resp = rpt_table.query(IndexName="documentId-index",
        KeyConditionExpression="documentId = :did",
        ExpressionAttributeValues={":did": document_id},
        ScanIndexForward=False)
    return {"reports": resp.get("Items", [])}

def get_compliance_report(document_id, report_id):
    rpt_table = dynamodb.Table(REPORTS_TABLE)
    resp = rpt_table.get_item(Key={"reportId": report_id, "documentId": document_id})
    item = resp.get("Item")
    return {"report": item} if item else {"error": "Report not found"}

def submit_compliance_review(document_id, report_id, body, user):
    rpt_table = dynamodb.Table(REPORTS_TABLE)
    fb_table = dynamodb.Table(FEEDBACK_TABLE)
    resp = rpt_table.get_item(Key={"reportId": report_id, "documentId": document_id})
    report = resp.get("Item")
    if not report:
        return {"error": "Report not found"}
    overrides = body.get("overrides", [])
    now = datetime.now(timezone.utc).isoformat()
    results_map = {r["requirementId"]: r for r in report.get("results", [])}
    for ov in overrides:
        req_id = ov["requirementId"]
        original = results_map.get(req_id, {})
        # Update verdict in report
        original["reviewerOverride"] = ov["correctedVerdict"]
        original["reviewerNote"] = ov.get("reviewerNote", "")
        results_map[req_id] = original
        # Create feedback record for learning loop
        fb_table.put_item(Item={
            "feedbackId": f"fb-{uuid.uuid4().hex[:12]}",
            "baselineId": report["baselineId"],
            "requirementId": req_id, "documentId": document_id,
            "originalVerdict": original.get("verdict", ""),
            "correctedVerdict": ov["correctedVerdict"],
            "reviewerNote": ov.get("reviewerNote", ""),
            "createdAt": now})
    rpt_table.update_item(Key={"reportId": report_id, "documentId": document_id},
        UpdateExpression="SET results = :r, #s = :s, reviewedBy = :u, reviewedAt = :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":r": list(results_map.values()),
            ":s": "reviewed", ":u": user or "anonymous", ":now": now})
    return {"reportId": report_id, "status": "reviewed", "overrideCount": len(overrides)}
```

**Run:** `uv run pytest tests/test_api_compliance_reports.py -v`

---

## Phase 5: Frontend — Baseline Management

### Task 11: Add baseline list page

**Files:** `frontend/src/pages/Baselines.tsx`, `frontend/src/services/api.ts`, `frontend/src/App.tsx`

**Test first** (`frontend/src/__tests__/Baselines.test.tsx`):
```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Baselines from '../pages/Baselines';
import { api } from '../services/api';
import { vi } from 'vitest';

vi.mock('../services/api');

test('renders baselines list with status badges', async () => {
  (api.listBaselines as any).mockResolvedValue({ baselines: [
    { baselineId: 'bl-1', name: 'OCC Mortgage', status: 'published',
      pluginIds: ['loan_package'], requirements: [{}, {}, {}] },
    { baselineId: 'bl-2', name: 'Draft Test', status: 'draft',
      pluginIds: [], requirements: [] },
  ]});
  const qc = new QueryClient();
  render(<QueryClientProvider client={qc}><MemoryRouter>
    <Baselines /></MemoryRouter></QueryClientProvider>);
  await waitFor(() => {
    expect(screen.getByText('OCC Mortgage')).toBeInTheDocument();
    expect(screen.getByText('published')).toBeInTheDocument();
    expect(screen.getByText('3 requirements')).toBeInTheDocument();
    expect(screen.getByText('Draft Test')).toBeInTheDocument();
  });
});

test('shows create baseline button', async () => {
  (api.listBaselines as any).mockResolvedValue({ baselines: [] });
  const qc = new QueryClient();
  render(<QueryClientProvider client={qc}><MemoryRouter>
    <Baselines /></MemoryRouter></QueryClientProvider>);
  await waitFor(() => {
    expect(screen.getByText(/create baseline/i)).toBeInTheDocument();
  });
});
```

**Implementation** (`frontend/src/pages/Baselines.tsx`):
```tsx
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { Shield, Plus, FileText, Archive } from 'lucide-react';

const statusColors: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-700',
  published: 'bg-green-100 text-green-700',
  archived: 'bg-gray-100 text-gray-500',
};

export default function Baselines() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('');
  const { data, isLoading } = useQuery({
    queryKey: ['baselines', statusFilter],
    queryFn: () => api.listBaselines({ status: statusFilter || undefined }),
  });
  const createMutation = useMutation({
    mutationFn: (body: { name: string; description: string }) =>
      api.createBaseline(body),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['baselines'] });
      navigate(`/baselines/${result.baselineId}`);
    },
  });
  const baselines = data?.baselines || [];
  return (
    <div className="h-full overflow-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="w-6 h-6" /> Compliance Baselines
        </h1>
        <button onClick={() => createMutation.mutate({
          name: 'New Baseline', description: '' })}
          className="btn-primary flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Create Baseline
        </button>
      </div>
      {/* Status filter tabs */}
      <div className="flex gap-2 mb-4">
        {['', 'draft', 'published', 'archived'].map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 rounded text-sm ${statusFilter === s
              ? 'bg-primary-100 text-primary-700' : 'text-gray-500 hover:bg-gray-100'}`}>
            {s || 'All'}
          </button>))}
      </div>
      {isLoading ? <div className="animate-spin h-8 w-8 border-b-2 border-primary-600 rounded-full mx-auto" />
       : <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {baselines.map((bl: any) => (
          <Link key={bl.baselineId} to={`/baselines/${bl.baselineId}`}
            className="border rounded-lg p-4 hover:shadow-md transition-shadow bg-white">
            <div className="flex items-start justify-between">
              <h3 className="font-semibold text-gray-900">{bl.name}</h3>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                statusColors[bl.status] || 'bg-gray-100'}`}>{bl.status}</span>
            </div>
            <p className="text-sm text-gray-500 mt-1">{bl.description || 'No description'}</p>
            <div className="flex items-center gap-3 mt-3 text-xs text-gray-400">
              <span>{(bl.requirements || []).length} requirements</span>
              <span>{(bl.pluginIds || []).join(', ') || 'Standalone'}</span>
            </div>
          </Link>))}
      </div>}
    </div>);
}
```

**Add API methods** (`frontend/src/services/api.ts`):
```typescript
  listBaselines: (params?: { status?: string }) =>
    fetchApi<{ baselines: any[] }>(`/baselines${params?.status ? `?status=${params.status}` : ''}`),
  createBaseline: (body: { name: string; description: string; pluginIds?: string[] }) =>
    fetchApi<any>('/baselines', { method: 'POST', body: JSON.stringify(body) }),
```

**Add route** (`frontend/src/App.tsx` — after `/config/:pluginId` route):
```tsx
import Baselines from './pages/Baselines';
// Inside <Routes>:
<Route path="/baselines" element={<ProtectedRoute><Layout><Baselines /></Layout></ProtectedRoute>} />
```

**Run:** `cd frontend && npx vitest run src/__tests__/Baselines.test.tsx`

### Task 12: Add baseline editor page

**Files:** `frontend/src/pages/BaselineEditor.tsx`, `frontend/src/services/api.ts`, `frontend/src/App.tsx`

**Test first** (`frontend/src/__tests__/BaselineEditor.test.tsx`):
```tsx
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import BaselineEditor from '../pages/BaselineEditor';
import { api } from '../services/api';
import { vi } from 'vitest';

vi.mock('../services/api');

const MOCK_BASELINE = {
  baselineId: 'bl-1', name: 'OCC Mortgage', status: 'draft', version: 0,
  description: 'Mortgage compliance', pluginIds: ['loan_package'],
  categories: ['Rates', 'Execution'],
  requirements: [
    { requirementId: 'req-001', text: 'Must specify APR',
      category: 'Rates', criticality: 'must-have', status: 'active' },
    { requirementId: 'req-002', text: 'Must include signature',
      category: 'Execution', criticality: 'should-have', status: 'active' },
  ],
};

test('renders requirements list and allows inline editing', async () => {
  (api.getBaseline as any).mockResolvedValue({ baseline: MOCK_BASELINE });
  const qc = new QueryClient();
  render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={['/baselines/bl-1']}>
    <Routes><Route path="/baselines/:baselineId" element={<BaselineEditor />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
  await waitFor(() => {
    expect(screen.getByText('OCC Mortgage')).toBeInTheDocument();
    expect(screen.getByText('Must specify APR')).toBeInTheDocument();
    expect(screen.getByText('Must include signature')).toBeInTheDocument();
    expect(screen.getByText('must-have')).toBeInTheDocument();
  });
});

test('shows publish button for draft baselines', async () => {
  (api.getBaseline as any).mockResolvedValue({ baseline: MOCK_BASELINE });
  const qc = new QueryClient();
  render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={['/baselines/bl-1']}>
    <Routes><Route path="/baselines/:baselineId" element={<BaselineEditor />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(screen.getByText(/publish/i)).toBeInTheDocument());
});
```

**Implementation** (`frontend/src/pages/BaselineEditor.tsx`):
```tsx
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { Shield, Plus, Trash2, Save, Send, Pencil } from 'lucide-react';

const criticalityColors: Record<string, string> = {
  'must-have': 'bg-red-100 text-red-700',
  'should-have': 'bg-yellow-100 text-yellow-700',
  'nice-to-have': 'bg-blue-100 text-blue-700',
};

export default function BaselineEditor() {
  const { baselineId } = useParams<{ baselineId: string }>();
  const queryClient = useQueryClient();
  const [editingReq, setEditingReq] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
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
```

**Add API methods** (`frontend/src/services/api.ts`):
```typescript
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
```

**Add route** (`frontend/src/App.tsx`):
```tsx
import BaselineEditor from './pages/BaselineEditor';
// Inside <Routes>, after /baselines route:
<Route path="/baselines/:baselineId" element={
  <ProtectedRoute><Layout><BaselineEditor /></Layout></ProtectedRoute>} />
```

**Run:** `cd frontend && npx vitest run src/__tests__/BaselineEditor.test.tsx`

---

## Phase 6: Frontend — Compliance Results

### Task 13: Add Compliance tab to DocumentViewer

**Files:**
- Create: `frontend/src/components/ComplianceTab.tsx`
- Create: `frontend/src/components/VerdictBadge.tsx`
- Create: `frontend/src/components/ComplianceScoreGauge.tsx`
- Modify: `frontend/src/components/DataViewTabs.tsx` (add tab)
- Modify: `frontend/src/components/DocumentViewer.tsx` (render tab content)
- Modify: `frontend/src/services/api.ts` (add compliance API)

**Step 1: Add API method** (`frontend/src/services/api.ts`):
```typescript
  getComplianceReports: (documentId: string) =>
    fetchApi<{ reports: any[] }>(`/documents/${documentId}/compliance`),
```

**Step 2: Create VerdictBadge** (`frontend/src/components/VerdictBadge.tsx`):
```tsx
const colors: Record<string, string> = {
  PASS: 'bg-green-100 text-green-700', FAIL: 'bg-red-100 text-red-700',
  PARTIAL: 'bg-yellow-100 text-yellow-700', NOT_FOUND: 'bg-gray-100 text-gray-500',
};
export default function VerdictBadge({ verdict }: { verdict: string }) {
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${
    colors[verdict] || 'bg-gray-100'}`}>{verdict}</span>;
}
```

**Step 3: Create ComplianceScoreGauge** (`frontend/src/components/ComplianceScoreGauge.tsx`):
```tsx
export default function ComplianceScoreGauge({ score }: { score: number }) {
  const color = score >= 90 ? 'text-green-600' : score >= 50 ? 'text-yellow-600' : 'text-red-600';
  const radius = 40, circ = 2 * Math.PI * radius, offset = circ - (score / 100) * circ;
  return (
    <div className="flex flex-col items-center">
      <svg width="100" height="100" className="-rotate-90">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#e5e7eb" strokeWidth="8" />
        <circle cx="50" cy="50" r={radius} fill="none" stroke="currentColor"
          strokeWidth="8" strokeDasharray={circ} strokeDashoffset={offset}
          className={color} strokeLinecap="round" />
      </svg>
      <span className={`text-2xl font-bold -mt-16 ${color}`}>{score}%</span>
      <span className="text-xs text-gray-500 mt-1">Compliance</span>
    </div>);
}
```

**Step 4: Create ComplianceTab** (`frontend/src/components/ComplianceTab.tsx`):
```tsx
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import VerdictBadge from './VerdictBadge';
import ComplianceScoreGauge from './ComplianceScoreGauge';

interface Props { documentId: string; onPageClick?: (page: number) => void; }

export default function ComplianceTab({ documentId, onPageClick }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['compliance', documentId],
    queryFn: () => api.getComplianceReports(documentId),
  });
  if (isLoading) return <div className="p-4 text-gray-500">Loading compliance...</div>;
  const reports = data?.reports || [];
  if (!reports.length) return <div className="p-4 text-gray-400">No compliance reports.</div>;
  const report = reports[0]; // most recent
  return (
    <div className="p-4 overflow-auto space-y-4">
      <ComplianceScoreGauge score={report.overallScore} />
      <div className="space-y-2">
        {(report.results || []).map((r: any) => (
          <div key={r.requirementId} className="border rounded p-3 bg-white">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{r.requirementId}</span>
              <VerdictBadge verdict={r.reviewerOverride || r.verdict} />
            </div>
            {r.evidence && (
              <p className="text-xs text-gray-600 mt-1 cursor-pointer hover:text-primary-600"
                onClick={() => r.pageReferences?.[0] && onPageClick?.(r.pageReferences[0])}
                title={r.evidenceCharStart != null
                  ? `Chars ${r.evidenceCharStart}–${r.evidenceCharEnd} on page ${r.pageReferences?.[0]}`
                  : undefined}>
                <span className="bg-yellow-100 px-0.5 rounded">{r.evidence}</span>
              </p>)}
            {/* Character-offset grounding: when PDF viewer supports text
                selection, use evidenceCharStart/End to auto-highlight the
                exact quote on the page. For now, yellow background + page
                jump provides the visual anchor. Inspired by LangExtract's
                source grounding pattern. */}
          </div>))}
      </div>
    </div>);
}
```

**Step 5: Add tab to DataViewTabs** (`frontend/src/components/DataViewTabs.tsx`):
Add to the `tabs` array:
```typescript
  { id: 'compliance', label: 'Compliance', icon: Shield },
```
Import `Shield` from `lucide-react`. Update `DataViewTab` type to include `'compliance'`.

**Step 6: Render in DocumentViewer** (`frontend/src/components/DocumentViewer.tsx`):
After the JSON tab conditional:
```tsx
{activeTab === 'compliance' && (
  <ComplianceTab documentId={documentId} onPageClick={handlePageClick} />
)}
```

**Run:** `cd frontend && npx vitest run --reporter=verbose 2>&1 | head -20`
**Done when:** Compliance tab renders with score gauge and verdict badges.

### Task 14: Add reviewer override UI

**Files:**
- Create: `frontend/src/components/ReviewerOverride.tsx`
- Modify: `frontend/src/components/ComplianceTab.tsx` (add override button per result)
- Modify: `frontend/src/services/api.ts` (add review endpoint)

**Step 1: Add API method** (`frontend/src/services/api.ts`):
```typescript
  submitComplianceReview: (documentId: string, reportId: string, body: any) =>
    fetchApi<any>(`/documents/${documentId}/compliance/${reportId}/review`,
      { method: 'POST', body: JSON.stringify(body) }),
```

**Step 2: Create ReviewerOverride** (`frontend/src/components/ReviewerOverride.tsx`):
```tsx
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

interface Props { documentId: string; reportId: string; requirementId: string;
  currentVerdict: string; onClose: () => void; }

const VERDICTS = ['PASS', 'FAIL', 'PARTIAL', 'NOT_FOUND'];

export default function ReviewerOverride({ documentId, reportId,
  requirementId, currentVerdict, onClose }: Props) {
  const [verdict, setVerdict] = useState(currentVerdict);
  const [note, setNote] = useState('');
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.submitComplianceReview(documentId, reportId, {
      overrides: [{ requirementId, correctedVerdict: verdict, reviewerNote: note }] }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['compliance'] }); onClose(); },
  });
  return (
    <div className="border rounded p-3 bg-gray-50 mt-2 space-y-2">
      <div className="flex gap-2">
        {VERDICTS.map(v => (
          <button key={v} onClick={() => setVerdict(v)}
            className={`px-2 py-1 text-xs rounded ${v === verdict
              ? 'bg-primary-600 text-white' : 'bg-white border'}`}>{v}</button>))}
      </div>
      <textarea value={note} onChange={e => setNote(e.target.value)}
        placeholder="Explain the correction..."
        className="w-full border rounded p-2 text-sm h-16" />
      <div className="flex gap-2">
        <button onClick={() => mutation.mutate()}
          className="btn-primary text-xs px-3 py-1">Submit</button>
        <button onClick={onClose} className="text-xs text-gray-500">Cancel</button>
      </div>
    </div>);
}
```

**Step 3: Integrate into ComplianceTab** — Add an "Override" button next to each verdict badge. When clicked, show `ReviewerOverride` inline below the result row. Pass `reportId` and `requirementId`.

**Run:** `cd frontend && npx vitest run --reporter=verbose 2>&1 | head -20`
**Done when:** Clicking Override opens inline form, submit updates verdict and creates feedback.

---

## Phase 7: Integration & Polish

### Task 15: Upload flow baseline selection

**Files:**
- Modify: `frontend/src/pages/Upload.tsx` (add baseline dropdown)
- Modify: `frontend/src/services/api.ts` (pass baselineIds in upload metadata)

**Step 1: Add baseline selector to Upload page**

In `Upload.tsx`, add a `useQuery` to fetch published baselines:
```tsx
const { data: baselinesData } = useQuery({
  queryKey: ['baselines', 'published'],
  queryFn: () => api.listBaselines({ status: 'published' }),
});
const [selectedBaselines, setSelectedBaselines] = useState<string[]>([]);
```

**Step 2: Add dropdown UI** — After the file drop zone, before the upload button:
```tsx
<div className="mt-4">
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Evaluate against baselines (optional)
  </label>
  <div className="space-y-1">
    {(baselinesData?.baselines || []).map((bl: any) => (
      <label key={bl.baselineId} className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={selectedBaselines.includes(bl.baselineId)}
          onChange={(e) => setSelectedBaselines(prev =>
            e.target.checked ? [...prev, bl.baselineId]
              : prev.filter(id => id !== bl.baselineId))} />
        {bl.name} <span className="text-gray-400">({bl.requirements?.length || 0} reqs)</span>
      </label>))}
  </div>
</div>
```

**Step 3: Pass baselineIds in upload metadata** — Include `selectedBaselines` in the upload request metadata so the trigger Lambda can pass them to Step Functions.

**Run:** `cd frontend && npm run dev` → Upload page shows baseline checkboxes.
**Done when:** Published baselines appear as checkboxes, selection is included in upload metadata.

### Task 16: Work queue compliance badges

**Files:**
- Modify: `frontend/src/pages/WorkQueue.tsx` (add compliance badge per document)
- Modify: `frontend/src/services/api.ts` (compliance data in document list response)

**Step 1: Add compliance score badge component inline**

In `WorkQueue.tsx`, after the existing status badge for each document card:
```tsx
{doc.complianceScore != null && doc.complianceScore >= 0 ? (
  <span className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${
    doc.complianceScore >= 90 ? 'bg-green-100 text-green-700'
    : doc.complianceScore >= 50 ? 'bg-yellow-100 text-yellow-700'
    : 'bg-red-100 text-red-700'}`}>
    {doc.complianceScore}% compliant
  </span>
) : (
  <span className="ml-2 px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-400">
    N/A
  </span>
)}
```

**Step 2: Add compliance filter** — Add filter tabs alongside existing status filter:
```tsx
const [complianceFilter, setComplianceFilter] = useState<string>('all');
// Filter options: all, compliant (>90%), non-compliant (<90%), not-evaluated
```

Apply filter to the document list before rendering.

**Step 3: Backend support** — The `complianceScore` field should be written to the
main `financial-documents` DynamoDB table by the compliance-evaluate Lambda
(in `_store_report`), so it's available in the document list API without a join.

**Run:** `cd frontend && npm run dev` → Work Queue shows compliance badges.
**Done when:** Each document card shows a color-coded compliance score badge.

### Task 17: End-to-end integration test

**Files:**
- Create: `scripts/test-compliance-e2e.sh`

**Step 1: Create e2e test script** (`scripts/test-compliance-e2e.sh`):
```bash
#!/bin/bash
# End-to-end compliance engine test
source "$(dirname "$0")/common.sh"
set -euo pipefail

echo "=== Step 1: Create a draft baseline ==="
BASELINE=$(curl -s -X POST "$API_URL/baselines" \
  -H "Content-Type: application/json" \
  -d '{"name":"E2E Test Baseline","description":"Test","pluginIds":["loan_package"]}')
BL_ID=$(echo "$BASELINE" | jq -r '.baselineId')
echo "Created baseline: $BL_ID"

echo "=== Step 2: Add requirements ==="
curl -s -X POST "$API_URL/baselines/$BL_ID/requirements" \
  -H "Content-Type: application/json" \
  -d '{"text":"Must specify interest rate","category":"Rates","criticality":"must-have",
       "evaluationHint":"Look for APR, interest rate, annual percentage"}'

echo "=== Step 3: Publish baseline ==="
curl -s -X POST "$API_URL/baselines/$BL_ID/publish"

echo "=== Step 4: Upload a test document ==="
# Uses existing upload-test-doc.sh flow
DOC_ID=$(bash scripts/upload-test-doc.sh tests/sample-documents/sample-loan.pdf | grep documentId | jq -r '.documentId')
echo "Uploaded document: $DOC_ID"

echo "=== Step 5: Wait for Step Functions to complete ==="
for i in $(seq 1 30); do
  STATUS=$(curl -s "$API_URL/documents/$DOC_ID/status" | jq -r '.status')
  echo "  Status: $STATUS (attempt $i/30)"
  [ "$STATUS" = "completed" ] && break
  sleep 10
done

echo "=== Step 6: Check compliance report ==="
REPORT=$(curl -s "$API_URL/documents/$DOC_ID/compliance")
echo "$REPORT" | jq .
SCORE=$(echo "$REPORT" | jq '.reports[0].overallScore // -1')
echo "Compliance score: $SCORE"

echo "=== Step 7: Cleanup ==="
curl -s -X DELETE "$API_URL/baselines/$BL_ID"
echo "Done. Baseline archived."
```

**Run:** `bash scripts/test-compliance-e2e.sh`

**Expected output:**
- Baseline created and published
- Document uploaded and processed
- Compliance report with per-requirement verdicts
- Score >= 0 (not -1)

**Done when:** Script runs end-to-end without errors and compliance report is returned.
