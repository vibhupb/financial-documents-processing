"""PageIndex Lambda handler — builds hierarchical tree index for documents.

Invoked by Step Functions after the Router classifies a document as
unstructured (has_sections=True). Stores the tree in DynamoDB and S3.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import boto3
from tree_builder import build_tree

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME", "financial-documents"))
BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Build PageIndex tree and store results.

    Input (from Step Functions):
        documentId, bucket, key, pluginId, classification, metadata, ...

    Output (merged back into Step Functions state):
        pageIndexTree: { structure, doc_description, total_pages, ... }
        pageIndexCost: { inputTokens, outputTokens, cost }
    """
    document_id = event["documentId"]
    bucket = event.get("bucket", BUCKET_NAME)
    key = event["key"]
    plugin_id = event.get("pluginId", "unknown")
    file_name = key.split("/")[-1] if "/" in key else key

    print(f"[PageIndex] Starting tree build for {document_id} "
          f"(plugin={plugin_id}, key={key})")

    # Record processing event
    _update_status(document_id, "INDEXING", "Building document tree index")

    # Download PDF
    start_time = time.time()
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_bytes = response["Body"].read()
    except Exception as e:
        print(f"[PageIndex] Failed to download PDF: {e}")
        _update_status(document_id, "INDEXING", f"PageIndex failed: {e}")
        return {**event, "hasPageIndexTree": False, "pageIndexCost": _zero_cost()}

    # Get plugin-specific PageIndex config
    pi_config = _get_page_index_config(event)

    # Build the tree
    try:
        tree = build_tree(
            pdf_bytes=pdf_bytes,
            doc_name=file_name,
            model=pi_config.get("model", BEDROCK_MODEL_ID),
            toc_check_page_num=pi_config.get("toc_check_page_num", 20),
            max_page_num_each_node=pi_config.get("max_page_num_each_node", 10),
            max_token_num_each_node=pi_config.get("max_token_num_each_node", 20000),
            generate_summaries_flag=pi_config.get("generate_summaries", False),
            generate_description_flag=pi_config.get("generate_description", True),
        )
    except Exception as e:
        print(f"[PageIndex] Tree build failed: {e}")
        _update_status(document_id, "INDEXING", f"PageIndex failed: {e}")
        return {**event, "hasPageIndexTree": False, "pageIndexCost": _zero_cost()}

    elapsed = time.time() - start_time

    # Store tree in S3 first (no size limit)
    _store_audit(bucket, document_id, tree)

    # Store tree in DynamoDB (may fail for large trees > 400KB)
    _store_tree(document_id, tree, bucket)

    # Record completion
    node_count = _count_nodes(tree.get("structure", []))
    _update_status(
        document_id, "INDEXING",
        f"Tree built: {node_count} nodes, {tree.get('total_pages', 0)} pages, "
        f"{elapsed:.1f}s"
    )

    # Estimate cost (rough: based on typical token usage patterns)
    cost = _estimate_cost(tree)

    print(f"[PageIndex] Complete: {node_count} nodes, "
          f"~${cost.get('cost', 0):.3f}, {elapsed:.1f}s")

    # Return lightweight reference — full tree is in DynamoDB + S3.
    # Avoids Step Functions 256KB payload limit for large documents.
    return {
        **event,
        "hasPageIndexTree": True,
        "pageIndexCost": cost,
        "pageIndexStats": {
            "nodeCount": node_count,
            "totalPages": tree.get("total_pages", 0),
            "buildSeconds": round(elapsed, 1),
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_page_index_config(event: dict) -> dict:
    """Extract PageIndex config from plugin metadata or use defaults."""
    # Check if plugin config was passed through
    metadata = event.get("metadata", {})
    plugin_config = metadata.get("pluginConfig", {})
    pi_config = plugin_config.get("page_index", {})

    # Also check classification-level hints
    classification = event.get("classification", {})
    if not pi_config and classification.get("has_sections"):
        pi_config = {"enabled": True}

    return pi_config


def _store_tree(document_id: str, tree: dict, bucket: str) -> None:
    """Store PageIndex tree in DynamoDB document record.

    If the tree exceeds DynamoDB's 400KB item limit, stores a reference
    to S3 (pageIndexTreeS3Key) instead of the full tree inline.
    """
    sanitized = _sanitize_for_dynamo(tree)

    # Estimate serialized size (rough — DynamoDB attribute overhead ~100 bytes)
    tree_json = json.dumps(sanitized, default=str)
    tree_size = len(tree_json.encode("utf-8"))
    print(f"[PageIndex] Tree JSON size: {tree_size:,} bytes")

    # DynamoDB has 400KB item limit; leave room for other attributes
    if tree_size > 350_000:
        print(f"[PageIndex] Tree too large for DynamoDB ({tree_size:,} bytes), "
              f"storing S3 reference")
        update_expr = (
            "SET pageIndexTreeS3Key = :s3key, "
            "updatedAt = :now"
        )
        attr_values = {
            ":s3key": f"audit/{document_id}/pageindex-tree.json",
            ":now": datetime.now(timezone.utc).isoformat(),
        }
    else:
        update_expr = (
            "SET pageIndexTree = :tree, "
            "updatedAt = :now"
        )
        attr_values = {
            ":tree": sanitized,
            ":now": datetime.now(timezone.utc).isoformat(),
        }

    # Find the document record (documentType may be PROCESSING or already classified)
    try:
        resp = table.query(
            KeyConditionExpression="documentId = :did",
            ExpressionAttributeValues={":did": document_id},
            Limit=1,
        )
        if resp.get("Items"):
            doc_type = resp["Items"][0]["documentType"]
        else:
            doc_type = "PROCESSING"
    except Exception:
        doc_type = "PROCESSING"

    try:
        table.update_item(
            Key={"documentId": document_id, "documentType": doc_type},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=attr_values,
        )
        print(f"[PageIndex] Stored tree in DynamoDB (key={doc_type})")
    except Exception as e:
        print(f"[PageIndex] DynamoDB update failed: {e}")


def _store_audit(bucket: str, document_id: str, tree: dict) -> None:
    """Store tree JSON in S3 audit trail."""
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=f"audit/{document_id}/pageindex-tree.json",
            Body=json.dumps(tree, indent=2, default=str),
            ContentType="application/json",
        )
    except Exception as e:
        print(f"[PageIndex] S3 audit write failed: {e}")


def _update_status(document_id: str, stage: str, message: str) -> None:
    """Append a processing event to the document record."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "stage": stage.lower(),
        "message": message,
    }
    try:
        table.update_item(
            Key={"documentId": document_id, "documentType": "PROCESSING"},
            UpdateExpression=(
                "SET processingEvents = list_append("
                "if_not_exists(processingEvents, :empty), :evt)"
            ),
            ExpressionAttributeValues={
                ":evt": [event],
                ":empty": [],
            },
        )
    except Exception:
        pass  # Non-critical — don't fail the pipeline for status updates


def _estimate_cost(tree: dict) -> dict:
    """Rough cost estimate based on tree size and page count."""
    total_pages = tree.get("total_pages", 0)
    node_count = _count_nodes(tree.get("structure", []))

    # Rough estimates for Claude Haiku 4.5:
    # TOC detection: ~15K tokens (batched, first 20 pages in one call)
    # Structure generation: ~2000 tokens/page
    # Verification: ~500 tokens × sample_size
    # Summaries: deferred (not generated during build)
    input_tokens = (
        min(total_pages, 20) * 500    # TOC detection (single batched call)
        + total_pages * 500            # structure/TOC processing
        + 15 * 500                     # verification
    )
    output_tokens = (
        200                            # TOC detection (single response)
        + total_pages * 100            # structure entries
        + 15 * 50                      # verification responses
    )

    # Claude Haiku 4.5: $1.00/MTok input, $5.00/MTok output
    cost = (input_tokens * 1.00 + output_tokens * 5.00) / 1_000_000

    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "cost": round(cost, 4),
    }


def _count_nodes(nodes: list) -> int:
    """Count total nodes in tree."""
    count = 0
    for node in nodes:
        count += 1
        if node.get("nodes"):
            count += _count_nodes(node["nodes"])
    return count


def _sanitize_for_dynamo(obj: Any) -> Any:
    """Convert floats to Decimal and clean data for DynamoDB."""
    from decimal import Decimal

    if isinstance(obj, float):
        return Decimal(str(round(obj, 6)))
    if isinstance(obj, dict):
        return {k: _sanitize_for_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_dynamo(v) for v in obj]
    return obj


def _zero_cost() -> dict:
    return {"inputTokens": 0, "outputTokens": 0, "cost": 0}
