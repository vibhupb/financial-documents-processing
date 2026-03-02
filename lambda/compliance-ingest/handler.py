"""Compliance Ingest Lambda — parse docs, extract requirements, store draft baseline."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import boto3

from parser import parse_docx, parse_pptx, parse_pdf
from extractor import extract_requirements

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
bl_table = dynamodb.Table(os.environ.get("BASELINES_TABLE", "compliance-baselines"))
BUCKET = os.environ.get("BUCKET_NAME", "")

PARSERS = {
    "docx": parse_docx,
    "pptx": parse_pptx,
    "pdf": parse_pdf,
}


def lambda_handler(event, context):
    """Parse reference document, extract requirements, update baseline."""
    bid = event["baselineId"]
    key = event["sourceDocumentKey"]
    fmt = event.get("sourceFormat", key.rsplit(".", 1)[-1].lower())

    if fmt not in PARSERS:
        raise ValueError(f"Unsupported format: {fmt}")

    # Download and parse reference document
    file_bytes = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    parsed = PARSERS[fmt](file_bytes)

    # Extract requirements via LLM
    reqs = extract_requirements(parsed)
    cats = sorted(set(r["category"] for r in reqs))

    # Update baseline with extracted requirements
    now = datetime.now(timezone.utc).isoformat()
    bl_table.update_item(
        Key={"baselineId": bid},
        UpdateExpression=(
            "SET requirements = :r, categories = :c, "
            "sourceDocumentKey = :k, sourceFormat = :f, updatedAt = :n"
        ),
        ExpressionAttributeValues={
            ":r": reqs,
            ":c": cats,
            ":k": key,
            ":f": fmt,
            ":n": now,
        },
    )

    return {
        "baselineId": bid,
        "requirementCount": len(reqs),
        "categories": cats,
    }
