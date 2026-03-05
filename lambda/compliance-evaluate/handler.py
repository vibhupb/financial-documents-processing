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
    tree = event.get("pageIndexTree") or _load_tree_from_s3(event)
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
