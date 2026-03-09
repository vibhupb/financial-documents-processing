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
            start = node.get("start_index", 1)
            end = node.get("end_index", start)
            title = node.get("title", "Unknown")
            # If node has children, recurse to get more specific sections
            if children and depth < 2:
                sections.extend(_get_all_sections(children, depth + 1))
            else:
                sections.append({"title": title, "start": start, "end": end})
        return sections

    sections = _get_all_sections(tree.get("structure", []))
    print(f"[Ingest] Tree has {len(sections)} sections to process")

    for i, section in enumerate(sections):
        start = section["start"]
        end = section["end"]
        title = section["title"]

        # Extract text for this section
        pages_text = []
        for p in range(start, min(end + 1, len(reader.pages) + 1)):
            text = reader.pages[p - 1].extract_text() or ""
            if text.strip():
                pages_text.append(f"--- Page {p} ---\n{text}")

        section_text = "\n\n".join(pages_text)
        if not section_text.strip():
            continue

        print(f"[Ingest] Section {i+1}/{len(sections)}: '{title}' (pp. {start}-{end}, {len(section_text)} chars)")

        # Create a ParsedContent for this section
        section_content = ParsedContent(text=f"SECTION: {title}\n\n{section_text}")
        section_reqs = extract_requirements(section_content, source_document=source_key)

        # Tag requirements with their source section
        for req in section_reqs:
            req["sourceSection"] = title
            req["sourcePages"] = f"{start}-{end}"

        all_reqs.extend(section_reqs)

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

    # Check if trees are available for any documents
    baseline = bl_table.get_item(Key={"baselineId": bid}).get("Item", {})
    reference_trees = baseline.get("referenceTree", {})

    # Parse and extract requirements from each document
    all_reqs = []
    source_docs = []
    for key in keys:
        fmt = key.rsplit(".", 1)[-1].lower()
        if fmt == "doc":
            fmt = "docx"
        if fmt == "xls":
            fmt = "xlsx"
        if fmt not in PARSERS:
            print(f"[Ingest] Skipping unsupported format: {fmt} ({key})")
            continue

        print(f"[Ingest] Processing: {key} (format: {fmt})")
        file_bytes = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()

        # Check for PageIndex tree (only for PDFs)
        tree = reference_trees.get(key)
        if tree and fmt == "pdf" and tree.get("structure"):
            print(f"[Ingest] Using PageIndex tree ({len(tree['structure'])} root nodes) for {key}")
            reqs = _extract_with_tree(file_bytes, tree, key)
        else:
            print(f"[Ingest] Using raw text extraction for {key}")
            parsed = PARSERS[fmt](file_bytes)
            reqs = extract_requirements(parsed, source_document=key)

        print(f"[Ingest] Extracted {len(reqs)} requirements from {key}")
        all_reqs.extend(reqs)
        source_docs.append(key)

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
