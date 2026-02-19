"""API Lambda - REST API for Document Processing Dashboard.

This Lambda function provides REST API endpoints for:
- Listing processed documents
- Getting document details and status
- Uploading documents for processing
- Getting processing metrics
"""

import copy
import json
import os
import uuid
import boto3
from botocore.config import Config
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import unquote

# Get region for S3 regional endpoint (avoids 307 redirect CORS issues)
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")

# Authentication configuration
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "false").lower() == "true"


@dataclass
class UserContext:
    """Authenticated user context from Cognito JWT claims."""
    user_id: str = "anonymous"
    email: str = ""
    groups: list = field(default_factory=list)
    is_authenticated: bool = False

    def can_view_pii(self) -> bool:
        return "Admins" in self.groups

    def can_modify(self) -> bool:
        return bool({"Admins", "Reviewers"} & set(self.groups))

    def has_role(self, role: str) -> bool:
        return role in self.groups


def extract_user_context(event: dict) -> UserContext:
    """Extract user context from API Gateway Cognito authorizer claims."""
    try:
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        if not claims:
            return UserContext()
        groups_raw = claims.get("cognito:groups", "")
        groups = [g.strip() for g in groups_raw.split(",") if g.strip()] if groups_raw else []
        return UserContext(
            user_id=claims.get("sub", "unknown"),
            email=claims.get("email", ""),
            groups=groups,
            is_authenticated=True,
        )
    except Exception:
        return UserContext()


def mask_pii_fields(data: dict, user: UserContext, document_type: str) -> dict:
    """Mask PII fields based on user role and plugin config."""
    if not data or user.can_view_pii():
        return data
    try:
        from document_plugins.registry import get_plugin_for_document_type
        plugin = get_plugin_for_document_type(document_type)
        if not plugin:
            return data
        pii_paths = plugin.get("pii_paths", [])
        if not pii_paths:
            return data
    except (ImportError, Exception):
        return data

    import re
    masked = copy.deepcopy(data)
    for marker in pii_paths:
        json_path = marker.get("json_path", "")
        pii_type = marker.get("pii_type", "")
        # Simple path-based masking for common patterns
        parts = json_path.replace("[*]", ".[*]").split(".")
        _mask_at_path(masked, parts, pii_type)
    return masked


def _mask_at_path(data, parts, pii_type, depth=0):
    """Recursively mask values at a path with [*] wildcard support."""
    if depth >= len(parts) or data is None:
        return
    part = parts[depth]
    if part == "[*]" and isinstance(data, list):
        for item in data:
            _mask_at_path(item, parts, pii_type, depth + 1)
    elif isinstance(data, dict) and part in data:
        if depth == len(parts) - 1:
            # Leaf - mask the value
            val = data[part]
            if val and isinstance(val, str):
                if pii_type == "ssn":
                    digits = val.replace("-", "").replace(" ", "")
                    data[part] = f"***-**-{digits[-4:]}" if len(digits) >= 4 else "***-**-****"
                elif pii_type == "dob":
                    data[part] = "****-**-**"
                elif pii_type == "tax_id":
                    digits = val.replace("-", "").replace(" ", "")
                    data[part] = f"**-***{digits[-4:]}" if len(digits) >= 4 else "**-*******"
                else:
                    data[part] = "**REDACTED**"
        else:
            _mask_at_path(data[part], parts, pii_type, depth + 1)

# Configure S3 client with regional endpoint to avoid 307 redirects
# which break CORS in browsers
s3_config = Config(
    region_name=AWS_REGION,
    signature_version='s3v4',
)
s3_client = boto3.client("s3", config=s3_config, region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb")
sfn_client = boto3.client("stepfunctions")

# Configuration
BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
TABLE_NAME = os.environ.get("TABLE_NAME", "financial-documents")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def cors_headers() -> dict[str, str]:
    """Return CORS headers for API responses."""
    return {
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Api-Key",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        "Content-Type": "application/json",
    }


def response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """Create API Gateway response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": cors_headers(),
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def list_documents(query_params: dict[str, str]) -> dict[str, Any]:
    """List processed documents with optional filtering.

    Query Parameters:
    - status: Filter by processing status
    - limit: Max number of results (default: 20)
    - lastKey: Pagination token
    """
    table = dynamodb.Table(TABLE_NAME)

    limit = int(query_params.get("limit", "20"))
    status_filter = query_params.get("status")
    last_key = query_params.get("lastKey")

    scan_kwargs: dict[str, Any] = {
        "Limit": min(limit, 100),
    }

    if status_filter:
        # Use GSI for status-based queries
        scan_kwargs["IndexName"] = "StatusIndex"
        scan_kwargs["KeyConditionExpression"] = boto3.dynamodb.conditions.Key("status").eq(status_filter)
        result = table.query(**scan_kwargs)
    else:
        # Full table scan for all documents
        if last_key:
            scan_kwargs["ExclusiveStartKey"] = json.loads(unquote(last_key))
        result = table.scan(**scan_kwargs)

    documents = result.get("Items", [])
    last_evaluated_key = result.get("LastEvaluatedKey")

    return {
        "documents": documents,
        "count": len(documents),
        "lastKey": json.dumps(last_evaluated_key) if last_evaluated_key else None,
    }


def get_document(document_id: str) -> dict[str, Any]:
    """Get details of a specific document."""
    table = dynamodb.Table(TABLE_NAME)

    # Query by documentId (partition key)
    result = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
        Limit=1,
    )

    items = result.get("Items", [])

    if not items:
        return {"error": "Document not found", "documentId": document_id}

    return {"document": items[0]}


def get_document_audit(document_id: str) -> dict[str, Any]:
    """Get audit trail for a document from S3."""
    prefix = f"audit/{document_id}/"

    try:
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix,
            MaxKeys=10,
        )

        audit_files = []
        for obj in response.get("Contents", []):
            audit_files.append({
                "key": obj["Key"],
                "lastModified": obj["LastModified"].isoformat(),
                "size": obj["Size"],
            })

        return {
            "documentId": document_id,
            "auditFiles": sorted(audit_files, key=lambda x: x["lastModified"], reverse=True),
        }
    except Exception as e:
        return {"error": f"Failed to get audit trail: {str(e)}"}


def create_upload_url(filename: str) -> dict[str, Any]:
    """Generate a presigned POST URL for document upload.

    Uses presigned POST instead of PUT for better CORS support with
    private S3 buckets. Uses regional S3 endpoint to avoid 307 redirects
    which break CORS in browsers.
    """
    document_id = str(uuid.uuid4())
    key = f"ingest/{document_id}/{filename}"

    try:
        # Use presigned POST which has better CORS support
        presigned_post = s3_client.generate_presigned_post(
            Bucket=BUCKET_NAME,
            Key=key,
            Fields={
                "Content-Type": "application/pdf",
            },
            Conditions=[
                {"Content-Type": "application/pdf"},
                ["content-length-range", 1, 52428800],  # 1 byte to 50MB
            ],
            ExpiresIn=3600,  # 1 hour
        )

        # Replace global S3 endpoint with regional endpoint to avoid 307 redirects
        # which break CORS in browsers. The presigned POST generates URLs like:
        # https://bucket.s3.amazonaws.com/ -> change to:
        # https://bucket.s3.us-west-2.amazonaws.com/
        upload_url = presigned_post["url"]
        if ".s3.amazonaws.com" in upload_url:
            upload_url = upload_url.replace(
                ".s3.amazonaws.com",
                f".s3.{AWS_REGION}.amazonaws.com"
            )

        return {
            "documentId": document_id,
            "uploadUrl": upload_url,
            "fields": presigned_post["fields"],
            "key": key,
            "expiresIn": 3600,
        }
    except Exception as e:
        return {"error": f"Failed to generate upload URL: {str(e)}"}


def get_document_pdf_url(document_id: str) -> dict[str, Any]:
    """Generate a presigned URL for viewing the document PDF."""
    table = dynamodb.Table(TABLE_NAME)

    # First, get the document to find the original file location
    result = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
        Limit=1,
    )

    items = result.get("Items", [])
    if not items:
        return {"error": "Document not found", "documentId": document_id}

    doc = items[0]
    pdf_key = None

    # Try to find the PDF
    try:
        # First, check if we have the original S3 key stored in DynamoDB
        original_key = doc.get("originalS3Key")
        if original_key:
            # Verify the file exists at the stored path
            try:
                s3_client.head_object(Bucket=BUCKET_NAME, Key=original_key)
                pdf_key = original_key
            except s3_client.exceptions.ClientError:
                # File doesn't exist at stored path, fall through to search
                pass

        # If not found via originalS3Key, search in ingest folder
        if not pdf_key:
            prefix = f"ingest/{document_id}/"
            list_response = s3_client.list_objects_v2(
                Bucket=BUCKET_NAME,
                Prefix=prefix,
                MaxKeys=1,
            )

            contents = list_response.get("Contents", [])
            if not contents:
                # Try processed folder as fallback
                prefix = f"processed/{document_id}/"
                list_response = s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    Prefix=prefix,
                    MaxKeys=1,
                )
                contents = list_response.get("Contents", [])

            if contents:
                pdf_key = contents[0]["Key"]

        if not pdf_key:
            return {"error": "PDF file not found", "documentId": document_id}

        # Generate presigned URL for viewing
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": pdf_key,
                "ResponseContentType": "application/pdf",
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=3600,  # 1 hour
        )

        return {
            "documentId": document_id,
            "pdfUrl": presigned_url,
            "expiresIn": 3600,
        }
    except Exception as e:
        return {"error": f"Failed to generate PDF URL: {str(e)}"}


def get_processing_status(document_id: str) -> dict[str, Any]:
    """Get the processing status from Step Functions."""
    if not STATE_MACHINE_ARN:
        return {"error": "State machine ARN not configured"}

    try:
        # List executions for this document
        response = sfn_client.list_executions(
            stateMachineArn=STATE_MACHINE_ARN,
            maxResults=10,
        )

        # Find execution for this document
        for execution in response.get("executions", []):
            if document_id[:8] in execution["name"]:
                # Get execution details
                exec_details = sfn_client.describe_execution(
                    executionArn=execution["executionArn"]
                )

                return {
                    "documentId": document_id,
                    "status": exec_details["status"],
                    "startDate": exec_details["startDate"].isoformat(),
                    "stopDate": exec_details.get("stopDate", "").isoformat() if exec_details.get("stopDate") else None,
                    "executionArn": execution["executionArn"],
                }

        return {"documentId": document_id, "status": "NOT_FOUND"}
    except Exception as e:
        return {"error": f"Failed to get processing status: {str(e)}"}


def get_metrics() -> dict[str, Any]:
    """Get processing metrics and statistics."""
    table = dynamodb.Table(TABLE_NAME)

    try:
        # Count documents by status
        status_counts: dict[str, int] = {}

        for status in ["PROCESSED", "PENDING", "FAILED"]:
            result = table.query(
                IndexName="StatusIndex",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("status").eq(status),
                Select="COUNT",
            )
            status_counts[status] = result.get("Count", 0)

        # Count documents by review status
        review_counts: dict[str, int] = {}
        for review_status in ["PENDING_REVIEW", "APPROVED", "REJECTED"]:
            result = table.query(
                IndexName="ReviewStatusIndex",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("reviewStatus").eq(review_status),
                Select="COUNT",
            )
            review_counts[review_status] = result.get("Count", 0)

        # Get recent documents
        recent = table.scan(
            Limit=5,
            ProjectionExpression="documentId, documentType, createdAt, #s, reviewStatus",
            ExpressionAttributeNames={"#s": "status"},
        )

        return {
            "statusCounts": status_counts,
            "reviewStatusCounts": review_counts,
            "totalDocuments": sum(status_counts.values()),
            "pendingReview": review_counts.get("PENDING_REVIEW", 0),
            "recentDocuments": recent.get("Items", []),
        }
    except Exception as e:
        return {"error": f"Failed to get metrics: {str(e)}"}


# ==========================================
# Review Workflow Endpoints
# ==========================================


def list_review_queue(query_params: dict[str, str]) -> dict[str, Any]:
    """List documents pending review.

    Query Parameters:
    - status: Review status filter (PENDING_REVIEW, APPROVED, REJECTED)
    - limit: Max number of results (default: 20)
    """
    table = dynamodb.Table(TABLE_NAME)

    limit = int(query_params.get("limit", "20"))
    review_status = query_params.get("status", "PENDING_REVIEW")

    try:
        result = table.query(
            IndexName="ReviewStatusIndex",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("reviewStatus").eq(review_status),
            Limit=min(limit, 100),
            ScanIndexForward=False,  # Most recent first
        )

        documents = result.get("Items", [])

        return {
            "reviewStatus": review_status,
            "documents": documents,
            "count": len(documents),
        }
    except Exception as e:
        return {"error": f"Failed to get review queue: {str(e)}"}


def get_document_for_review(document_id: str) -> dict[str, Any]:
    """Get a document with all details needed for review."""
    table = dynamodb.Table(TABLE_NAME)

    result = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
        Limit=1,
    )

    items = result.get("Items", [])
    if not items:
        return {"error": "Document not found", "documentId": document_id}

    doc = items[0]

    # Generate PDF URL for viewing
    pdf_result = get_document_pdf_url(document_id)

    return {
        "document": doc,
        "pdfUrl": pdf_result.get("pdfUrl"),
        "reviewStatus": doc.get("reviewStatus"),
        "extractedData": doc.get("extractedData", {}),
        "validation": doc.get("validation", {}),
        "corrections": doc.get("corrections"),
    }


def approve_document(document_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Approve a document after review.

    Body:
    - reviewedBy: Name or ID of the reviewer
    - notes: Optional approval notes
    """
    table = dynamodb.Table(TABLE_NAME)
    timestamp = datetime.utcnow().isoformat() + "Z"

    reviewed_by = body.get("reviewedBy", "unknown")
    notes = body.get("notes", "")

    try:
        # First get the document to get its sort key
        result = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
            Limit=1,
        )
        items = result.get("Items", [])
        if not items:
            return {"error": "Document not found", "documentId": document_id}

        doc = items[0]
        document_type = doc.get("documentType", "LOAN_PACKAGE")
        current_version = doc.get("version", 1)

        # Update the document with approval
        table.update_item(
            Key={"documentId": document_id, "documentType": document_type},
            UpdateExpression="SET reviewStatus = :status, reviewedBy = :reviewer, reviewedAt = :timestamp, reviewNotes = :notes, updatedAt = :timestamp, version = :new_version",
            ConditionExpression="version = :current_version",  # Optimistic locking
            ExpressionAttributeValues={
                ":status": "APPROVED",
                ":reviewer": reviewed_by,
                ":timestamp": timestamp,
                ":notes": notes,
                ":current_version": current_version,
                ":new_version": current_version + 1,
            },
        )

        return {
            "documentId": document_id,
            "reviewStatus": "APPROVED",
            "reviewedBy": reviewed_by,
            "reviewedAt": timestamp,
            "message": "Document approved successfully",
        }
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return {"error": "Document was modified by another user. Please refresh and try again."}
    except Exception as e:
        return {"error": f"Failed to approve document: {str(e)}"}


def reject_document(document_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Reject a document and optionally trigger reprocessing.

    Body:
    - reviewedBy: Name or ID of the reviewer
    - notes: Required rejection reason
    - reprocess: Whether to trigger re-processing (default: false)
    """
    table = dynamodb.Table(TABLE_NAME)
    timestamp = datetime.utcnow().isoformat() + "Z"

    reviewed_by = body.get("reviewedBy", "unknown")
    notes = body.get("notes", "")
    should_reprocess = body.get("reprocess", False)

    if not notes:
        return {"error": "Rejection notes are required"}

    try:
        # Get the document
        result = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
            Limit=1,
        )
        items = result.get("Items", [])
        if not items:
            return {"error": "Document not found", "documentId": document_id}

        doc = items[0]
        document_type = doc.get("documentType", "LOAN_PACKAGE")
        current_version = doc.get("version", 1)

        # Update the document with rejection
        table.update_item(
            Key={"documentId": document_id, "documentType": document_type},
            UpdateExpression="SET reviewStatus = :status, reviewedBy = :reviewer, reviewedAt = :timestamp, reviewNotes = :notes, updatedAt = :timestamp, version = :new_version",
            ConditionExpression="version = :current_version",
            ExpressionAttributeValues={
                ":status": "REJECTED",
                ":reviewer": reviewed_by,
                ":timestamp": timestamp,
                ":notes": notes,
                ":current_version": current_version,
                ":new_version": current_version + 1,
            },
        )

        result_data = {
            "documentId": document_id,
            "reviewStatus": "REJECTED",
            "reviewedBy": reviewed_by,
            "reviewedAt": timestamp,
            "notes": notes,
            "message": "Document rejected",
        }

        # Trigger reprocessing if requested
        if should_reprocess and STATE_MACHINE_ARN:
            reprocess_result = reprocess_document(document_id, {"force": True})
            result_data["reprocessing"] = reprocess_result

        return result_data
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return {"error": "Document was modified by another user. Please refresh and try again."}
    except Exception as e:
        return {"error": f"Failed to reject document: {str(e)}"}


def correct_document_fields(document_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Update specific fields in a document's extracted data.

    Body:
    - corrections: Dict of field paths and corrected values
    - revalidate: Whether to re-run validation after correction (default: false)
    - correctedBy: Name or ID of the person making corrections
    """
    table = dynamodb.Table(TABLE_NAME)
    timestamp = datetime.utcnow().isoformat() + "Z"

    corrections = body.get("corrections", {})
    corrected_by = body.get("correctedBy", "unknown")
    revalidate = body.get("revalidate", False)

    if not corrections:
        return {"error": "No corrections provided"}

    try:
        # Get the document
        result = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
            Limit=1,
        )
        items = result.get("Items", [])
        if not items:
            return {"error": "Document not found", "documentId": document_id}

        doc = items[0]
        document_type = doc.get("documentType", "LOAN_PACKAGE")
        current_version = doc.get("version", 1)
        existing_corrections = doc.get("corrections") or {}

        # Merge corrections
        merged_corrections = {**existing_corrections, **corrections}
        merged_corrections["_lastCorrectedBy"] = corrected_by
        merged_corrections["_lastCorrectedAt"] = timestamp

        # Update the document
        update_expression = "SET corrections = :corrections, updatedAt = :timestamp, version = :new_version"
        expression_values = {
            ":corrections": merged_corrections,
            ":timestamp": timestamp,
            ":current_version": current_version,
            ":new_version": current_version + 1,
        }

        # Reset to pending review if corrected
        update_expression += ", reviewStatus = :review_status"
        expression_values[":review_status"] = "PENDING_REVIEW"

        table.update_item(
            Key={"documentId": document_id, "documentType": document_type},
            UpdateExpression=update_expression,
            ConditionExpression="version = :current_version",
            ExpressionAttributeValues=expression_values,
        )

        return {
            "documentId": document_id,
            "corrections": merged_corrections,
            "reviewStatus": "PENDING_REVIEW",
            "message": "Corrections saved successfully",
        }
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return {"error": "Document was modified by another user. Please refresh and try again."}
    except Exception as e:
        return {"error": f"Failed to save corrections: {str(e)}"}


def reprocess_document(document_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Trigger re-processing of a document through the Step Functions workflow.

    Body:
    - force: Force reprocessing even if already processed (default: false)
    """
    if not STATE_MACHINE_ARN:
        return {"error": "State machine ARN not configured"}

    table = dynamodb.Table(TABLE_NAME)
    force = body.get("force", False)

    try:
        # Get the document to find the original PDF location
        result = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
            Limit=1,
        )
        items = result.get("Items", [])
        if not items:
            return {"error": "Document not found", "documentId": document_id}

        doc = items[0]
        original_s3_key = doc.get("originalS3Key")

        if not original_s3_key:
            # Try to find in ingest folder
            prefix = f"ingest/{document_id}/"
            list_response = s3_client.list_objects_v2(
                Bucket=BUCKET_NAME,
                Prefix=prefix,
                MaxKeys=1,
            )
            contents = list_response.get("Contents", [])
            if contents:
                original_s3_key = contents[0]["Key"]

        if not original_s3_key:
            return {"error": "Original document not found", "documentId": document_id}

        # Start new Step Functions execution
        execution_name = f"{document_id[:8]}-reprocess-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        sfn_response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps({
                "documentId": document_id,
                "bucket": BUCKET_NAME,
                "key": original_s3_key,
                "reprocess": True,
                "contentHash": doc.get("contentHash"),
            }),
        )

        # Update document status
        document_type = doc.get("documentType", "LOAN_PACKAGE")
        table.update_item(
            Key={"documentId": document_id, "documentType": document_type},
            UpdateExpression="SET #s = :status, reviewStatus = :review_status, updatedAt = :timestamp",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "REPROCESSING",
                ":review_status": "PENDING_REVIEW",
                ":timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )

        return {
            "documentId": document_id,
            "executionArn": sfn_response["executionArn"],
            "status": "REPROCESSING",
            "message": "Document reprocessing started",
        }
    except Exception as e:
        return {"error": f"Failed to reprocess document: {str(e)}"}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Main Lambda handler for API Gateway requests."""
    print(f"API Lambda received event: {json.dumps(event)}")

    # Handle OPTIONS (CORS preflight)
    http_method = event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", ""))
    if http_method == "OPTIONS":
        return response(200, {"message": "CORS preflight"})

    # Extract authenticated user context from Cognito JWT claims
    user = extract_user_context(event)
    if REQUIRE_AUTH and not user.is_authenticated:
        return response(401, {"error": "Authentication required"})
    # Backward compat: when REQUIRE_AUTH=false, anonymous gets all roles
    if not REQUIRE_AUTH and not user.is_authenticated:
        user = UserContext(user_id="anonymous", email="anonymous@system",
                          groups=["Admins", "Reviewers", "Viewers"], is_authenticated=False)

    # Extract path and method
    path = event.get("path", event.get("rawPath", ""))
    path_params = event.get("pathParameters", {}) or {}
    query_params = event.get("queryStringParameters", {}) or {}
    body = event.get("body")

    if body and isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = {}

    print(f"Processing {http_method} {path}")

    try:
        # Route requests
        if path == "/documents" and http_method == "GET":
            return response(200, list_documents(query_params))

        elif path.startswith("/documents/") and "/audit" in path and http_method == "GET":
            document_id = path_params.get("documentId") or path.split("/")[2]
            return response(200, get_document_audit(document_id))

        elif path.startswith("/documents/") and "/status" in path and http_method == "GET":
            document_id = path_params.get("documentId") or path.split("/")[2]
            return response(200, get_processing_status(document_id))

        elif path.startswith("/documents/") and "/pdf" in path and http_method == "GET":
            document_id = path_params.get("documentId") or path.split("/")[2]
            return response(200, get_document_pdf_url(document_id))

        elif path.startswith("/documents/") and "/fields" in path and http_method == "PUT":
            # PUT /documents/{documentId}/fields - Correct field values
            document_id = path_params.get("documentId") or path.split("/")[2]
            return response(200, correct_document_fields(document_id, body or {}))

        elif path.startswith("/documents/") and "/reprocess" in path and http_method == "POST":
            # POST /documents/{documentId}/reprocess - Trigger re-processing
            document_id = path_params.get("documentId") or path.split("/")[2]
            return response(200, reprocess_document(document_id, body or {}))

        elif path.startswith("/documents/") and http_method == "GET":
            document_id = path_params.get("documentId") or path.split("/")[2]
            return response(200, get_document(document_id))

        elif path == "/upload" and http_method == "POST":
            filename = body.get("filename", "document.pdf") if body else "document.pdf"
            return response(200, create_upload_url(filename))

        elif path == "/metrics" and http_method == "GET":
            return response(200, get_metrics())

        # Review workflow endpoints
        elif path == "/review" and http_method == "GET":
            return response(200, list_review_queue(query_params))

        elif path.startswith("/review/") and "/approve" in path and http_method == "POST":
            # POST /review/{documentId}/approve
            document_id = path_params.get("documentId") or path.split("/")[2]
            return response(200, approve_document(document_id, body or {}))

        elif path.startswith("/review/") and "/reject" in path and http_method == "POST":
            # POST /review/{documentId}/reject
            document_id = path_params.get("documentId") or path.split("/")[2]
            return response(200, reject_document(document_id, body or {}))

        elif path.startswith("/review/") and http_method == "GET":
            # GET /review/{documentId} - Get document for review
            document_id = path_params.get("documentId") or path.split("/")[2]
            return response(200, get_document_for_review(document_id))

        else:
            return response(404, {"error": "Not found", "path": path, "method": http_method})

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return response(500, {"error": "Internal server error", "message": str(e)})
