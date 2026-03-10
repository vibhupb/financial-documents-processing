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
from decimal import Decimal

s3_client = boto3.client("s3")
bedrock_client = boto3.client(
    "bedrock-runtime", config=Config(
        max_pool_connections=50,
        read_timeout=120,
        retries={"max_attempts": 3, "mode": "adaptive"},
    )
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
BATCH_SIZE = int(os.environ.get("REQUIREMENT_BATCH_SIZE", "10"))
MAX_CORRECTIONS = int(os.environ.get("MAX_CORRECTIONS", "5"))
MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6"
)
# Haiku for fast tasks (tree navigation, page finding) — Sonnet only for evaluation
FAST_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
BUCKET = os.environ.get("BUCKET_NAME", "")


def _append_event(doc_id, message):
    """Append a compliance processing event to the document record."""
    doc_table_name = os.environ.get("TABLE_NAME", "financial-documents")
    doc_table = dynamodb.Table(doc_table_name)
    try:
        resp = doc_table.query(
            KeyConditionExpression="documentId = :did",
            ExpressionAttributeValues={":did": doc_id},
            ProjectionExpression="documentId, documentType",
            Limit=1,
        )
        items = resp.get("Items", [])
        if items:
            doc_table.update_item(
                Key={"documentId": items[0]["documentId"], "documentType": items[0]["documentType"]},
                UpdateExpression="SET processingEvents = list_append(if_not_exists(processingEvents, :empty), :evt)",
                ExpressionAttributeValues={
                    ":evt": [{"ts": datetime.now(timezone.utc).isoformat(), "stage": "compliance", "message": message}],
                    ":empty": [],
                },
            )
    except Exception as e:
        print(f"[Compliance] Warning: Could not append event: {e}")


def evaluate_document(doc_id, plugin_id, tree, pdf_bytes, baseline_ids=None):
    """Evaluate a document against all applicable baselines.

    Args:
        doc_id: The document identifier.
        plugin_id: The plugin/document type identifier (e.g. 'loan_package').
        tree: PageIndex hierarchical tree structure for the document.
        pdf_bytes: Raw PDF content as bytes.
        baseline_ids: Optional explicit list of baseline IDs from upload.

    Returns:
        A compliance report dict with overallScore, results, and status.
    """
    baselines = _find_baselines(plugin_id, baseline_ids=baseline_ids)
    if not baselines:
        _append_event(doc_id, "No compliance baselines found — skipping evaluation")
        return {
            "reportId": str(uuid.uuid4()),
            "documentId": doc_id,
            "overallScore": -1,
            "results": [],
            "status": "no_baselines",
        }

    total_reqs = sum(len(b.get("requirements", [])) for b in baselines)
    _append_event(doc_id, f"Evaluating against {len(baselines)} baseline(s), {total_reqs} requirements")

    reports = []
    for baseline in baselines:
        bl_name = baseline.get("name", baseline.get("baselineId", "unknown"))
        baseline_results = []
        reqs = baseline.get("requirements", [])
        batches = [reqs[i : i + BATCH_SIZE] for i in range(0, len(reqs), BATCH_SIZE)]

        # Parallel batch evaluation — process all batches concurrently
        # to avoid sequential Sonnet 4.6 calls timing out the Lambda
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _process_batch(batch):
            pages = _navigate_tree_for_batch(tree, batch)
            page_text = _extract_pages(pdf_bytes, pages)
            return _evaluate_batch(batch, page_text, doc_id, baseline["baselineId"])

        with ThreadPoolExecutor(max_workers=min(len(batches), 3)) as executor:
            futures = {executor.submit(_process_batch, b): i for i, b in enumerate(batches)}
            results_by_idx = {}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results_by_idx[idx] = future.result()
                except Exception as e:
                    print(f"[Compliance] Batch {idx} failed: {e}")
                    results_by_idx[idx] = []

        # Merge results in original order
        for idx in sorted(results_by_idx.keys()):
            baseline_results.extend(results_by_idx[idx])
        _append_event(doc_id, f"Evaluated {len(baseline_results)}/{len(reqs)} requirements ({bl_name})")

        # Score excludes NOT_APPLICABLE requirements (they don't apply to this doc type)
        applicable = [r for r in baseline_results if r.get("verdict") != "NOT_APPLICABLE"]
        pass_count = sum(1 for r in applicable if r["verdict"] == "PASS")
        score = round(pass_count / len(applicable) * 100) if applicable else 0

        reports.append({
            "reportId": str(uuid.uuid4()),
            "documentId": doc_id,
            "baselineId": baseline["baselineId"],
            "baselineVersion": baseline.get("version", 1),
            "status": "completed",
            "overallScore": score,
            "results": baseline_results,
            "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        })

        _append_event(doc_id, f"Compliance complete: {bl_name} — score {score}% ({pass_count}/{len(baseline_results)} passed)")

    # Return single report for backward compat, or list for multi-baseline
    if len(reports) == 1:
        return reports[0]
    return reports


def _find_baselines(plugin_id, baseline_ids=None):
    """Find baselines for evaluation.

    If baseline_ids are provided (from upload), fetch those specific baselines.
    Otherwise, query by pluginId GSI for all published baselines matching the plugin.
    """
    if baseline_ids:
        # Fetch explicit baselines by ID
        items = []
        for bid in baseline_ids:
            try:
                resp = baselines_table.get_item(Key={"baselineId": bid})
                item = resp.get("Item")
                if item and item.get("status") == "published":
                    items.append(item)
            except Exception as e:
                print(f"[Compliance] Failed to fetch baseline {bid}: {e}")
        return items

    # Fallback: query by plugin type
    resp = baselines_table.query(
        IndexName="pluginId-index",
        KeyConditionExpression="pluginId = :pid AND #s = :pub",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":pid": plugin_id, ":pub": "published"},
    )
    return resp.get("Items", [])


def _compact_tree(nodes, total_pages=0):
    """Build compact tree representation for LLM navigation."""
    result = []
    for n in nodes:
        start = int(n.get("start_index", 1))
        end = int(n.get("end_index", start))
        if total_pages > 0:
            start = min(start, total_pages)
            end = min(end, total_pages)
        entry = {
            "title": n.get("title", ""),
            "pages": f"{start}-{end}",
        }
        children = n.get("nodes", [])
        if children:
            entry["sections"] = _compact_tree(children, total_pages)
        result.append(entry)
    return result


def _navigate_tree_for_batch(tree, batch):
    """Use LLM to find relevant pages for a batch of requirements.

    Sends the document's PageIndex tree structure and the requirement
    hints to the LLM, which returns page numbers to examine.
    Clamps returned pages to actual document length.
    """
    total_pages = int(tree.get("total_pages", 0))
    hints = "\n".join(
        f"- {r['text']} (hint: {r.get('evaluationHint', '')})" for r in batch
    )
    compact = json.dumps(_compact_tree(tree.get("structure", []), total_pages), indent=1)
    prompt = (
        f"Given these requirements:\n{hints}\n\n"
        f"And this document structure (total {total_pages} pages):\n{compact}\n\n"
        "Return a JSON array of page numbers (integers) to examine. "
        "Include pages from ALL relevant sections, not just the first match."
    )
    resp = bedrock_client.converse(
        modelId=FAST_MODEL_ID,  # Haiku for navigation — fast, cheap
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 512},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    pages = _parse_page_list(text)
    # Clamp to actual document length
    if total_pages > 0:
        pages = [min(p, total_pages) for p in pages if p >= 1]
    return sorted(set(pages))


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

    Sends the requirements and extracted page text to the LLM,
    which returns verdict, confidence, and evidence for each requirement.
    Uses semantic evaluation — assesses intent and substance, not literal
    wording. Includes any prior feedback corrections as few-shot examples.
    """
    corrections_block = _get_corrections_block(baseline_id, batch)
    reqs_text = "\n".join(
        f"{i + 1}. [{r['requirementId']}] {r['text']}\n"
        f"   Hint: {r.get('evaluationHint', '')}"
        for i, r in enumerate(batch)
    )
    prompt = (
        "You are a compliance analyst evaluating whether a document meets "
        "regulatory and policy requirements. Evaluate INTENT and SUBSTANCE, "
        "not exact wording.\n\n"
        "EVALUATION PRINCIPLES:\n"
        "- A requirement is MET if the document addresses the same obligation, "
        "even using different terminology or phrasing.\n"
        "- Look for EQUIVALENT CONCEPTS: e.g., 'maintain insurance' may appear "
        "as 'keep policies in force', 'coverage shall remain effective', etc.\n"
        "- Consider the SPIRIT of each requirement, not just literal keywords.\n"
        "- Financial terms may be expressed differently across document types "
        "(e.g., 'interest rate' vs 'applicable margin', 'borrower' vs 'obligor').\n"
        "- Partial compliance counts: if a document addresses part of a "
        "requirement but not all aspects, use PARTIAL.\n\n"
        f"{corrections_block}"
        f"REQUIREMENTS:\n{reqs_text}\n\nDOCUMENT CONTENT:\n{page_text}\n\n"
        "Respond with a JSON array. For each requirement:\n"
        "- requirementId: the ID from above\n"
        "- verdict: PASS (requirement substantively met), FAIL (document "
        "contradicts or clearly does not meet), PARTIAL (some aspects met), "
        "NOT_FOUND (no relevant content found), or NOT_APPLICABLE (requirement "
        "does not apply to this document type)\n"
        "- confidence: 0.0-1.0 how confident you are in the verdict\n"
        "- evidence: the relevant passage from the document (may be summarized "
        "or quoted — include enough context to justify the verdict)\n"
        "- pageReferences: array of page numbers where evidence was found\n"
        "- reasoning: brief explanation of WHY this verdict was reached, "
        "especially for PARTIAL or FAIL verdicts\n\n"
        "Return ONLY the JSON array."
    )
    resp = bedrock_client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 8192},
    )
    raw = resp["output"]["message"]["content"][0]["text"].strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"```$", "", raw.strip())
    # LLM sometimes appends explanation text after the JSON array/object.
    # Extract only the first valid JSON structure.
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Find the first JSON array or object anywhere in the response
        # (LLM may prepend explanation text before the JSON)
        start_idx = -1
        bracket = "["
        close = "]"
        for marker in ("[", "{"):
            idx = raw.find(marker)
            if idx >= 0 and (start_idx < 0 or idx < start_idx):
                start_idx = idx
                bracket = marker
                close = "]" if marker == "[" else "}"
        if start_idx >= 0:
            depth, end = 0, 0
            for i in range(start_idx, len(raw)):
                ch = raw[i]
                if ch == bracket:
                    depth += 1
                elif ch == close:
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end > 0:
                return json.loads(raw[start_idx:end])
        raise


def _get_corrections_block(baseline_id, batch):
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
            f"{c['correctedVerdict']}: {c.get('reviewerNote', '')}"
        )
    return "\n".join(lines) + "\n\n"


def _convert_floats(obj):
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_floats(i) for i in obj]
    return obj


def _store_report(report):
    """Store compliance report and update document with compliance score."""
    reports_table.put_item(Item=_convert_floats(report))
    # Write complianceScore to main documents table for Work Queue display
    # The documents table has a composite key (documentId + documentType),
    # so we must query first to find the documentType.
    doc_table_name = os.environ.get("TABLE_NAME", "financial-documents")
    doc_table = dynamodb.Table(doc_table_name)
    try:
        resp = doc_table.query(
            KeyConditionExpression="documentId = :did",
            ExpressionAttributeValues={":did": report["documentId"]},
            ProjectionExpression="documentId, documentType",
            Limit=1,
        )
        items = resp.get("Items", [])
        if items:
            doc_table.update_item(
                Key={"documentId": items[0]["documentId"], "documentType": items[0]["documentType"]},
                UpdateExpression="SET complianceScore = :score",
                ExpressionAttributeValues={":score": report.get("overallScore", 0)},
            )
    except Exception as e:
        print(f"[Compliance] Warning: Could not update complianceScore on document: {e}")


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
