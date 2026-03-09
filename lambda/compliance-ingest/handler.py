"""Compliance Ingest Lambda — parse docs, extract requirements, store draft baseline."""
from __future__ import annotations

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


def lambda_handler(event, context):
    """Parse reference document(s), extract requirements, update baseline.

    Supports both single document (legacy) and multiple documents:
      - event.sourceDocumentKey: single key (string)
      - event.sourceDocumentKeys: array of keys (list[str])
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
            "updatedAt = :n"
        ),
        ExpressionAttributeValues={
            ":r": merged_reqs,
            ":c": all_cats,
            ":keys": source_docs,
            ":empty": [],
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
