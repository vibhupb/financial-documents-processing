"""S3 Event Trigger Lambda with Deduplication.

This Lambda function is triggered by S3 events when a new document
is uploaded to the ingest/ prefix. It:
1. Downloads the document and calculates its SHA-256 hash
2. Checks DynamoDB for existing documents with the same hash
3. If duplicate found, returns cached results (skip processing)
4. If new document, starts the Step Functions state machine
"""

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from typing import Any, Optional
from urllib.parse import unquote_plus

import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal

# Initialize AWS clients
s3_client = boto3.client("s3")
sfn_client = boto3.client("stepfunctions")
dynamodb = boto3.resource("dynamodb")


def convert_decimals(obj):
    """Convert Decimal objects to int/float for JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    return obj

# Environment variables
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]
TABLE_NAME = os.environ.get("TABLE_NAME", "financial-documents")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "")

# Constants
CONTENT_HASH_INDEX = "ContentHashIndex"
MAX_FILE_SIZE_FOR_HASH = 100 * 1024 * 1024  # 100MB limit for in-memory hashing


def calculate_content_hash(bucket: str, key: str) -> tuple[str, int]:
    """Calculate SHA-256 hash of S3 object content.

    Downloads the object in streaming mode to minimize memory usage.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Tuple of (hash_hex_string, file_size_bytes)
    """
    hasher = hashlib.sha256()
    total_size = 0

    response = s3_client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]

    # Stream in 64KB chunks
    for chunk in iter(lambda: body.read(65536), b""):
        hasher.update(chunk)
        total_size += len(chunk)

    return hasher.hexdigest(), total_size


def check_for_duplicate(content_hash: str) -> Optional[dict[str, Any]]:
    """Check if a document with the same content hash already exists.

    Args:
        content_hash: SHA-256 hash of document content

    Returns:
        Existing document record if found, None otherwise
    """
    table = dynamodb.Table(TABLE_NAME)

    try:
        response = table.query(
            IndexName=CONTENT_HASH_INDEX,
            KeyConditionExpression=Key("contentHash").eq(content_hash),
            Limit=1,
        )

        items = response.get("Items", [])
        if items:
            print(f"Found existing document with hash {content_hash[:16]}...")
            return items[0]

    except Exception as e:
        print(f"Error checking for duplicate: {str(e)}")
        # Continue with processing even if duplicate check fails

    return None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle S3 event with deduplication check.

    Args:
        event: S3 event containing information about the uploaded file
        context: Lambda context object

    Returns:
        dict: Response with execution details or cached results
    """
    print(f"Received event: {json.dumps(event)}")

    responses = []

    for record in event.get("Records", []):
        # Extract S3 object information
        # URL-decode the key (spaces come as '+', special chars as %XX)
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        size = record["s3"]["object"].get("size", 0)

        # Skip if file is too large for processing
        if size > MAX_FILE_SIZE_FOR_HASH:
            print(f"File too large ({size} bytes), skipping: {key}")
            responses.append(
                {
                    "key": key,
                    "error": f"File exceeds maximum size ({MAX_FILE_SIZE_FOR_HASH} bytes)",
                    "status": "SKIPPED",
                }
            )
            continue

        try:
            # Step 1: Calculate content hash
            print(f"Calculating hash for s3://{bucket}/{key}")
            content_hash, actual_size = calculate_content_hash(bucket, key)
            print(f"Content hash: {content_hash[:16]}... (size: {actual_size} bytes)")

            # Step 2: Check for duplicate
            existing_doc = check_for_duplicate(content_hash)

            if existing_doc:
                # Duplicate found - return cached results
                print(
                    f"Duplicate detected! Original document: {existing_doc.get('documentId')}"
                )
                responses.append(
                    {
                        "key": key,
                        "status": "DUPLICATE",
                        "originalDocumentId": existing_doc.get("documentId"),
                        "contentHash": content_hash,
                        "message": "Document already processed. Using cached results.",
                        "cachedExtraction": convert_decimals(existing_doc.get("extractedData")),
                    }
                )
                continue

            # Step 3: No duplicate - start processing
            # Extract document ID from S3 key path: ingest/<document_id>/filename.pdf
            # This ensures the document ID matches what the upload API returned to the frontend
            key_parts = key.split("/")
            if len(key_parts) >= 2 and key_parts[0] == "ingest":
                document_id = key_parts[1]
                print(f"Extracted document ID from S3 key: {document_id}")
            else:
                # Fallback to new UUID if path doesn't match expected format
                document_id = str(uuid.uuid4())
                print(f"Generated new document ID (unexpected path format): {document_id}")

            # Prepare input for Step Functions
            sfn_input = {
                "documentId": document_id,
                "bucket": bucket,
                "key": key,
                "size": actual_size,
                "contentHash": content_hash,
                "uploadedAt": datetime.utcnow().isoformat() + "Z",
                "source": "s3-trigger",
            }

            # Start Step Functions execution
            # Sanitize name: Step Functions only allows [a-zA-Z0-9-_]
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", document_id)[:8]
            execution_name = f"doc-{safe_id}-{int(datetime.utcnow().timestamp())}"

            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=execution_name,
                input=json.dumps(sfn_input),
            )

            print(f"Started execution: {response['executionArn']}")

            # Step 4: Create initial DynamoDB record with PENDING status
            # This allows the frontend to track processing status immediately
            table = dynamodb.Table(TABLE_NAME)
            timestamp = datetime.utcnow().isoformat() + "Z"

            # Extract filename from key for display
            filename = key.split("/")[-1] if "/" in key else key

            initial_record = {
                "documentId": document_id,
                "documentType": "PROCESSING",  # Placeholder until classification determines actual type
                "status": "PENDING",
                "createdAt": timestamp,
                "updatedAt": timestamp,
                "contentHash": content_hash,
                "originalS3Key": key,
                "fileName": filename,
                "fileSize": actual_size,
                "executionArn": response["executionArn"],
                "ttl": int(datetime.utcnow().timestamp()) + (365 * 24 * 60 * 60),  # 1 year TTL
            }

            table.put_item(Item=initial_record)
            print(f"Created initial DynamoDB record with PENDING status: {document_id}")

            responses.append(
                {
                    "documentId": document_id,
                    "contentHash": content_hash,
                    "executionArn": response["executionArn"],
                    "status": "STARTED",
                }
            )

        except Exception as e:
            print(f"Error processing {key}: {str(e)}")
            responses.append({"key": key, "error": str(e), "status": "FAILED"})

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": f"Processed {len(responses)} documents", "results": responses}
        ),
    }
