"""Compliance evaluation — evaluates documents against baselines."""
from __future__ import annotations

import io
import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3
from botocore.config import Config

s3_client = boto3.client("s3")
bedrock_client = boto3.client(
    "bedrock-runtime", config=Config(max_pool_connections=50)
)
dynamodb = boto3.resource("dynamodb")
baselines_table = dynamodb.Table(
    os.environ.get("BASELINES_TABLE", "compliance-baselines")
)
reports_table = dynamodb.Table(
    os.environ.get("REPORTS_TABLE", "compliance-reports")
)
feedback_table = dynamodb.Table(
    os.environ.get("FEEDBACK_TABLE", "compliance-feedback")
)
BATCH_SIZE = int(os.environ.get("REQUIREMENT_BATCH_SIZE", "6"))
MAX_CORRECTIONS = int(os.environ.get("MAX_CORRECTIONS", "5"))
MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
BUCKET = os.environ.get("BUCKET_NAME", "")


def evaluate_document(doc_id, plugin_id, tree, pdf_bytes):
    """Evaluate a document against all applicable baselines.

    Args:
        doc_id: The document identifier.
        plugin_id: The plugin/document type identifier (e.g. 'loan_package').
        tree: PageIndex hierarchical tree structure for the document.
        pdf_bytes: Raw PDF content as bytes.

    Returns:
        A compliance report dict with overallScore, results, and status.
    """
    baselines = _find_baselines(plugin_id)
    if not baselines:
        return {
            "reportId": str(uuid.uuid4()),
            "documentId": doc_id,
            "overallScore": -1,
            "results": [],
            "status": "no_baselines",
        }

    all_results = []
    for baseline in baselines:
        reqs = baseline.get("requirements", [])
        batches = [reqs[i : i + BATCH_SIZE] for i in range(0, len(reqs), BATCH_SIZE)]
        for batch in batches:
            pages = _navigate_tree_for_batch(tree, batch)
            page_text = _extract_pages(pdf_bytes, pages)
            verdicts = _evaluate_batch(batch, page_text, doc_id, baseline["baselineId"])
            all_results.extend(verdicts)

    pass_count = sum(1 for r in all_results if r["verdict"] == "PASS")
    score = round(pass_count / len(all_results) * 100) if all_results else 0

    return {
        "reportId": str(uuid.uuid4()),
        "documentId": doc_id,
        "baselineId": baselines[0]["baselineId"],
        "baselineVersion": baselines[0].get("version", 1),
        "status": "completed",
        "overallScore": score,
        "results": all_results,
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
    }


def _find_baselines(plugin_id):
    """Find published baselines for a given plugin type.

    Queries the baselines DynamoDB table using the pluginId-index GSI
    to find all baselines with status='published' for the given plugin.
    """
    resp = baselines_table.query(
        IndexName="pluginId-index",
        KeyConditionExpression="pluginId = :pid AND #s = :pub",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":pid": plugin_id, ":pub": "published"},
    )
    return resp.get("Items", [])


def _navigate_tree_for_batch(tree, batch):
    """Use LLM to find relevant pages for a batch of requirements.

    Sends the document's PageIndex tree structure and the requirement
    hints to Claude Haiku, which returns the page numbers most likely
    to contain evidence for the requirements.
    """
    hints = "\n".join(
        f"- {r['text']} (hint: {r.get('evaluationHint', '')})" for r in batch
    )
    compact = json.dumps(
        [{"title": n["title"], "pages": n.get("page_range")}
         for n in tree.get("structure", [])],
        indent=1,
    )
    prompt = (
        f"Given these requirements:\n{hints}\n\n"
        f"And this document structure:\n{compact}\n\n"
        "Return a JSON array of page numbers (integers) to examine."
    )
    resp = bedrock_client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 512},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    return _parse_page_list(text)


def _parse_page_list(text):
    """Extract a list of integers from LLM response text.

    Tries JSON parsing first, then falls back to regex extraction
    of all integers from the text.
    """
    # Try JSON parse first
    cleaned = re.sub(r"^```(?:json)?\s*|```$", "", text.strip())
    try:
        pages = json.loads(cleaned)
        if isinstance(pages, list):
            return [int(p) for p in pages if isinstance(p, (int, float))]
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: extract all integers
    return [int(m) for m in re.findall(r"\b(\d+)\b", text)]


def _extract_pages(pdf_bytes, pages):
    """Extract text from specific pages of a PDF.

    Uses PyPDF to read targeted pages, returning formatted text
    with page markers for evidence grounding.
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        parts = []
        for p in sorted(set(pages)):
            if 1 <= p <= len(reader.pages):
                text = reader.pages[p - 1].extract_text() or ""
                parts.append(f"--- Page {p} ---\n{text}")
        return "\n\n".join(parts)
    except Exception:
        return f"[PDF extraction failed for pages {pages}]"


def _evaluate_batch(batch, page_text, doc_id, baseline_id):
    """Evaluate a batch of requirements against page content.

    Sends the requirements and extracted page text to Claude Haiku,
    which returns verdict, confidence, and evidence for each requirement.
    Includes any prior feedback corrections as few-shot examples.
    """
    corrections_block = _get_corrections_block(baseline_id, batch)
    reqs_text = "\n".join(
        f"{i + 1}. [{r['requirementId']}] {r['text']}\n"
        f"   Hint: {r.get('evaluationHint', '')}"
        for i, r in enumerate(batch)
    )
    prompt = (
        f"Evaluate these compliance requirements against the document.\n\n"
        f"{corrections_block}"
        f"REQUIREMENTS:\n{reqs_text}\n\nDOCUMENT CONTENT:\n{page_text}\n\n"
        "Respond with a JSON array: [{requirementId, verdict, confidence, "
        "evidence, evidenceCharStart, evidenceCharEnd, pageReferences}].\n"
        "IMPORTANT: 'evidence' must be an EXACT quote from the document "
        "(copy-paste, not paraphrased). 'evidenceCharStart' and "
        "'evidenceCharEnd' are the 0-based character offsets of the quote "
        "within the page text provided. Verdicts: PASS/FAIL/PARTIAL/NOT_FOUND."
    )
    resp = bedrock_client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 2048},
    )
    raw = resp["output"]["message"]["content"][0]["text"].strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"```$", "", raw.strip())
    return json.loads(raw)


def _get_corrections_block(baseline_id, batch):
    """Placeholder for few-shot corrections -- Task 8 will implement this.

    Will query the feedback table for prior human corrections and format
    them as few-shot examples to improve evaluation accuracy.
    """
    return ""


def _store_report(report):
    """Store compliance report in DynamoDB."""
    reports_table.put_item(Item=report)


def _load_tree_from_s3(event):
    """Load PageIndex tree from S3 if not inline."""
    key = event.get("pageIndexTreeS3Key", "")
    if not key:
        return {"structure": [], "total_pages": 0}
    resp = s3_client.get_object(Bucket=BUCKET, Key=key)
    return json.loads(resp["Body"].read())


def _download_pdf(event):
    """Download the PDF document from S3."""
    key = event.get("documentKey", event.get("key", ""))
    if not key:
        return b""
    resp = s3_client.get_object(Bucket=BUCKET, Key=key)
    return resp["Body"].read()
