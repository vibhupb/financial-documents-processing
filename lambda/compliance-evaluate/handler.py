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

    report = evaluate_document(doc_id, plugin_id, tree, pdf_bytes, baseline_ids=baseline_ids)
    _store_report(report)

    return {
        **event,
        "complianceReport": {
            "reportId": report["reportId"],
            "overallScore": report["overallScore"],
        },
    }
