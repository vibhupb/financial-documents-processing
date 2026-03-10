"""Compliance Ingest Lambda — parse docs, extract requirements, store draft baseline."""
from __future__ import annotations

import io
import os
from datetime import datetime, timezone

import boto3

from parser import parse_docx, parse_pptx, parse_pdf, parse_xlsx, ParsedContent
from extractor import extract_requirements, deduplicate_requirements

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
bl_table = dynamodb.Table(os.environ.get("BASELINES_TABLE", "compliance-baselines"))
BUCKET = os.environ.get("BUCKET_NAME", "")

PARSERS = {
    "docx": parse_docx,
    "pptx": parse_pptx,
    "pdf": parse_pdf,
    "xlsx": parse_xlsx,
}


import time
import json


PAGEINDEX_FUNCTION = os.environ.get("PAGEINDEX_FUNCTION", "doc-processor-pageindex")
lambda_client = boto3.client("lambda")


def _wait_for_tree(baseline_id: str, doc_key: str, max_wait: int = 180) -> dict | None:
    """Poll baseline until PageIndex tree is available for a document.

    The frontend triggers tree building before calling ingest. This function
    waits for the tree to appear in the baseline's referenceTree map.
    """
    start = time.time()
    poll_interval = 5
    while time.time() - start < max_wait:
        baseline = bl_table.get_item(Key={"baselineId": baseline_id}).get("Item", {})
        trees = baseline.get("referenceTree", {})
        tree = trees.get(doc_key)
        if tree and isinstance(tree, dict) and tree.get("structure"):
            return tree
        gen_status = baseline.get("generatingStatus", "")
        if gen_status == "tree_ready":
            # Tree ready but might be under a different key — check all
            for k, v in trees.items():
                if isinstance(v, dict) and v.get("structure"):
                    return v
        elapsed = int(time.time() - start)
        print(f"[Ingest] Waiting for PageIndex tree ({elapsed}s / {max_wait}s)...")
        time.sleep(poll_interval)
    print(f"[Ingest] Tree wait timed out after {max_wait}s")
    return None


def _build_tree_inline(baseline_id: str, doc_key: str) -> dict | None:
    """Invoke PageIndex Lambda synchronously as a last resort."""
    try:
        resp = lambda_client.invoke(
            FunctionName=PAGEINDEX_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "bucket": BUCKET,
                "key": doc_key,
                "entityType": "baseline",
                "entityId": baseline_id,
                "entityDocKey": doc_key,
            }),
        )
        result = json.loads(resp["Payload"].read())
        if result.get("hasPageIndexTree"):
            # Re-fetch from DynamoDB
            baseline = bl_table.get_item(Key={"baselineId": baseline_id}).get("Item", {})
            return baseline.get("referenceTree", {}).get(doc_key)
    except Exception as e:
        print(f"[Ingest] Inline tree build failed: {e}")
    return None


def _extract_with_tree(pdf_bytes: bytes, tree: dict, source_key: str) -> list:
    """Extract requirements section-by-section using PageIndex tree.

    Instead of sending the entire document text (which gets truncated),
    iterates tree sections and runs targeted LLM extraction per section.
    This produces higher-quality requirements for large documents.
    """
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    all_reqs = []

    def _get_all_sections(nodes, depth=0):
        """Flatten tree into leaf/small sections for processing."""
        sections = []
        for node in nodes:
            children = node.get("nodes", [])
            start = int(node.get("start_index", 1))
            end = int(node.get("end_index", start))
            title = node.get("title", "Unknown")
            # If node has children, recurse to get more specific sections
            if children and depth < 2:
                sections.extend(_get_all_sections(children, depth + 1))
            else:
                sections.append({"title": title, "start": start, "end": end})
        return sections

    sections = _get_all_sections(tree.get("structure", []))
    print(f"[Ingest] Tree has {len(sections)} sections to process (parallel)")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _process_section(i, section):
        start = section["start"]
        end = section["end"]
        title = section["title"]

        pages_text = []
        for p in range(start, min(end + 1, len(reader.pages) + 1)):
            text = reader.pages[p - 1].extract_text() or ""
            if text.strip():
                pages_text.append(f"--- Page {p} ---\n{text}")

        section_text = "\n\n".join(pages_text)
        if not section_text.strip():
            return []

        print(f"[Ingest] Section {i+1}/{len(sections)}: '{title}' (pp. {start}-{end}, {len(section_text)} chars)")

        section_content = ParsedContent(text=f"SECTION: {title}\n\n{section_text}")
        section_reqs = extract_requirements(section_content, source_document=source_key)

        for req in section_reqs:
            req["sourceSection"] = title
            req["sourcePages"] = f"{start}-{end}"

        return section_reqs

    with ThreadPoolExecutor(max_workers=min(len(sections), 5)) as executor:
        futures = {executor.submit(_process_section, i, sec): i for i, sec in enumerate(sections)}
        results_by_idx = {}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results_by_idx[idx] = future.result()
            except Exception as e:
                print(f"[Ingest] Section {idx} failed: {e}")
                results_by_idx[idx] = []

    # Merge in original order
    for idx in sorted(results_by_idx.keys()):
        all_reqs.extend(results_by_idx[idx])

    return all_reqs


def lambda_handler(event, context):
    """Parse reference document(s), extract requirements, update baseline.

    Supports both single document (legacy) and multiple documents:
      - event.sourceDocumentKey: single key (string)
      - event.sourceDocumentKeys: array of keys (list[str])

    When a PageIndex tree is available for a document, uses tree-assisted
    extraction (per-section LLM calls) instead of raw text truncation.
    """
    bid = event["baselineId"]

    # Support both single and multiple document keys
    keys = event.get("sourceDocumentKeys", [])
    if not keys:
        single_key = event.get("sourceDocumentKey", "")
        if single_key:
            keys = [single_key]

    if not keys:
        raise ValueError("No document keys provided")

    # Process each document — parallel when multiple docs
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _process_document(key):
        fmt = key.rsplit(".", 1)[-1].lower()
        if fmt == "doc":
            fmt = "docx"
        if fmt == "xls":
            fmt = "xlsx"
        if fmt not in PARSERS:
            print(f"[Ingest] Skipping unsupported format: {fmt} ({key})")
            return key, []

        print(f"[Ingest] Processing: {key} (format: {fmt})")
        file_bytes = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()

        if fmt == "pdf":
            tree = _wait_for_tree(bid, key)
            if tree and tree.get("structure"):
                print(f"[Ingest] Using PageIndex tree ({len(tree['structure'])} root nodes) for {key}")
                reqs = _extract_with_tree(file_bytes, tree, key)
            else:
                print(f"[Ingest] No tree available, triggering inline PageIndex build for {key}")
                tree = _build_tree_inline(bid, key)
                if tree and tree.get("structure"):
                    reqs = _extract_with_tree(file_bytes, tree, key)
                else:
                    print(f"[Ingest] Tree build failed, falling back to raw text for {key}")
                    parsed = PARSERS[fmt](file_bytes)
                    reqs = extract_requirements(parsed, source_document=key)
        else:
            print(f"[Ingest] Parsing {fmt} document: {key}")
            parsed = PARSERS[fmt](file_bytes)
            reqs = extract_requirements(parsed, source_document=key)

        print(f"[Ingest] Extracted {len(reqs)} requirements from {key}")
        return key, reqs

    all_reqs = []
    source_docs = []
    with ThreadPoolExecutor(max_workers=min(len(keys), 3)) as executor:
        futures = {executor.submit(_process_document, key): key for key in keys}
        for future in as_completed(futures):
            try:
                key, reqs = future.result()
                all_reqs.extend(reqs)
                source_docs.append(key)
            except Exception as e:
                print(f"[Ingest] Document failed: {futures[future]}: {e}")

    # Deduplicate if multiple documents produced overlapping requirements
    if len(source_docs) > 1 and all_reqs:
        print(f"[Ingest] Deduplicating {len(all_reqs)} requirements from {len(source_docs)} documents...")
        all_reqs = deduplicate_requirements(all_reqs)
        print(f"[Ingest] After deduplication: {len(all_reqs)} requirements")

    cats = sorted(set(r["category"] for r in all_reqs))

    # Update baseline — APPEND to existing requirements (don't overwrite)
    now = datetime.now(timezone.utc).isoformat()
    existing = bl_table.get_item(Key={"baselineId": bid}).get("Item", {})
    existing_reqs = existing.get("requirements", [])
    merged_reqs = existing_reqs + all_reqs
    all_cats = sorted(set(cats + existing.get("categories", [])))

    bl_table.update_item(
        Key={"baselineId": bid},
        UpdateExpression=(
            "SET requirements = :r, categories = :c, "
            "sourceDocumentKeys = list_append(if_not_exists(sourceDocumentKeys, :empty), :keys), "
            "generatingStatus = :done, "
            "updatedAt = :n"
        ),
        ExpressionAttributeValues={
            ":r": merged_reqs,
            ":c": all_cats,
            ":keys": source_docs,
            ":empty": [],
            ":done": "complete",
            ":n": now,
        },
    )

    return {
        "baselineId": bid,
        "requirementCount": len(all_reqs),
        "totalRequirements": len(merged_reqs),
        "categories": all_cats,
        "documentsProcessed": len(source_docs),
    }
