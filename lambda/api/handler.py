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
import re
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

    # Enrich each document with latestEvent from processingEvents
    for doc in documents:
        events = doc.get("processingEvents", [])
        if events:
            doc["latestEvent"] = events[-1]
        # Remove full processingEvents list from list response to keep payload small
        doc.pop("processingEvents", None)

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

    doc = items[0]

    # Load PageIndex tree from S3 if stored as reference (large trees)
    if not doc.get("pageIndexTree") and doc.get("pageIndexTreeS3Key"):
        try:
            resp = s3_client.get_object(
                Bucket=BUCKET_NAME, Key=doc["pageIndexTreeS3Key"]
            )
            doc["pageIndexTree"] = json.loads(resp["Body"].read().decode("utf-8"))
        except Exception:
            pass  # Non-critical — tree just won't be available

    return {"document": doc}


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


def create_upload_url(filename: str, processing_mode: str = "extract") -> dict[str, Any]:
    """Generate a presigned POST URL for document upload.

    Uses presigned POST instead of PUT for better CORS support with
    private S3 buckets. Uses regional S3 endpoint to avoid 307 redirects
    which break CORS in browsers.

    Args:
        filename: Original filename
        processing_mode: "extract" (default), "understand", or "both"
    """
    document_id = str(uuid.uuid4())
    key = f"ingest/{document_id}/{filename}"
    # Validate processing mode
    if processing_mode not in ("extract", "understand", "both"):
        processing_mode = "extract"

    try:
        # Use presigned POST which has better CORS support
        presigned_post = s3_client.generate_presigned_post(
            Bucket=BUCKET_NAME,
            Key=key,
            Fields={
                "Content-Type": "application/pdf",
                "x-amz-meta-processing-mode": processing_mode,
            },
            Conditions=[
                {"Content-Type": "application/pdf"},
                {"x-amz-meta-processing-mode": processing_mode},
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
    """Get enriched processing status from DynamoDB processingEvents.

    Reads the document record, extracts processingEvents, and derives
    per-stage status from the event log + overall document status.
    """
    table = dynamodb.Table(TABLE_NAME)

    try:
        result = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
            Limit=1,
        )
        items = result.get("Items", [])
        if not items:
            return {"documentId": document_id, "status": "NOT_FOUND"}

        doc = items[0]
        status = doc.get("status", "PENDING")
        document_type = doc.get("documentType", "")
        events = doc.get("processingEvents", [])
        created_at = doc.get("createdAt")
        updated_at = doc.get("updatedAt")

        # Derive per-stage status from events
        router_events = [e for e in events if e.get("stage") == "router"]
        extractor_events = [e for e in events if e.get("stage") == "extractor"]
        normalizer_events = [e for e in events if e.get("stage") == "normalizer"]

        # Classification stage
        classification_status = "PENDING"
        classification_result: dict[str, Any] = {}
        if router_events:
            classification_status = "COMPLETED"
            for evt in router_events:
                msg = evt.get("message", "")
                if "Classified as" in msg:
                    # Parse "Classified as credit_agreement (confidence: high)"
                    parts = msg.replace("Classified as ", "").split(" (confidence: ")
                    if len(parts) >= 2:
                        classification_result["documentType"] = parts[0]
                        classification_result["confidence"] = parts[1].rstrip(")")
                if "Targeted" in msg:
                    # Parse "Targeted 42/156 pages across 7 sections"
                    match = re.search(r"Targeted (\d+)/(\d+) pages across (\d+) sections", msg)
                    if match:
                        classification_result["targetedPages"] = int(match.group(1))
                        classification_result["totalPages"] = int(match.group(2))

        # Extraction stage
        extraction_status = "PENDING"
        extraction_progress: dict[str, Any] = {"completed": 0, "total": None, "currentSection": None}
        if extractor_events:
            # Count all section starts: "Processing section:" and "Skipped section:"
            started_sections = [e for e in extractor_events if "Processing section:" in e.get("message", "") or "Skipped section:" in e.get("message", "")]
            # Count all section completions: "Extracted data from" and "Skipped section:"
            finished_sections = [e for e in extractor_events if "Extracted data from" in e.get("message", "") or "Skipped section:" in e.get("message", "")]
            # Count only actively processed (non-skipped) for user-facing progress
            active_sections = [e for e in extractor_events if "Processing section:" in e.get("message", "")]
            completed_sections = [e for e in extractor_events if "Extracted data from" in e.get("message", "")]
            failed_sections = [e for e in extractor_events if "Failed to extract" in e.get("message", "")]

            extraction_progress["completed"] = len(completed_sections)
            extraction_progress["total"] = len(active_sections) if active_sections else None

            # All sections finished (completed + skipped + failed >= total started)
            if started_sections and len(finished_sections) + len(failed_sections) >= len(started_sections):
                extraction_status = "COMPLETED"
            elif extractor_events:
                extraction_status = "IN_PROGRESS"
                # Get the latest "Processing section" that hasn't completed or failed
                completed_names = set()
                for c in completed_sections + failed_sections:
                    # Extract section name from "Extracted data from <name> (...)" or "Failed to extract <name>: ..."
                    msg = c.get("message", "")
                    if "Extracted data from " in msg:
                        completed_names.add(msg.split("Extracted data from ")[1].split(" (")[0])
                    elif "Failed to extract " in msg:
                        completed_names.add(msg.split("Failed to extract ")[1].split(":")[0])
                for evt in reversed(active_sections):
                    section_name = evt.get("message", "").replace("Processing section: ", "")
                    if section_name not in completed_names:
                        extraction_progress["currentSection"] = section_name
                        break

        # Normalization stage
        normalization_status = "PENDING"
        if normalizer_events:
            if any("Normalization complete" in e.get("message", "") for e in normalizer_events):
                normalization_status = "COMPLETED"
            else:
                normalization_status = "IN_PROGRESS"

        # Override with overall status
        if status == "FAILED":
            if not router_events:
                classification_status = "FAILED"
            elif not extractor_events or extraction_status != "COMPLETED":
                extraction_status = "FAILED"
            else:
                normalization_status = "FAILED"

        # Build section list from extraction events
        sections = []
        for evt in extractor_events:
            msg = evt.get("message", "")
            if "Processing section:" in msg:
                sections.append(msg.replace("Processing section: ", ""))
        if sections:
            classification_result["sections"] = sections

        # Calculate elapsed time per stage from event timestamps
        def _stage_elapsed(stage_events: list) -> float | None:
            if len(stage_events) < 2:
                return None
            try:
                first_ts = stage_events[0].get("ts", "")
                last_ts = stage_events[-1].get("ts", "")
                t0 = datetime.fromisoformat(first_ts)
                t1 = datetime.fromisoformat(last_ts)
                return round((t1 - t0).total_seconds(), 1)
            except (ValueError, TypeError):
                return None

        return {
            "documentId": document_id,
            "status": status,
            "documentType": document_type,
            "stages": {
                "classification": {
                    "status": classification_status,
                    "elapsed": _stage_elapsed(router_events),
                    "result": classification_result if classification_result else None,
                },
                "extraction": {
                    "status": extraction_status,
                    "elapsed": _stage_elapsed(extractor_events),
                    "progress": extraction_progress,
                },
                "normalization": {
                    "status": normalization_status,
                    "elapsed": _stage_elapsed(normalizer_events),
                },
            },
            "events": events,
            "startedAt": created_at,
            "completedAt": updated_at if status in ("PROCESSED", "FAILED") else None,
        }

    except Exception as e:
        return {"error": f"Failed to get processing status: {str(e)}"}


def get_registered_plugins() -> dict[str, Any]:
    """Return registered document type plugins with their schemas.

    The frontend uses this to dynamically render extracted data
    for ANY document type without hardcoded component mappings.
    """
    try:
        from document_plugins.registry import get_all_plugins
        plugins = get_all_plugins()
        result = {}
        for plugin_id, config in plugins.items():
            result[plugin_id] = {
                "pluginId": plugin_id,
                "name": config.get("name", plugin_id),
                "description": config.get("description", ""),
                "version": config.get("plugin_version", "1.0.0"),
                "outputSchema": config.get("output_schema", {}),
                "classification": {
                    "keywords": config.get("classification", {}).get("keywords", [])[:10],
                },
                "sections": list(config.get("sections", {}).keys()),
                "hasPiiFields": len(config.get("pii_paths", [])) > 0,
                "requiresSignatures": config.get("requires_signatures", False),
                "_source": config.get("_source", "file"),
                "_dynamodb_item": config.get("_dynamodb_item"),
            }
        return {"plugins": result, "count": len(result)}
    except (ImportError, Exception) as e:
        return {"plugins": {}, "count": 0, "error": str(e)}


PLUGIN_CONFIGS_TABLE = os.environ.get("PLUGIN_CONFIGS_TABLE", "document-plugin-configs")


def _convert_floats_to_decimal(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimal(v) for v in obj]
    return obj


def create_plugin_config(body: dict[str, Any], user: Any) -> dict[str, Any]:
    """Create a new draft plugin configuration."""
    plugin_id = body.get("pluginId", "").strip().lower().replace(" ", "_")
    if not plugin_id:
        return {"error": "pluginId is required"}

    name = body.get("name", plugin_id)
    config = _convert_floats_to_decimal(body.get("config", {}))
    prompt_template = body.get("promptTemplate", "")
    timestamp = datetime.utcnow().isoformat() + "Z"

    table = dynamodb.Table(PLUGIN_CONFIGS_TABLE)
    item = {
        "pluginId": plugin_id,
        "version": "v1",
        "status": "DRAFT",
        "name": name,
        "description": body.get("description", ""),
        "config": config,
        "promptTemplate": prompt_template,
        "createdBy": getattr(user, 'email', 'unknown') if user else 'unknown',
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "testResults": [],
        "sampleDocumentKey": body.get("sampleDocumentKey", ""),
    }
    table.put_item(Item=item)
    return {"pluginId": plugin_id, "version": "v1", "status": "DRAFT"}


def _extract_fields_from_plugin(plugin_config: dict) -> list[dict]:
    """Extract FieldDef list from a file-based plugin config for the editor."""
    fields = []
    output_schema = plugin_config.get("output_schema", {})
    properties = output_schema.get("properties", {})
    for _section_key, section_schema in properties.items():
        if isinstance(section_schema, dict) and "properties" in section_schema:
            for field_key, field_schema in section_schema.get("properties", {}).items():
                schema_type = field_schema.get("type", "string")
                if schema_type in ("number", "integer"):
                    field_type = "number"
                elif schema_type == "boolean":
                    field_type = "boolean"
                else:
                    field_type = "string"
                fields.append({
                    "name": field_key,
                    "label": field_schema.get("description", field_key),
                    "type": field_type,
                    "query": "",
                })
    return fields


def get_plugin_config(plugin_id: str) -> dict[str, Any]:
    """Get a plugin config with all versions.

    Returns DynamoDB versions if they exist. For file-based plugins with no
    DynamoDB entry, returns a synthetic version so the editor can populate
    and allow editing (first save creates a DynamoDB override).
    """
    table = dynamodb.Table(PLUGIN_CONFIGS_TABLE)
    result = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("pluginId").eq(plugin_id),
        ScanIndexForward=False,  # Latest version first
    )
    items = result.get("Items", [])
    if items:
        return {
            "pluginId": plugin_id,
            "versions": items,
            "latestVersion": items[0].get("version"),
            "latestStatus": items[0].get("status"),
        }

    # Not in DynamoDB — try file-based registry and return synthetic version
    # with the FULL extraction pipeline config so edits preserve sections/queries
    try:
        from document_plugins.registry import get_plugin
        file_config = get_plugin(plugin_id)

        # Deep copy the full config, removing internal registry metadata
        full_config = copy.deepcopy(file_config)
        for k in ("_source", "_version", "_dynamodb_item", "_prompt_template_text"):
            full_config.pop(k, None)

        # Add wizard-friendly fields for the editor UI (in addition to the full config)
        full_config["fields"] = _extract_fields_from_plugin(file_config)
        full_config["keywords"] = file_config.get("classification", {}).get("keywords", [])
        full_config["promptRules"] = []

        synthetic_version = {
            "pluginId": plugin_id,
            "version": "file",
            "status": "PUBLISHED",
            "name": file_config.get("name", plugin_id),
            "description": file_config.get("description", ""),
            "config": _convert_floats_to_decimal(full_config),
            "_source": "file",
        }
        return {
            "pluginId": plugin_id,
            "versions": [synthetic_version],
            "latestVersion": "file",
            "latestStatus": "PUBLISHED",
            "_source": "file",
        }
    except (KeyError, ImportError):
        pass

    return {"error": "Plugin not found", "pluginId": plugin_id}


def update_plugin_config(plugin_id: str, body: dict[str, Any], user: Any) -> dict[str, Any]:
    """Update a draft plugin configuration (creates new version if published).

    If no DynamoDB entry exists (file-based plugin being edited for the first
    time), creates a new v1 DRAFT entry as a customized override.
    """
    table = dynamodb.Table(PLUGIN_CONFIGS_TABLE)
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Get latest version
    result = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("pluginId").eq(plugin_id),
        ScanIndexForward=False,
        Limit=1,
    )
    items = result.get("Items", [])
    if not items:
        # First edit of a file-based plugin — create DynamoDB override entry
        item = {
            "pluginId": plugin_id,
            "version": "v1",
            "status": "DRAFT",
            "name": body.get("name", plugin_id),
            "description": body.get("description", ""),
            "config": _convert_floats_to_decimal(body.get("config", {})),
            "promptTemplate": body.get("promptTemplate", ""),
            "createdBy": getattr(user, 'email', 'unknown') if user else 'unknown',
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "testResults": [],
        }
        table.put_item(Item=item)
        return {"pluginId": plugin_id, "version": "v1", "status": "DRAFT", "created": True}

    latest = items[0]
    current_version = latest["version"]
    current_status = latest.get("status", "DRAFT")

    # If published, create new draft version
    if current_status == "PUBLISHED":
        version_num = int(current_version.replace("v", "")) + 1
        new_version = f"v{version_num}"
        item = {
            "pluginId": plugin_id,
            "version": new_version,
            "status": "DRAFT",
            "name": body.get("name", latest.get("name", "")),
            "description": body.get("description", latest.get("description", "")),
            "config": _convert_floats_to_decimal(body.get("config", latest.get("config", {}))),
            "promptTemplate": body.get("promptTemplate", latest.get("promptTemplate", "")),
            "createdBy": getattr(user, 'email', 'unknown') if user else 'unknown',
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "testResults": [],
            "sampleDocumentKey": body.get("sampleDocumentKey", latest.get("sampleDocumentKey", "")),
        }
        table.put_item(Item=item)
        return {"pluginId": plugin_id, "version": new_version, "status": "DRAFT"}

    # Otherwise update the draft in place
    update_fields = {}
    for key in ["name", "description", "config", "promptTemplate", "sampleDocumentKey"]:
        if key in body:
            update_fields[key] = _convert_floats_to_decimal(body[key]) if key == "config" else body[key]
    update_fields["updatedAt"] = timestamp

    expr_parts = []
    attr_values = {}
    for i, (k, v) in enumerate(update_fields.items()):
        expr_parts.append(f"#{k} = :val{i}")
        attr_values[f":val{i}"] = v

    attr_names = {f"#{k}": k for k in update_fields}

    table.update_item(
        Key={"pluginId": plugin_id, "version": current_version},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )
    return {"pluginId": plugin_id, "version": current_version, "status": "DRAFT", "updated": True}


def publish_plugin_config(plugin_id: str, user: Any) -> dict[str, Any]:
    """Publish the latest draft version for production use."""
    table = dynamodb.Table(PLUGIN_CONFIGS_TABLE)
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Get latest version
    result = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("pluginId").eq(plugin_id),
        ScanIndexForward=False,
        Limit=1,
    )
    items = result.get("Items", [])
    if not items:
        return {"error": "Plugin not found"}

    latest = items[0]
    version = latest["version"]

    if latest.get("status") == "PUBLISHED":
        return {"error": "Already published", "version": version}

    # Unpublish any previously published version
    all_versions = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("pluginId").eq(plugin_id),
    ).get("Items", [])

    for item in all_versions:
        if item.get("status") == "PUBLISHED" and item["version"] != version:
            table.update_item(
                Key={"pluginId": plugin_id, "version": item["version"]},
                UpdateExpression="SET #s = :s, updatedAt = :t",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "ARCHIVED", ":t": timestamp},
            )

    # Publish this version
    table.update_item(
        Key={"pluginId": plugin_id, "version": version},
        UpdateExpression="SET #s = :s, updatedAt = :t, publishedBy = :by",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "PUBLISHED",
            ":t": timestamp,
            ":by": getattr(user, 'email', 'unknown') if user else 'unknown',
        },
    )

    return {"pluginId": plugin_id, "version": version, "status": "PUBLISHED"}


def delete_plugin_config(plugin_id: str) -> dict[str, Any]:
    """Delete DynamoDB overrides for a plugin.

    For plugins with a file-based baseline, this reverts to the original
    built-in defaults. For purely dynamic plugins, this deletes permanently.
    """
    has_file_source = False
    try:
        from document_plugins.registry import get_plugin
        existing = get_plugin(plugin_id)
        has_file_source = existing.get("_source") == "file"
    except (KeyError, ImportError):
        pass

    table = dynamodb.Table(PLUGIN_CONFIGS_TABLE)
    result = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("pluginId").eq(plugin_id),
    )
    items = result.get("Items", [])

    if not items and has_file_source:
        return {"error": "No customizations to delete — plugin uses built-in defaults"}

    deleted = 0
    for item in items:
        table.delete_item(Key={"pluginId": plugin_id, "version": item["version"]})
        deleted += 1

    message = "Reverted to built-in defaults" if has_file_source else "Plugin deleted"
    return {"pluginId": plugin_id, "deletedVersions": deleted, "message": message}


def analyze_sample_document(body: dict[str, Any]) -> dict[str, Any]:
    """Analyze a sample document: run Textract FORMS + PyPDF text extraction.

    Accepts an S3 key (from presigned upload) and returns raw extraction data
    that the wizard displays to the analyst.
    """
    s3_key = body.get("s3Key", "")
    bucket = body.get("bucket", os.environ.get("BUCKET_NAME", ""))
    if not s3_key or not bucket:
        return {"error": "s3Key and bucket are required"}

    results = {"pages": [], "forms": {}, "text": ""}

    try:
        # PyPDF text extraction (free, fast)
        s3_response = boto3.client("s3").get_object(Bucket=bucket, Key=s3_key)
        pdf_bytes = s3_response["Body"].read()

        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_texts = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            page_texts.append({"page": i + 1, "text": text[:2000], "charCount": len(text)})
        results["pages"] = page_texts
        results["pageCount"] = len(reader.pages)
        results["text"] = "\n\n".join(p["text"] for p in page_texts)[:10000]

        # Textract FORMS on first 3 pages (enough to detect field names)
        textract = boto3.client("textract")
        # Use first page as representative
        try:
            textract_response = textract.analyze_document(
                Document={"S3Object": {"Bucket": bucket, "Name": s3_key}},
                FeatureTypes=["FORMS", "TABLES"],
            )
            blocks = textract_response.get("Blocks", [])
            blocks_map = {b["Id"]: b for b in blocks}

            # Extract key-value pairs
            kv_pairs = {}
            for block in blocks:
                if block["BlockType"] == "KEY_VALUE_SET" and "KEY" in block.get("EntityTypes", []):
                    key_text = ""
                    for rel in block.get("Relationships", []):
                        if rel["Type"] == "CHILD":
                            for cid in rel["Ids"]:
                                cb = blocks_map.get(cid)
                                if cb and cb["BlockType"] == "WORD":
                                    key_text += cb.get("Text", "") + " "

                    value_text = ""
                    for rel in block.get("Relationships", []):
                        if rel["Type"] == "VALUE":
                            for vid in rel["Ids"]:
                                vb = blocks_map.get(vid)
                                if vb:
                                    for vrel in vb.get("Relationships", []):
                                        if vrel["Type"] == "CHILD":
                                            for wid in vrel["Ids"]:
                                                wb = blocks_map.get(wid)
                                                if wb and wb["BlockType"] == "WORD":
                                                    value_text += wb.get("Text", "") + " "

                    if key_text.strip():
                        kv_pairs[key_text.strip()] = {
                            "value": value_text.strip(),
                            "confidence": block.get("Confidence", 0),
                        }

            results["forms"] = kv_pairs
            results["formFieldCount"] = len(kv_pairs)
        except Exception as textract_err:
            results["textractError"] = str(textract_err)

    except Exception as e:
        return {"error": str(e)}

    return results


def generate_plugin_config(body: dict[str, Any]) -> dict[str, Any]:
    """Use Claude to auto-generate a plugin config from sample extraction data.

    Sends the raw extraction text + form fields to Claude with existing plugin
    examples, and gets back a draft plugin config + prompt template.
    """
    extracted_text = body.get("text", "")[:8000]
    form_fields_raw = body.get("formFields", {})
    doc_name = body.get("name", "New Document Type")
    page_count = body.get("pageCount", 1)

    if not extracted_text and not form_fields_raw:
        return {"error": "No extraction data provided"}

    # Normalize form_fields: accept both dict and list formats
    if isinstance(form_fields_raw, list):
        # Frontend sends [{key, value}, ...] — convert to dict
        form_fields = {
            f.get("key", ""): {"value": f.get("value", "")}
            for f in form_fields_raw if f.get("key")
        }
    elif isinstance(form_fields_raw, dict):
        form_fields = form_fields_raw
    else:
        form_fields = {}

    # Build the meta-prompt
    form_summary = "\n".join(f"  {k}: {v.get('value', '')}" for k, v in list(form_fields.items())[:50])

    prompt = f"""You are an expert at configuring document extraction pipelines.

Analyze this document and generate a plugin configuration for extracting structured data from it.

DOCUMENT NAME: {doc_name}
PAGE COUNT: {page_count}

TEXTRACT FORM FIELDS DETECTED:
{form_summary}

SAMPLE TEXT (first pages):
{extracted_text[:5000]}

Generate a JSON response with:
1. "pluginId": a snake_case identifier for this document type
2. "name": human-readable name
3. "description": what this document contains
4. "keywords": 10-15 classification keywords that distinguish this document
5. "fields": array of fields to extract, each with:
   - "name": camelCase field name
   - "label": human-readable label
   - "type": "string" | "number" | "date" | "boolean" | "currency"
   - "query": a Textract query question to extract this field
   - "formKey": the Textract form key name if detected (from the form fields above)
6. "promptRules": 5-10 normalization rules specific to this document type

Return ONLY valid JSON."""

    try:
        bedrock = boto3.client("bedrock-runtime")
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        response_body = json.loads(response["body"].read())
        content = response_body["content"][0]["text"]

        # Parse JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        generated = json.loads(content.strip())

        usage = response_body.get("usage", {})
        generated["_generation"] = {
            "model": "claude-haiku-4.5",
            "inputTokens": usage.get("input_tokens", 0),
            "outputTokens": usage.get("output_tokens", 0),
        }

        return generated

    except Exception as e:
        return {"error": f"AI generation failed: {str(e)}"}


def _deep_merge_configs(base: dict, override: dict) -> dict:
    """Deep merge override into base. Override values win on conflict."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge_configs(result[key], value)
        else:
            result[key] = copy.deepcopy(value) if isinstance(value, (dict, list)) else value
    return result


def refine_plugin_config(body: dict[str, Any]) -> dict[str, Any]:
    """Use Claude to refine a plugin config based on a plain-English instruction.

    For large configs (full extraction pipeline configs), uses a diff-based approach:
    the LLM returns only the changed/added parts, which are deep-merged into the
    original config. This avoids the LLM having to reproduce the entire config.
    """
    current_config = body.get("config", {})
    instruction = body.get("instruction", "").strip()

    if not instruction:
        return {"error": "No instruction provided"}
    if not current_config:
        return {"error": "No current config provided"}

    # Serialize current config for the prompt
    config_json = json.dumps(current_config, indent=2, default=str)
    is_large_config = len(config_json) > 5000

    if is_large_config:
        prompt = f"""You are an expert at configuring document extraction pipelines.

Below is the current plugin configuration for a document type. The user wants to modify it.

CURRENT CONFIGURATION:
```json
{config_json}
```

USER INSTRUCTION:
{instruction}

IMPORTANT: This config is large. Return ONLY the JSON keys/sections that need to change or be added.
The response will be deep-merged into the original config, so:
- Include only changed/new top-level keys and their complete values
- For nested objects like "sections", "output_schema": include the full subtree that changed
- For arrays like "fields": include the COMPLETE updated array (not partial)
- Do NOT include unchanged keys — they will be preserved from the original

For new fields in the "fields" array: use camelCase "name", descriptive "label", appropriate "type" (string|number|date|boolean|currency), and a Textract "query" question.
For new Textract queries in "sections.*.queries": add the query string to the section's queries array.
For new schema fields in "output_schema": add them to the appropriate section's properties.

Return ONLY valid JSON with the changed parts — no explanation, no markdown fences."""
    else:
        prompt = f"""You are an expert at configuring document extraction pipelines.

Below is the current plugin configuration for a document type. The user wants to modify it.

CURRENT CONFIGURATION:
```json
{config_json}
```

USER INSTRUCTION:
{instruction}

Apply the user's requested changes to the configuration. Rules:
- Return the COMPLETE updated configuration (not just the diff)
- For new fields: use camelCase "name", descriptive "label", appropriate "type" (string|number|date|boolean|currency), and a Textract "query" question
- For keyword changes: maintain 10-15 relevant classification keywords
- For rule changes: keep rules specific and actionable for LLM normalization
- Preserve all existing fields/rules that the user didn't ask to change
- If the instruction is ambiguous, make reasonable assumptions

Return ONLY valid JSON — no explanation, no markdown fences."""

    try:
        bedrock = boto3.client("bedrock-runtime")
        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 8192,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        response_body = json.loads(response["body"].read())
        content = response_body["content"][0]["text"]

        # Parse JSON from response (handle markdown fences just in case)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        changes = json.loads(content.strip())

        # For large configs, deep-merge the changes into the original
        if is_large_config:
            updated = _deep_merge_configs(current_config, changes)
        else:
            updated = changes

        usage = response_body.get("usage", {})
        updated["_refinement"] = {
            "model": "claude-haiku-4.5",
            "instruction": instruction,
            "inputTokens": usage.get("input_tokens", 0),
            "outputTokens": usage.get("output_tokens", 0),
        }

        return updated

    except json.JSONDecodeError as e:
        return {"error": f"AI returned invalid JSON: {str(e)}"}
    except Exception as e:
        return {"error": f"AI refinement failed: {str(e)}"}


# ---------------------------------------------------------------------------
# PageIndex endpoints
# ---------------------------------------------------------------------------

def get_document_tree(document_id: str) -> dict[str, Any]:
    """GET /documents/{id}/tree — return cached PageIndex tree.

    Tree may be stored inline in DynamoDB or in S3 (for large trees).
    """
    table = dynamodb.Table(TABLE_NAME)
    doc = _get_document_item(table, document_id)
    if not doc:
        return {"error": "Document not found"}

    tree = doc.get("pageIndexTree")

    # Check if tree is stored in S3 (large trees exceed DynamoDB 400KB limit)
    if not tree:
        s3_key = doc.get("pageIndexTreeS3Key")
        if s3_key:
            try:
                s3 = boto3.client("s3")
                resp = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
                tree = json.loads(resp["Body"].read().decode("utf-8"))
            except Exception as e:
                print(f"Failed to load tree from S3: {e}")

    if not tree:
        return {
            "documentId": document_id,
            "pageIndexTree": None,
            "message": "No PageIndex tree available for this document",
        }

    return {
        "documentId": document_id,
        "documentType": doc.get("documentType"),
        "status": doc.get("status"),
        "pageIndexTree": tree,
    }


def trigger_document_extraction(document_id: str) -> dict[str, Any]:
    """POST /documents/{id}/extract — trigger deferred extraction.

    For documents in INDEXED status (tree built, extraction deferred).
    Starts a new Step Functions execution that uses the cached tree.
    """
    table = dynamodb.Table(TABLE_NAME)
    doc = _get_document_item(table, document_id)
    if not doc:
        return {"error": "Document not found"}

    status = doc.get("status", "")
    if status not in ("INDEXED", "COMPLETED"):
        return {"error": f"Document not ready for extraction (status: {status})"}

    tree = doc.get("pageIndexTree")
    bucket = doc.get("bucket", os.environ.get("BUCKET_NAME", ""))
    key = doc.get("originalS3Key", "")
    plugin_id = doc.get("pluginId", "")

    if not key:
        return {"error": "Document has no S3 key for extraction"}

    # Start Step Functions execution with cached tree + skip flags
    sfn_input = {
        "documentId": document_id,
        "bucket": bucket,
        "key": key,
        "contentHash": doc.get("contentHash", ""),
        "size": doc.get("fileSize", 0),
        "processingMode": "extract",
        "pageIndexTree": tree if tree else None,
        "pluginId": plugin_id,
        "source": "deferred-extraction",
    }

    state_machine_arn = os.environ.get("STATE_MACHINE_ARN", "")
    if not state_machine_arn:
        return {"error": "STATE_MACHINE_ARN not configured"}

    try:
        import re as _re
        safe_id = _re.sub(r"[^a-zA-Z0-9_-]", "_", document_id)[:8]
        from datetime import datetime as _dt
        exec_name = f"extract-{safe_id}-{int(_dt.utcnow().timestamp())}"
        sfn_client = boto3.client("stepfunctions")
        resp = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=exec_name,
            input=json.dumps(sfn_input, default=str),
        )
        # Update status
        table.update_item(
            Key={"documentId": document_id, "documentType": doc["documentType"]},
            UpdateExpression="SET #s = :s, updatedAt = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "EXTRACTING",
                ":now": _dt.utcnow().isoformat() + "Z",
            },
        )
        return {
            "documentId": document_id,
            "status": "EXTRACTING",
            "executionArn": resp["executionArn"],
        }
    except Exception as e:
        return {"error": f"Failed to start extraction: {str(e)}"}


def ask_document(document_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST /documents/{id}/ask — Hybrid Q&A over extracted data + PageIndex tree.

    Three-source approach:
    1. Already-extracted structured data (highest quality, from Textract + normalization)
    2. Tree navigation to find relevant PDF pages (for questions beyond extraction)
    3. Combined context for LLM answer generation
    """
    question = (body.get("question") or "").strip()
    if not question:
        return {"error": "Question is required"}

    table = dynamodb.Table(TABLE_NAME)
    doc = _get_document_item(table, document_id)
    if not doc:
        return {"error": "Document not found"}

    tree = doc.get("pageIndexTree")
    if not tree or not tree.get("structure"):
        return {"error": "No PageIndex tree available for Q&A"}

    bucket = doc.get("bucket", os.environ.get("BUCKET_NAME", ""))
    key = doc.get("originalS3Key", "")

    # Gather extracted data if available (primary source)
    extracted_data = doc.get("extractedData") or doc.get("data") or {}
    extracted_context = ""
    if extracted_data:
        try:
            extracted_json = json.dumps(extracted_data, indent=2, default=str)
            # Cap at 8K chars to leave room for page text
            if len(extracted_json) > 8000:
                extracted_json = extracted_json[:8000] + "\n... (truncated)"
            extracted_context = (
                f"=== EXTRACTED STRUCTURED DATA ===\n"
                f"(This data was extracted and verified from the document via OCR)\n"
                f"{extracted_json}\n"
                f"=== END EXTRACTED DATA ===\n\n"
            )
        except Exception:
            pass

    try:
        bedrock_client = boto3.client("bedrock-runtime")
        model_id = os.environ.get(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        )

        # Step 1: Navigate tree to find relevant nodes
        # Build a compact tree (title + node_id + pages only) to save tokens
        compact_tree = _build_compact_tree(tree["structure"])
        nav_prompt = (
            "You are analyzing a document's table of contents to find sections "
            "relevant to a user's question.\n\n"
            f"Question: {question}\n\n"
            f"Document: {tree.get('doc_description', 'Unknown document')}\n"
            f"Total pages: {tree.get('total_pages', '?')}\n\n"
            f"Table of contents:\n{compact_tree}\n\n"
            "Think about WHERE in a document this information would typically appear. "
            "For example:\n"
            "- Party names/borrowers → preamble (first pages), signature pages, or recitals\n"
            "- Financial terms → specific articles about rates, fees, payments\n"
            "- Definitions → definitions section (but prefer the actual substantive sections)\n"
            "- Covenants → covenant articles\n\n"
            "Select the most relevant leaf nodes (prefer specific sections over broad parent nodes). "
            "Pick 3-6 nodes maximum.\n\n"
            'Return JSON: {"thinking": "<your reasoning>", "node_ids": ["0001", "0005"]}'
        )

        nav_resp = bedrock_client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": nav_prompt}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 1024},
        )
        nav_text = nav_resp["output"]["message"]["content"][0]["text"]

        # Parse node IDs
        node_ids = []
        try:
            nav_json = json.loads(
                nav_text.replace("```json", "").replace("```", "").strip()
            )
            node_ids = nav_json.get("node_ids", nav_json.get("node_list", []))
        except json.JSONDecodeError:
            import re
            node_ids = re.findall(r'"(\d{4})"', nav_text)

        # Step 2: Gather page text from relevant nodes
        sorted_pages: list[int] = []
        page_texts = ""
        if node_ids:
            all_nodes = _flatten_tree_nodes(tree["structure"])
            node_map = {n.get("node_id"): n for n in all_nodes}
            relevant_pages: set[int] = set()
            for nid in node_ids:
                node = node_map.get(nid)
                if node:
                    start = int(node.get("start_index", 0))
                    end = int(node.get("end_index", start))
                    # Cap each node's contribution to 5 pages
                    end = min(end, start + 4)
                    relevant_pages.update(range(start, end + 1))

            # Limit to 15 pages to leave room for extracted data context
            sorted_pages = sorted(relevant_pages)[:15]

            if sorted_pages:
                page_texts = _extract_pages_for_qa(bucket, key, sorted_pages)

        # Step 3: Generate answer using both sources
        context_parts = []
        if extracted_context:
            context_parts.append(extracted_context)
        if page_texts:
            context_parts.append(
                f"=== RELEVANT PAGE TEXT (pages {sorted_pages}) ===\n"
                f"{page_texts}\n"
                f"=== END PAGE TEXT ===\n"
            )

        if not context_parts:
            return {
                "answer": "I couldn't find relevant information to answer this question.",
                "sourceNodes": node_ids,
                "sourcePages": [],
            }

        combined_context = "\n".join(context_parts)

        answer_prompt = (
            "Answer the following question using the document context below. "
            "The context includes two sources:\n"
            "1. EXTRACTED STRUCTURED DATA — verified, high-quality data from OCR extraction\n"
            "2. RELEVANT PAGE TEXT — raw text from specific pages of the document\n\n"
            "Prefer the extracted structured data when it contains the answer. "
            "Use page text for additional detail or when the extracted data doesn't cover the question. "
            "Be specific, cite sources (extracted data or page numbers), and provide a complete answer.\n\n"
            f"Question: {question}\n\n"
            f"{combined_context}\n"
            "Answer:"
        )

        answer_resp = bedrock_client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": answer_prompt}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 2048},
        )
        answer = answer_resp["output"]["message"]["content"][0]["text"]

        return {
            "answer": answer,
            "sourceNodes": node_ids,
            "sourcePages": sorted_pages,
            "question": question,
        }

    except Exception as e:
        return {"error": f"Q&A failed: {str(e)}"}


def _build_compact_tree(nodes: list, depth: int = 0) -> str:
    """Build a compact text representation of the tree for navigation prompts."""
    lines = []
    indent = "  " * depth
    for node in nodes:
        nid = node.get("node_id", "?")
        title = node.get("title", "?")
        start = node.get("start_index", "?")
        end = node.get("end_index", start)
        page_str = f"p.{start}" if start == end else f"p.{start}-{end}"
        lines.append(f"{indent}[{nid}] {title} ({page_str})")
        children = node.get("nodes", [])
        if children:
            lines.append(_build_compact_tree(children, depth + 1))
    return "\n".join(lines)


def generate_section_summary(
    document_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    """POST /documents/{id}/section-summary — On-demand summary for a tree node.

    Checks if a cached summary exists first. If not, extracts the section's
    page text, generates a summary via LLM, and caches it in both DynamoDB
    (inline in the tree node) and S3 (audit trail).
    """
    node_id = (body.get("nodeId") or "").strip()
    if not node_id:
        return {"error": "nodeId is required"}

    table = dynamodb.Table(TABLE_NAME)
    doc = _get_document_item(table, document_id)
    if not doc:
        return {"error": "Document not found"}

    tree = doc.get("pageIndexTree")
    if not tree or not tree.get("structure"):
        return {"error": "No PageIndex tree available"}

    # Find the target node
    all_nodes = _flatten_tree_nodes(tree["structure"])
    node_map = {n.get("node_id"): n for n in all_nodes}
    target = node_map.get(node_id)
    if not target:
        return {"error": f"Node {node_id} not found in tree"}

    # Check cache — return immediately if summary already exists
    cached = target.get("summary")
    if cached:
        return {
            "nodeId": node_id,
            "summary": cached,
            "cached": True,
        }

    # Extract page text for this section
    bucket = doc.get("bucket", os.environ.get("BUCKET_NAME", ""))
    key = doc.get("originalS3Key", "")
    start = int(target.get("start_index", 1))
    end = int(target.get("end_index", start))
    page_numbers = list(range(start, min(end, start + 20) + 1))  # cap at 20 pages

    page_texts = _extract_pages_for_qa(bucket, key, page_numbers)
    if page_texts.startswith("("):
        return {"error": f"Could not extract text: {page_texts}"}

    # Generate summary via LLM
    try:
        bedrock_client = boto3.client("bedrock-runtime")
        model_id = os.environ.get(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        )

        prompt = (
            "Generate a concise summary (2-4 sentences) of this document section. "
            "Focus on the key provisions, terms, or information covered.\n\n"
            f"Section: {target.get('title', 'Unknown')}\n"
            f"Pages {start}-{end}\n\n"
            f"{page_texts}\n\n"
            "Summary:"
        )

        resp = bedrock_client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 512},
        )
        summary = resp["output"]["message"]["content"][0]["text"].strip()
    except Exception as e:
        return {"error": f"Summary generation failed: {str(e)}"}

    # Cache the summary back into the tree
    _cache_section_summary(doc, tree, node_id, summary, bucket, document_id)

    return {
        "nodeId": node_id,
        "summary": summary,
        "cached": False,
        "pages": page_numbers,
    }


def _cache_section_summary(
    doc: dict, tree: dict, node_id: str, summary: str,
    bucket: str, document_id: str,
) -> None:
    """Write the generated summary back into the tree in DynamoDB and S3."""
    # Update the node in the tree structure in-memory
    _set_node_summary(tree["structure"], node_id, summary)

    # Write updated tree to S3 audit (always works, no size limit)
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=f"audit/{document_id}/pageindex-tree.json",
            Body=json.dumps(tree, indent=2, default=str),
            ContentType="application/json",
        )
    except Exception:
        pass

    # Update DynamoDB — only if tree is stored inline (not S3 reference)
    if doc.get("pageIndexTree"):
        from decimal import Decimal

        def _sanitize(obj: Any) -> Any:
            if isinstance(obj, float):
                return Decimal(str(round(obj, 6)))
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_sanitize(v) for v in obj]
            return obj

        doc_type = doc.get("documentType", "PROCESSING")
        try:
            table = dynamodb.Table(TABLE_NAME)
            table.update_item(
                Key={"documentId": document_id, "documentType": doc_type},
                UpdateExpression="SET pageIndexTree = :tree",
                ExpressionAttributeValues={":tree": _sanitize(tree)},
            )
        except Exception:
            pass  # Non-critical — S3 has the authoritative copy


def _set_node_summary(nodes: list, node_id: str, summary: str) -> bool:
    """Recursively find a node by ID and set its summary."""
    for node in nodes:
        if node.get("node_id") == node_id:
            node["summary"] = summary
            return True
        if node.get("nodes") and _set_node_summary(node["nodes"], node_id, summary):
            return True
    return False


def _get_document_item(table: Any, document_id: str) -> dict | None:
    """Query DynamoDB for a document by ID (any documentType)."""
    resp = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def _flatten_tree_nodes(nodes: list) -> list:
    """Flatten a nested tree structure to a flat list."""
    flat = []
    for node in nodes:
        flat.append(node)
        if node.get("nodes"):
            flat.extend(_flatten_tree_nodes(node["nodes"]))
    return flat


def _extract_pages_for_qa(
    bucket: str, key: str, page_numbers: list[int]
) -> str:
    """Download PDF and extract text from specific pages for Q&A."""
    try:
        from io import BytesIO
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_bytes = resp["Body"].read()

        # Try PyPDF2 first
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(BytesIO(pdf_bytes))
            parts = []
            for pn in page_numbers:
                if 1 <= pn <= len(reader.pages):
                    text = reader.pages[pn - 1].extract_text() or ""
                    parts.append(f"--- Page {pn} ---\n{text[:3000]}")
            return "\n\n".join(parts)
        except Exception:
            pass

        # Fallback to PyMuPDF
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            parts = []
            for pn in page_numbers:
                if 1 <= pn <= len(doc):
                    text = doc[pn - 1].get_text() or ""
                    parts.append(f"--- Page {pn} ---\n{text[:3000]}")
            doc.close()
            return "\n\n".join(parts)
        except Exception:
            pass

        return "(Could not extract page text)"
    except Exception as e:
        return f"(Error reading PDF: {e})"


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
        # Sanitize name: Step Functions only allows [a-zA-Z0-9-_]
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", document_id)[:8]
        execution_name = f"{safe_id}-reprocess-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

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

    # Helper: extract and URL-decode document ID from path params or URL
    def _doc_id() -> str:
        raw = path_params.get("documentId") or path.split("/")[2]
        return unquote(raw)

    try:
        # Route requests
        if path == "/documents" and http_method == "GET":
            return response(200, list_documents(query_params))

        elif path.startswith("/documents/") and "/audit" in path and http_method == "GET":
            return response(200, get_document_audit(_doc_id()))

        elif path.startswith("/documents/") and "/status" in path and http_method == "GET":
            return response(200, get_processing_status(_doc_id()))

        elif path.startswith("/documents/") and "/pdf" in path and http_method == "GET":
            return response(200, get_document_pdf_url(_doc_id()))

        elif path.startswith("/documents/") and "/fields" in path and http_method == "PUT":
            # PUT /documents/{documentId}/fields - Correct field values
            return response(200, correct_document_fields(_doc_id(), body or {}))

        elif path.startswith("/documents/") and "/reprocess" in path and http_method == "POST":
            # POST /documents/{documentId}/reprocess - Trigger re-processing
            return response(200, reprocess_document(_doc_id(), body or {}))

        elif path.startswith("/documents/") and "/tree" in path and http_method == "GET":
            # GET /documents/{documentId}/tree - Get PageIndex tree
            return response(200, get_document_tree(_doc_id()))

        elif path.startswith("/documents/") and "/extract" in path and http_method == "POST":
            # POST /documents/{documentId}/extract - Trigger deferred extraction
            return response(200, trigger_document_extraction(_doc_id()))

        elif path.startswith("/documents/") and "/ask" in path and http_method == "POST":
            # POST /documents/{documentId}/ask - Q&A over document tree
            return response(200, ask_document(_doc_id(), body or {}))

        elif path.startswith("/documents/") and "/section-summary" in path and http_method == "POST":
            # POST /documents/{documentId}/section-summary - On-demand section summary
            return response(200, generate_section_summary(_doc_id(), body or {}))

        elif path.startswith("/documents/") and http_method == "GET":
            return response(200, get_document(_doc_id()))

        elif path == "/upload" and http_method == "POST":
            filename = body.get("filename", "document.pdf") if body else "document.pdf"
            processing_mode = body.get("processingMode", "extract") if body else "extract"
            return response(200, create_upload_url(filename, processing_mode))

        elif path == "/metrics" and http_method == "GET":
            return response(200, get_metrics())

        elif path == "/plugins" and http_method == "GET":
            return response(200, get_registered_plugins())

        elif path == "/plugins" and http_method == "POST":
            return response(200, create_plugin_config(body or {}, user))

        elif path == "/plugins/analyze" and http_method == "POST":
            return response(200, analyze_sample_document(body or {}))

        elif path == "/plugins/generate" and http_method == "POST":
            return response(200, generate_plugin_config(body or {}))

        elif path == "/plugins/refine" and http_method == "POST":
            return response(200, refine_plugin_config(body or {}))

        elif path.startswith("/plugins/") and "/test" in path and http_method == "POST":
            pid = path.split("/")[2]
            # Test runs the full pipeline on the sample - reuse existing Step Functions
            return response(200, {"pluginId": pid, "status": "TEST_QUEUED", "message": "Test run queued (Phase 3)"})

        elif path.startswith("/plugins/") and "/publish" in path and http_method == "POST":
            pid = path.split("/")[2]
            return response(200, publish_plugin_config(pid, user))

        elif path.startswith("/plugins/") and http_method == "GET":
            pid = path_params.get("pluginId") or path.split("/")[2]
            return response(200, get_plugin_config(pid))

        elif path.startswith("/plugins/") and http_method == "PUT":
            pid = path_params.get("pluginId") or path.split("/")[2]
            return response(200, update_plugin_config(pid, body or {}, user))

        elif path.startswith("/plugins/") and http_method == "DELETE":
            pid = path_params.get("pluginId") or path.split("/")[2]
            return response(200, delete_plugin_config(pid))

        # Review workflow endpoints
        elif path == "/review" and http_method == "GET":
            return response(200, list_review_queue(query_params))

        elif path.startswith("/review/") and "/approve" in path and http_method == "POST":
            # POST /review/{documentId}/approve
            return response(200, approve_document(_doc_id(), body or {}))

        elif path.startswith("/review/") and "/reject" in path and http_method == "POST":
            # POST /review/{documentId}/reject
            return response(200, reject_document(_doc_id(), body or {}))

        elif path.startswith("/review/") and http_method == "GET":
            # GET /review/{documentId} - Get document for review
            return response(200, get_document_for_review(_doc_id()))

        else:
            return response(404, {"error": "Not found", "path": path, "method": http_method})

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return response(500, {"error": "Internal server error", "message": str(e)})
