"""Compliance Evaluate Lambda — entry point."""
from evaluate import evaluate_document, _store_report, _load_tree_from_s3, _download_pdf


def lambda_handler(event, context):
    """Evaluate document against compliance baselines.

    Expected event keys:
        documentId: str -- the document ID to evaluate
        pluginId: str -- the document type plugin (e.g. 'loan_package')
        baselineIds: list[str] (optional) -- explicit baseline IDs from upload
        pageIndexTree: dict (optional) -- inline PageIndex tree
        pageIndexTreeS3Key: str (optional) -- S3 key for PageIndex tree
        documentKey: str -- S3 key for the PDF document
    """
    doc_id = event["documentId"]
    plugin_id = event.get("pluginId", "unknown")
    baseline_ids = event.get("baselineIds", [])

    # Load tree: check event first, then S3 key, then DynamoDB
    tree = event.get("pageIndexTree") or _load_tree_from_s3(event)
    if not tree or not tree.get("structure"):
        # Fall back to loading from DynamoDB (tree stored by PageIndex Lambda)
        import boto3 as _boto3
        import os as _os
        try:
            _table = _boto3.resource("dynamodb").Table(_os.environ.get("TABLE_NAME", "financial-documents"))
            _resp = _table.query(
                KeyConditionExpression=_boto3.dynamodb.conditions.Key("documentId").eq(doc_id),
                Limit=1,
            )
            if _resp.get("Items"):
                tree = _resp["Items"][0].get("pageIndexTree", {})
                if not tree.get("structure"):
                    # Try S3 reference
                    s3_key = _resp["Items"][0].get("pageIndexTreeS3Key")
                    if s3_key:
                        import json as _json
                        from evaluate import s3_client as _s3, BUCKET as _bucket
                        _obj = _s3.get_object(Bucket=_bucket, Key=s3_key)
                        tree = _json.loads(_obj["Body"].read())
                print(f"[Compliance] Loaded tree from DynamoDB: {len(tree.get('structure', []))} root nodes")
        except Exception as _e:
            print(f"[Compliance] Failed to load tree from DynamoDB: {_e}")

    pdf_bytes = _download_pdf(event)

    result = evaluate_document(doc_id, plugin_id, tree, pdf_bytes, baseline_ids=baseline_ids)

    # Handle both single report (dict) and multi-baseline (list of dicts)
    if isinstance(result, list):
        for report in result:
            _store_report(report)
        return {
            **event,
            "complianceReports": [
                {"reportId": r["reportId"], "overallScore": r["overallScore"]}
                for r in result
            ],
        }
    else:
        _store_report(result)
        return {
            **event,
            "complianceReport": {
                "reportId": result["reportId"],
                "overallScore": result["overallScore"],
            },
        }
