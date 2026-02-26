"""Extractor Lambda - Targeted Textract Extraction

This Lambda function implements the "Surgeon" pattern:
1. Receives specific page numbers from the Router
2. Extracts ONLY those pages from the PDF
3. Uses Amazon Textract with targeted queries/tables/forms
4. Returns structured extraction results

This is the PRECISION layer - we use Textract's visual grounding
for accurate extraction of specific document elements.

Supports both single-page extraction (mortgage docs) and multi-page
section extraction (Credit Agreements).
"""

import datetime
import json
import os
import io
import boto3
from botocore.exceptions import ClientError
from pypdf import PdfReader, PdfWriter
from typing import Dict, List, Any, Optional, Tuple
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# PyMuPDF for rendering PDF pages to images (Textract works better with images)
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("Warning: PyMuPDF not available. Falling back to PDF-based extraction.")

# Initialize AWS clients
s3_client = boto3.client('s3')
textract_client = boto3.client('textract')

# Configuration
BUCKET_NAME = os.environ.get('BUCKET_NAME')

# Confidence threshold for financial documents (AWS recommends 90%+ for financial applications)
# Results below this threshold will be flagged as low confidence
CONFIDENCE_THRESHOLD = float(os.environ.get('CONFIDENCE_THRESHOLD', '85.0'))

# Parallel processing configuration
# Max workers for concurrent Textract API calls (balances speed vs API throttling)
# 30 workers utilizes ~60% of 50 TPS Textract quota (leaves headroom for burst/overhead)
MAX_PARALLEL_WORKERS = int(os.environ.get('MAX_PARALLEL_WORKERS', '30'))

# Image rendering DPI - balance between quality and speed
# 150 DPI is sufficient for OCR while being faster than 200 DPI
IMAGE_DPI = int(os.environ.get('IMAGE_DPI', '150'))

# Step Functions payload limit is 256KB. We need to truncate rawText to prevent DataLimitExceeded errors.
# Leave ~100KB for other data (tables, queries, metadata), so cap rawText at 150KB.
# The normalizer uses MAX_LOAN_AGREEMENT_RAW_TEXT = 50000, but we can be more generous at extractor level
# since Step Functions combines multiple extraction results in parallel state.
MAX_RAW_TEXT_CHARS = int(os.environ.get('MAX_RAW_TEXT_CHARS', '80000'))  # ~80KB max for rawText
S3_EXTRACTION_PREFIX = os.environ.get('S3_EXTRACTION_PREFIX', 'extractions/')
TABLE_NAME = os.environ.get('TABLE_NAME', 'financial-documents')


def append_processing_event(document_id: str, document_type: str, stage: str, message: str):
    """Append a timestamped event to the document's processingEvents list."""
    try:
        table = boto3.resource("dynamodb").Table(TABLE_NAME)
        table.update_item(
            Key={"documentId": document_id, "documentType": document_type},
            UpdateExpression="SET processingEvents = list_append(if_not_exists(processingEvents, :empty), :event)",
            ExpressionAttributeValues={
                ":event": [{
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "stage": stage,
                    "message": message,
                }],
                ":empty": [],
            },
        )
    except Exception:
        pass  # Non-critical — don't fail processing if event logging fails


# ==========================================
# Plugin-Driven Generic Section Extraction
# ==========================================


def extract_section_generic(
    bucket: str,
    key: str,
    document_id: str,
    section_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Generic section extraction for Step Functions Map state.

    Receives sectionConfig from the plugin and delegates to appropriate
    Textract features. Replaces per-document-type extraction branches.
    """
    section_id = section_config.get("sectionId", "unknown")
    pages = section_config.get("sectionPages", [])
    textract_features = section_config.get("textractFeatures", [])
    queries = section_config.get("queries", [])
    sc = section_config.get("sectionConfig", section_config)
    include_pypdf = sc.get("include_pypdf_text", False)
    extract_sigs = sc.get("extract_signatures", False)
    render_dpi = sc.get("render_dpi", IMAGE_DPI)

    # Resolve DynamoDB documentType for event logging
    _doc_type_for_events = "PROCESSING"
    try:
        _q = boto3.resource("dynamodb").Table(TABLE_NAME).query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
            Limit=1,
        )
        if _q.get("Items"):
            _doc_type_for_events = _q["Items"][0].get("documentType", "PROCESSING")
    except Exception:
        pass

    if not pages:
        section_name = sc.get("name", section_id)
        append_processing_event(document_id, _doc_type_for_events, "extractor", f"Skipped section: {section_name} (no pages identified)")
        return {
            "section": section_id,
            "status": "SKIPPED",
            "reason": "No pages identified",
            "results": None,
        }

    section_name = sc.get("name", section_id)
    append_processing_event(document_id, _doc_type_for_events, "extractor", f"Processing section: {section_name}")

    print(f"extract_section_generic: '{section_id}' pages={pages} "
          f"features={textract_features} queries={len(queries)}")

    section_start = time.time()
    results = {}
    textract_failed = False
    page_images = []
    temp_key = None

    try:
        # Download PDF
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_stream = io.BytesIO(s3_response['Body'].read())

        # Extract section pages
        section_bytes = extract_multiple_pages(pdf_stream, pages)

        # Render to images
        if PYMUPDF_AVAILABLE:
            try:
                page_images = render_pdf_pages_to_images(section_bytes, dpi=render_dpi)
                results["pagesProcessed"] = len(page_images)
            except Exception as e:
                print(f"Image rendering failed for '{section_id}': {e}")

        # S3 fallback
        if not page_images:
            temp_key = upload_temp_section(bucket, document_id, section_id, section_bytes)

        # Run each Textract feature
        for feature in textract_features:
            feat = feature.upper()
            if feat == "QUERIES" and queries:
                if page_images and len(page_images) > 1:
                    results["queries"] = process_pages_queries_parallel(page_images, queries, bucket)
                elif page_images:
                    results["queries"] = extract_with_queries(bucket, "", queries, image_bytes=page_images[0])
                elif temp_key:
                    results["queries"] = extract_with_queries(bucket, temp_key, queries)
                textract_failed = textract_failed or not results.get("queries")

            elif feat == "TABLES":
                if page_images and len(page_images) > 1:
                    tables, failed = process_pages_tables_parallel(page_images, bucket)
                    results["tables"] = {"tables": tables, "tableCount": len(tables)}
                    textract_failed = textract_failed or failed
                elif page_images:
                    results["tables"] = extract_tables(bucket, "", image_bytes=page_images[0])
                elif temp_key:
                    results["tables"] = extract_tables(bucket, temp_key)

            elif feat == "FORMS":
                if page_images and len(page_images) > 1:
                    # Multi-page forms: extract per-page and merge
                    all_kv = {}
                    for idx, img in enumerate(page_images):
                        page_result = extract_forms(bucket, "", image_bytes=img)
                        for k, v in page_result.get("keyValues", {}).items():
                            if k not in all_kv or (isinstance(v, dict) and v.get("confidence", 0) >
                                    all_kv[k].get("confidence", 0)):
                                all_kv[k] = v
                    results["forms"] = {"keyValues": all_kv, "fieldCount": len(all_kv)}
                elif page_images:
                    results["forms"] = extract_forms(bucket, "", image_bytes=page_images[0])
                elif temp_key:
                    results["forms"] = extract_forms(bucket, temp_key)

        # Signature detection
        if extract_sigs and page_images:
            if len(page_images) > 1:
                all_sigs = process_pages_signatures_parallel(page_images, bucket)
                results["signatures"] = {
                    "signatures": all_sigs,
                    "signatureCount": len(all_sigs),
                    "hasSignatures": len(all_sigs) > 0,
                }
            else:
                results["signatures"] = extract_signatures(bucket, "", image_bytes=page_images[0])

        # PyPDF text
        if include_pypdf:
            pdf_stream.seek(0)
            raw_text = extract_text_from_pages(pdf_stream, pages)
            if raw_text:
                if len(raw_text) > MAX_RAW_TEXT_CHARS:
                    raw_text = raw_text[:MAX_RAW_TEXT_CHARS] + "\n\n... [TRUNCATED]"
                results["rawText"] = raw_text

        # OCR fallback for scanned/low-quality pages.
        # If PyPDF yields very little text (<500 chars) and we have page images,
        # fall back to Textract DetectDocumentText for OCR-based raw text.
        # This restores the hybrid OCR logic from the legacy
        # extract_loan_agreement_multi_page function.
        low_quality_fallback = sc.get("low_quality_fallback", False)
        pypdf_text_len = len(results.get("rawText", ""))
        if low_quality_fallback and page_images and pypdf_text_len < 500:
            print(f"OCR fallback for '{section_id}': PyPDF text too short "
                  f"({pypdf_text_len} chars), running Textract OCR on "
                  f"{len(page_images)} page images")
            try:
                ocr_text = extract_raw_text_ocr_parallel(page_images, bucket)
                if ocr_text and len(ocr_text) > pypdf_text_len:
                    if len(ocr_text) > MAX_RAW_TEXT_CHARS:
                        ocr_text = ocr_text[:MAX_RAW_TEXT_CHARS] + "\n\n... [TRUNCATED]"
                    results["rawText"] = ocr_text
                    results["rawTextSource"] = "textract_ocr"
                    print(f"OCR fallback produced {len(ocr_text)} chars (replaced PyPDF)")
            except Exception as ocr_err:
                print(f"OCR fallback failed for '{section_id}': {ocr_err}")

        # Cleanup
        if temp_key:
            try:
                s3_client.delete_object(Bucket=bucket, Key=temp_key)
            except Exception:
                pass

        processing_time = time.time() - section_start
        append_processing_event(document_id, _doc_type_for_events, "extractor", f"Extracted data from {section_name} ({len(pages)} pages, {round(processing_time, 1)}s)")
        return {
            "section": section_id,
            "status": "EXTRACTED" if not textract_failed else "PARTIAL_EXTRACTION",
            "pageNumbers": pages,
            "pageCount": len(pages),
            "pagesProcessed": len(page_images) if page_images else 1,
            "results": results,
            "processingTimeSeconds": round(processing_time, 2),
        }

    except Exception as e:
        print(f"Error extracting section '{section_id}': {e}")
        append_processing_event(document_id, _doc_type_for_events, "extractor", f"Failed to extract {section_name}: {e}")
        if temp_key:
            try:
                s3_client.delete_object(Bucket=bucket, Key=temp_key)
            except Exception:
                pass
        return {
            "section": section_id,
            "status": "FAILED",
            "pageNumbers": pages,
            "error": str(e),
        }


# COMPREHENSIVE Credit Agreement section-specific queries
# Optimized for both speed AND extraction quality based on ground truth analysis
# Key insight: Specific queries get higher confidence than consolidated "or" queries
# Updated to fix: borrower identification, rate index, effective date, missing facilities
CREDIT_AGREEMENT_QUERIES = {
    "agreementInfo": [
        # Document identification - SPECIFIC queries work better than consolidated
        "What type of agreement is this?",  # 93% confidence - CRITICAL
        "What is the document title or type?",  # 98% confidence
        "What is the Instrument Type or Loan Type?",
        # Dates - FIX: Add explicit effective date queries
        "What is the date this agreement is dated as of?",  # NEW: Critical for effective date
        "What is the agreement date or effective date?",
        "What is the Effective Date of this agreement?",  # NEW: Direct query
        "What is the Closing Date?",  # NEW: Alternative name for effective date
        "What is the Maturity Date?",  # Separate for higher confidence
        "What is the Termination Date?",
        # Parties - FIX: Extract ALL joint borrowers (not just one)
        "Who are all the companies listed as Borrower?",  # NEW: Gets all joint borrowers
        "List all company names that together are the Borrower",  # NEW: Joint borrower extraction
        "What companies are named as Borrower in this agreement?",  # NEW: Agreement context
        "Who is the Borrower?",  # Keep original - may return multiple names
        "Who are the Borrowers identified in the first paragraph?",  # NEW: First paragraph context
        "What companies together constitute the Borrower?",  # NEW: Explicitly joint
        "Who is the Company or Primary Obligor?",
        "Who is the Ultimate Holdings or Parent Company?",  # NEW: For complex structures
        "Who is the Intermediate Holdings?",  # NEW: For holding structures
        "Who is the Administrative Agent?",  # Separate for clarity
        "Who is the Collateral Agent?",
        # Amendment tracking - FIX: More specific to avoid false positives
        "What is the Amendment Number in the document title?",  # NEW: More specific
        "Is this document titled as an amendment? What number?",  # NEW: Context aware
        "Is this an amendment and restatement?",
        # Currency
        "What is the currency of this loan?",
        "What currency are amounts denominated in?",  # NEW: Alternative phrasing
    ],
    "applicableRates": [
        # Rate Index - FIX: Better SOFR vs Prime detection
        "What is the Rate Index used (SOFR, LIBOR, Prime)?",  # NEW: Direct question
        "Is the loan rate based on Term SOFR?",  # NEW: Specific SOFR check
        "What benchmark rate is used for interest calculation?",  # NEW: Broader check
        "What is the Reference Rate or Index Rate?",  # NEW: Alternative terms
        # Rate/Margin
        "What is the Applicable Rate or Applicable Margin?",
        "What is the Spread added to the index rate?",  # NEW: Clearer phrasing
        "What is the Base Rate?",
        # SOFR - specific queries
        "What is the Term SOFR spread or margin?",
        "What is the Daily Simple SOFR spread?",
        "What is the Adjusted Term SOFR spread?",
        "What is the SOFR floor rate?",  # NEW: SOFR-specific floor
        # Rate type - IMPROVED detection
        "Is the interest rate Fixed or Variable/Floating?",  # NEW: Clearer options
        "Does this loan use SOFR or Prime as the base rate?",  # NEW: Binary choice
        # ABR/Prime
        "What is the ABR spread or Base Rate spread?",
        "What is the Prime Rate margin?",
        "What is the Alternate Base Rate?",  # NEW: ABR definition
        # Day Count
        "What is the Day Count Convention?",
        "What year basis is used for interest calculation (360 or 365)?",  # NEW: Specific
        # Fees within rates
        "What is the commitment fee rate?",
        "What is the unused commitment fee?",
        "What is the LC fee rate?",
        "What is the Letter of Credit participation fee?",  # NEW: LC specific
        # Floor
        "What is the floor rate or interest rate floor?",
        "What is the minimum interest rate?",  # NEW: Alternative phrasing
        # Pricing grid - FIX: Get tiered pricing
        "What is the pricing grid or applicable margins by tier?",
        "What are the pricing levels based on availability or usage?",  # NEW: Tiered pricing
        "What is the Applicable Margin for each Pricing Level?",  # NEW: Level-specific
        "What spread applies at each tier or level?",  # NEW: Tier extraction
    ],
    "facilityTerms": [
        # Total Facility
        "What is the Total Credit Facility amount?",
        "What is the Aggregate Commitment amount?",
        # Revolving
        "What is the Total Revolving Credit Amount?",
        "What is the Maximum Revolving Credit Amount?",
        "What is the Aggregate Maximum Revolving Credit Amount?",  # NEW: Exact term
        "What is the Revolving Commitment?",
        "What is the Aggregate Elected Revolving Credit Commitment?",  # NEW: Elected amount
        # LC - FIX: Better LC sublimit extraction
        "What is the Letter of Credit Sublimit?",  # NEW: Specific sublimit
        "What is the LC Commitment?",  # NEW: Separate query
        "What is the maximum amount for Letters of Credit?",  # NEW: Alternative phrasing
        # Swingline
        "What is the Swingline Sublimit?",  # NEW: Specific sublimit
        "What is the Swingline Commitment?",  # NEW: Separate query
        # Term Loan - FIX: Better term loan extraction
        "What is the Term Loan Commitment?",
        "What is the Term Facility amount?",
        "What is the Term Loan A Commitment amount?",  # NEW: With "amount" suffix
        "What dollar amount is the Term Loan A Commitment?",  # NEW: Explicit dollar amount
        "What is the Term Loan B Commitment?",
        "What is the Term Loan Bond Redemption Commitment?",  # NEW: Bond redemption facility
        "What is the Term Loan Bond Redemption amount?",  # NEW: Alternative
        # Delayed Draw
        "What is the Delayed Draw Term Loan or DDTL Commitment?",
        # Incremental
        "What is the Incremental Facility or Accordion amount?",
        # Maturity - FIX: Get maturity for each facility type
        "When does the facility mature?",  # 92% confidence - CRITICAL
        "What is the Maturity Date?",  # 86% confidence
        "What is the Revolving Credit Maturity Date?",  # NEW: Facility-specific
        "What is the Term Loan Maturity Date?",  # NEW: Facility-specific
        "What is the Term Loan A Maturity Date?",  # NEW: Specific term loan
        "What is the Term Loan Bond Redemption Maturity Date?",  # NEW: Bond redemption
        # Schedule
        "What amounts are shown in Schedule 1.01?",
        "What amounts are shown in Schedule 2.01?",  # NEW: Common schedule number
    ],
    "lenderCommitments": [
        # Lender identification - HIGH PERFORMERS
        "Who are the Lenders?",  # 99% confidence
        "What is each Lender's name?",  # 100% confidence
        "List all Lender names",  # 100% confidence
        "Who are the Banks?",  # 97% confidence
        # Lead Arranger - NEW: Critical party
        "Who is the Lead Arranger?",  # NEW: Lead arranger extraction
        "Who are the Joint Lead Arrangers?",  # NEW: Multiple arrangers
        "Who is the Bookrunner?",  # NEW: Related party
        # Swingline Lender - NEW: Critical party
        "Who is the Swingline Lender?",  # NEW: Swingline lender
        # L/C Issuer - NEW: Critical party
        "Who is the L/C Issuer?",  # NEW: LC issuer
        "Who is the Issuing Bank?",  # NEW: Alternative name
        "Who is the Letter of Credit Issuer?",  # NEW: Full name
        # Percentage
        "What is each Lender's Applicable Percentage?",  # 91% confidence
        "What percentage commitment does each Lender have?",  # NEW: Alternative
        # Commitment amounts - HIGH PERFORMERS
        "What is each Lender's Revolving Credit Commitment?",  # 97% confidence
        "What is each Lender's Revolving Commitment amount?",  # 93% confidence
        "What dollar amount is each Lender's Revolving Commitment?",  # NEW: Explicit
        "What is each Lender's Term Loan Commitment?",  # 99% confidence
        "What is each Lender's Term Commitment?",  # 96% confidence
        "What dollar amount is each Lender's Term Loan Commitment?",  # NEW: Explicit
        "What is each Lender's Term Loan A Commitment?",  # NEW: Specific term loan
        "What is each Lender's Term Loan Bond Redemption Commitment?",  # NEW: Bond
        # Aggregates - HIGH PERFORMERS
        "What is the Aggregate Revolving Commitment?",  # 95% confidence
        "What is the total commitment amount?",  # 90% confidence
        # Schedule
        "What commitments are shown in Schedule 1.01?",
        "What commitments are shown in Schedule 2.01?",  # NEW: Common schedule
        "What is in the Schedule of Lenders and Commitments?",  # 99% confidence
    ],
    "covenants": [
        # Fixed Charge Coverage
        "What is the Fixed Charge Coverage Ratio (FCCR) requirement?",
        # Leverage
        "What is the maximum Leverage Ratio?",
        "What is the Debt to EBITDA requirement?",
        "What is the Total Net Leverage Ratio?",
        "What is the Consolidated Leverage Ratio?",
        # Interest Coverage
        "What is the Interest Coverage Ratio requirement?",
        # Liquidity
        "What is the minimum Liquidity requirement?",
        "What is the minimum Cash requirement?",
        # General covenants
        "What are the financial maintenance covenants?",
        "What are the affirmative covenants?",
        "What are the negative covenants?",
        # Testing
        "What is the testing period for covenants?",
    ],
    "fees": [
        # Commitment Fee
        "What is the Commitment Fee?",
        "What is the Unused Fee or Facility Fee?",
        # LC Fee
        "What is the Letter of Credit Fee?",
        "What is the LC Participation Fee?",
        # Fronting Fee
        "What is the Fronting Fee or Issuing Bank Fee?",
        # Agency Fee
        "What is the Agency Fee or Administrative Agent Fee?",
        # Upfront Fees
        "What is the Upfront Fee or Closing Fee?",
        "What are the arrangement fees?",
        # Other fees
        "What is the Prepayment Penalty?",
        "What is the Late Charge fee?",
        "What is the Default Interest rate?",
    ],
    "definitions": [
        # Rate definitions
        "What is the definition of Applicable Rate?",
        "What is the definition of Applicable Margin?",
        "What is the definition of Base Rate?",
        # EBITDA
        "What is the definition of EBITDA?",
        "What is the definition of Adjusted EBITDA?",
        "What adjustments are made to EBITDA?",
        # Borrowing Base
        "What is the definition of Borrowing Base?",
        "How is Borrowing Base calculated?",
        # Maturity Date - HIGH PERFORMER
        "What is the definition of Maturity Date?",
        "What date is the Maturity Date?",  # 86% confidence
        # Guarantors
        "Who are the Guarantors?",
        "Who are the Credit Parties?",
        # Business Day
        "What is the definition of Business Day?",
        # Interest Period
        "What is the definition of Interest Payment Date?",
        "What is the definition of Interest Period?",
        # Lead Arranger
        "Who is the Lead Arranger or Joint Lead Arranger?",
        # Unused Commitment - HIGH PERFORMER
        "What is the definition of Unused Revolving Credit Commitment?",
        "How is unused commitment determined?",  # 94% confidence
        # LC definitions
        "What is the definition of Letter of Credit?",
        "What is the LC Expiration Date?",
        # Commitment Fee
        "What is the definition of Commitment Fee?",
        # Material Adverse Effect
        "What is the definition of Material Adverse Effect?",
    ],
}


def render_pdf_to_image(pdf_bytes: bytes, dpi: int = None) -> bytes:
    """Render PDF page(s) to a PNG image using PyMuPDF.

    Textract works more reliably with images than with PyPDF-manipulated PDFs.
    This function converts the PDF to a high-resolution PNG image.

    Args:
        pdf_bytes: Raw bytes of the PDF document (typically a single page)
        dpi: Resolution for rendering (default IMAGE_DPI, typically 150 for speed)

    Returns:
        PNG image bytes suitable for Textract AnalyzeDocument

    Raises:
        RuntimeError: If PyMuPDF is not available
    """
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF not available for image rendering")

    # Use configurable DPI for speed/quality balance
    if dpi is None:
        dpi = IMAGE_DPI

    # Open PDF from bytes
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    try:
        # For multi-page PDFs, we'll render each page and stack them vertically
        # But typically we're working with single-page extracts
        if len(pdf_doc) == 1:
            # Single page - render directly
            page = pdf_doc[0]
            # Use a matrix for the specified DPI (72 is default PDF DPI)
            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            return pix.tobytes("png")
        else:
            # Multiple pages - render each and return as separate images
            # For now, render first page (most extraction is single-page)
            page = pdf_doc[0]
            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            return pix.tobytes("png")
    finally:
        pdf_doc.close()


def render_pdf_pages_to_images(pdf_bytes: bytes, dpi: int = None) -> List[bytes]:
    """Render all pages of a PDF to individual PNG images.

    Args:
        pdf_bytes: Raw bytes of the PDF document
        dpi: Resolution for rendering (default IMAGE_DPI for speed)

    Returns:
        List of PNG image bytes, one per page
    """
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF not available for image rendering")

    # Use configurable DPI for speed/quality balance
    if dpi is None:
        dpi = IMAGE_DPI

    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []

    try:
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        for page in pdf_doc:
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))

        return images
    finally:
        pdf_doc.close()


def extract_single_page(pdf_stream: io.BytesIO, page_number: int) -> bytes:
    """Extract a single page from a PDF as a new PDF document.

    Args:
        pdf_stream: BytesIO stream containing the full PDF
        page_number: 1-indexed page number to extract

    Returns:
        Bytes of the single-page PDF
    """
    reader = PdfReader(pdf_stream)
    writer = PdfWriter()

    # Convert to 0-indexed
    page_index = page_number - 1

    if page_index < 0 or page_index >= len(reader.pages):
        raise ValueError(f"Page {page_number} out of range (document has {len(reader.pages)} pages)")

    writer.add_page(reader.pages[page_index])

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return output.read()


def extract_multiple_pages(pdf_stream: io.BytesIO, page_numbers: List[int]) -> bytes:
    """Extract multiple pages from a PDF as a new PDF document.

    Args:
        pdf_stream: BytesIO stream containing the full PDF
        page_numbers: List of 1-indexed page numbers to extract

    Returns:
        Bytes of the multi-page PDF
    """
    reader = PdfReader(pdf_stream)
    writer = PdfWriter()
    total_pages = len(reader.pages)

    for page_number in sorted(set(page_numbers)):  # Dedupe and sort
        page_index = page_number - 1
        if 0 <= page_index < total_pages:
            writer.add_page(reader.pages[page_index])
        else:
            print(f"Warning: Page {page_number} out of range (document has {total_pages} pages)")

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return output.read()


def upload_temp_section(bucket: str, document_id: str, section_name: str, page_bytes: bytes) -> str:
    """Upload extracted section pages to S3 for Textract processing.

    Args:
        bucket: S3 bucket name
        document_id: Unique document identifier
        section_name: Name of the Credit Agreement section
        page_bytes: PDF bytes of the section pages

    Returns:
        S3 key of the uploaded section
    """
    key = f"temp/{document_id}/section_{section_name}.pdf"

    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=page_bytes,
        ContentType='application/pdf'
    )

    return key


# =============================================================================
# Parallel Processing Helper Functions
# =============================================================================

def _process_single_page_queries(
    args: Tuple[int, bytes, str, List[str]]
) -> Tuple[int, Dict[str, Any]]:
    """Process queries for a single page (used by parallel executor).

    Args:
        args: Tuple of (page_index, image_bytes, bucket, queries)

    Returns:
        Tuple of (page_index, query_results)
    """
    page_idx, image_bytes, bucket, queries = args
    try:
        results = extract_with_queries(bucket, "", queries, image_bytes=image_bytes)
        return (page_idx, results)
    except Exception as e:
        print(f"Error processing page {page_idx + 1} queries: {str(e)}")
        return (page_idx, {"error": str(e)})


def _process_single_page_tables(
    args: Tuple[int, bytes, str]
) -> Tuple[int, Dict[str, Any]]:
    """Process table extraction for a single page (used by parallel executor).

    Args:
        args: Tuple of (page_index, image_bytes, bucket)

    Returns:
        Tuple of (page_index, table_results)
    """
    page_idx, image_bytes, bucket = args
    try:
        results = extract_tables(bucket, "", image_bytes=image_bytes)
        return (page_idx, results)
    except Exception as e:
        print(f"Error processing page {page_idx + 1} tables: {str(e)}")
        return (page_idx, {"error": str(e), "tables": [], "tableCount": 0})


def _process_single_page_signatures(
    args: Tuple[int, bytes, str]
) -> Tuple[int, Dict[str, Any]]:
    """Process signature detection for a single page (used by parallel executor).

    Args:
        args: Tuple of (page_index, image_bytes, bucket)

    Returns:
        Tuple of (page_index, signature_results)
    """
    page_idx, image_bytes, bucket = args
    try:
        results = extract_signatures(bucket, "", image_bytes=image_bytes)
        return (page_idx, results)
    except Exception as e:
        print(f"Error processing page {page_idx + 1} signatures: {str(e)}")
        return (page_idx, {"error": str(e), "signatures": [], "signatureCount": 0})


def process_pages_queries_parallel(
    page_images: List[bytes],
    queries: List[str],
    bucket: str,
) -> Dict[str, Any]:
    """Process query extraction for multiple pages in parallel.

    Uses ThreadPoolExecutor to run Textract query API calls concurrently.
    Merges results, keeping highest confidence answer for each query.

    Args:
        page_images: List of PNG image bytes, one per page
        queries: List of natural language queries to run
        bucket: S3 bucket name (for API signature, not used with image bytes)

    Returns:
        Merged query results with source page tracking
    """
    all_query_results = {}
    pages_processed = 0
    pages_failed = 0

    # Prepare arguments for parallel processing
    task_args = [(idx, img, bucket, queries) for idx, img in enumerate(page_images)]

    print(f"  Starting parallel query processing for {len(page_images)} pages with {MAX_PARALLEL_WORKERS} workers...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
        futures = {executor.submit(_process_single_page_queries, args): args[0] for args in task_args}

        for future in as_completed(futures):
            page_idx = futures[future]
            try:
                result_page_idx, page_results = future.result()

                if page_results.get("error"):
                    print(f"  Page {result_page_idx + 1}: queries failed - {page_results.get('error')}")
                    pages_failed += 1
                    continue

                pages_processed += 1

                # Merge results - keep highest confidence answer for each query
                for query_text, answer_data in page_results.items():
                    if query_text in ["error", "errorMessage", "queries", "fallbackUsed", "_extractionMetadata"]:
                        continue
                    if isinstance(answer_data, dict) and answer_data.get("answer"):
                        existing = all_query_results.get(query_text)
                        if not existing or answer_data.get("confidence", 0) > existing.get("confidence", 0):
                            all_query_results[query_text] = answer_data.copy()
                            all_query_results[query_text]["sourcePage"] = result_page_idx + 1

            except Exception as e:
                print(f"  Page {page_idx + 1}: future error - {str(e)}")
                pages_failed += 1

    elapsed = time.time() - start_time
    print(f"  Parallel query processing completed in {elapsed:.2f}s ({pages_processed} succeeded, {pages_failed} failed)")

    return all_query_results


def process_pages_tables_parallel(
    page_images: List[bytes],
    bucket: str,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Process table extraction for multiple pages in parallel.

    Uses ThreadPoolExecutor to run Textract table API calls concurrently.

    Args:
        page_images: List of PNG image bytes, one per page
        bucket: S3 bucket name (for API signature, not used with image bytes)

    Returns:
        Tuple of (all_tables list, any_failed boolean)
    """
    all_tables = []
    pages_processed = 0
    pages_failed = 0

    # Prepare arguments for parallel processing
    task_args = [(idx, img, bucket) for idx, img in enumerate(page_images)]

    print(f"  Starting parallel table processing for {len(page_images)} pages with {MAX_PARALLEL_WORKERS} workers...")
    start_time = time.time()

    # Collect results with page indices for proper ordering
    results_by_page = {}

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
        futures = {executor.submit(_process_single_page_tables, args): args[0] for args in task_args}

        for future in as_completed(futures):
            page_idx = futures[future]
            try:
                result_page_idx, page_results = future.result()

                if page_results.get("error"):
                    print(f"  Page {result_page_idx + 1}: tables failed - {page_results.get('error')}")
                    pages_failed += 1
                    continue

                pages_processed += 1

                # Store tables with page index for later ordering
                page_tables = page_results.get("tables", [])
                for table in page_tables:
                    table["sourcePage"] = result_page_idx + 1
                results_by_page[result_page_idx] = page_tables

            except Exception as e:
                print(f"  Page {page_idx + 1}: future error - {str(e)}")
                pages_failed += 1

    # Combine tables in page order
    for page_idx in sorted(results_by_page.keys()):
        all_tables.extend(results_by_page[page_idx])

    elapsed = time.time() - start_time
    print(f"  Parallel table processing completed in {elapsed:.2f}s ({pages_processed} succeeded, {pages_failed} failed)")

    return all_tables, (pages_failed > 0 and pages_processed == 0)


def process_pages_signatures_parallel(
    page_images: List[bytes],
    bucket: str,
) -> List[Dict[str, Any]]:
    """Process signature detection for multiple pages in parallel.

    Uses ThreadPoolExecutor to run Textract signature API calls concurrently.

    Args:
        page_images: List of PNG image bytes, one per page
        bucket: S3 bucket name (for API signature, not used with image bytes)

    Returns:
        List of all detected signatures with source page tracking
    """
    all_signatures = []
    pages_processed = 0
    pages_failed = 0

    # Prepare arguments for parallel processing
    task_args = [(idx, img, bucket) for idx, img in enumerate(page_images)]

    print(f"  Starting parallel signature processing for {len(page_images)} pages with {MAX_PARALLEL_WORKERS} workers...")
    start_time = time.time()

    # Collect results with page indices for proper ordering
    results_by_page = {}

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
        futures = {executor.submit(_process_single_page_signatures, args): args[0] for args in task_args}

        for future in as_completed(futures):
            page_idx = futures[future]
            try:
                result_page_idx, page_results = future.result()

                if page_results.get("error"):
                    print(f"  Page {result_page_idx + 1}: signatures failed - {page_results.get('error')}")
                    pages_failed += 1
                    continue

                pages_processed += 1

                # Store signatures with page index for later ordering
                page_sigs = page_results.get("signatures", [])
                for sig in page_sigs:
                    sig["sourcePage"] = result_page_idx + 1
                results_by_page[result_page_idx] = page_sigs

            except Exception as e:
                print(f"  Page {page_idx + 1}: future error - {str(e)}")
                pages_failed += 1

    # Combine signatures in page order
    for page_idx in sorted(results_by_page.keys()):
        all_signatures.extend(results_by_page[page_idx])

    elapsed = time.time() - start_time
    print(f"  Parallel signature processing completed in {elapsed:.2f}s ({pages_processed} succeeded, {pages_failed} failed)")

    return all_signatures


def extract_credit_agreement_section(
    bucket: str,
    key: str,
    document_id: str,
    section_name: str,
    page_numbers: List[int],
    pdf_stream: io.BytesIO,
) -> Dict[str, Any]:
    """Extract a specific section from a Credit Agreement document.

    Uses PyPDF to extract ONLY the specified pages, then renders to images
    for Textract processing. Image-based extraction is more reliable than
    PyPDF-manipulated PDFs which Textract often rejects.

    Args:
        bucket: S3 bucket name
        key: Original document S3 key
        document_id: Unique document identifier
        section_name: Name of the section to extract
        page_numbers: List of page numbers for this section
        pdf_stream: BytesIO stream of the full PDF

    Returns:
        Dict with section extraction results
    """
    if not page_numbers:
        return {
            "section": section_name,
            "status": "SKIPPED",
            "reason": "No pages identified for this section",
            "results": None,
        }

    print(f"Extracting Credit Agreement section '{section_name}' from pages {page_numbers}")

    # Start timing for performance measurement
    section_start_time = time.time()

    # Get queries for this section
    queries = CREDIT_AGREEMENT_QUERIES.get(section_name, [])

    # Extract the section pages using PyPDF
    pdf_stream.seek(0)  # Reset stream position
    section_bytes = extract_multiple_pages(pdf_stream, page_numbers)

    results = {}
    textract_failed = False
    fallback_text = None
    page_images = []
    temp_key = None

    try:
        # Try to render PDF pages to images for more reliable Textract processing
        if PYMUPDF_AVAILABLE:
            try:
                print(f"Rendering section '{section_name}' to images for Textract...")
                # Render ALL PDF pages to images for multi-page processing
                page_images = render_pdf_pages_to_images(section_bytes)
                print(f"Rendered {len(page_images)} page(s) to images for '{section_name}'")
                results["extractionMethod"] = "image_rendering"
                results["pagesProcessed"] = len(page_images)
            except Exception as render_error:
                print(f"Image rendering failed for '{section_name}': {render_error}")
                page_images = []

        # If image rendering failed or unavailable, fall back to S3 upload
        if not page_images:
            print(f"Falling back to S3 upload for section '{section_name}'")
            temp_key = upload_temp_section(bucket, document_id, section_name, section_bytes)
            print(f"Uploaded section '{section_name}' ({len(page_numbers)} pages) to s3://{bucket}/{temp_key}")

        # Run queries extraction on ALL pages if we have queries (PARALLEL PROCESSING)
        if queries:
            print(f"Running {len(queries)} queries for section '{section_name}' across {len(page_images) if page_images else 1} page(s)")

            if page_images and len(page_images) > 1:
                # PARALLEL: Process all pages concurrently using ThreadPoolExecutor
                all_query_results = process_pages_queries_parallel(page_images, queries, bucket)
                results["queries"] = all_query_results
                if not all_query_results:
                    textract_failed = True
                    print(f"Textract queries failed for all pages in '{section_name}'")
            elif page_images:
                # Single page - no need for parallelism overhead
                page_query_results = extract_with_queries(bucket, "", queries, image_bytes=page_images[0])
                if page_query_results.get("error"):
                    textract_failed = True
                    print(f"Textract queries failed for '{section_name}': {page_query_results.get('error')}")
                results["queries"] = page_query_results
            else:
                # Fall back to S3 path (single document)
                query_results = extract_with_queries(bucket, temp_key, queries)
                results["queries"] = query_results
                if query_results.get("error"):
                    textract_failed = True
                    print(f"Textract queries failed for '{section_name}': {query_results.get('error')}")

        # For lender commitments, extract tables from ALL pages (PARALLEL PROCESSING)
        if section_name == "lenderCommitments":
            print(f"Running table extraction for '{section_name}' across {len(page_images) if page_images else 1} page(s)")

            if page_images and len(page_images) > 1:
                # PARALLEL: Process all pages concurrently
                all_tables, all_failed = process_pages_tables_parallel(page_images, bucket)
                results["tables"] = {"tables": all_tables, "tableCount": len(all_tables)}
                if all_failed:
                    textract_failed = True
                    print(f"Textract tables failed for all pages in '{section_name}'")
            elif page_images:
                # Single page - no parallelism overhead
                page_table_results = extract_tables(bucket, "", image_bytes=page_images[0])
                if page_table_results.get("error"):
                    textract_failed = True
                    print(f"Textract tables failed for '{section_name}': {page_table_results.get('error')}")
                results["tables"] = page_table_results
            else:
                table_results = extract_tables(bucket, temp_key)
                results["tables"] = table_results
                if table_results.get("error"):
                    textract_failed = True
                    print(f"Textract tables failed for '{section_name}': {table_results.get('error')}")

        # For applicable rates, extract tables (pricing grids) from ALL pages (PARALLEL PROCESSING)
        if section_name == "applicableRates":
            print(f"Running table extraction for '{section_name}' (pricing grid) across {len(page_images) if page_images else 1} page(s)")

            if page_images and len(page_images) > 1:
                # PARALLEL: Process all pages concurrently
                all_tables, all_failed = process_pages_tables_parallel(page_images, bucket)
                results["tables"] = {"tables": all_tables, "tableCount": len(all_tables)}
                if all_failed:
                    textract_failed = True
                    print(f"Textract tables failed for all pages in '{section_name}'")
            elif page_images:
                # Single page - no parallelism overhead
                page_table_results = extract_tables(bucket, "", image_bytes=page_images[0])
                if page_table_results.get("error"):
                    textract_failed = True
                    print(f"Textract tables failed for '{section_name}': {page_table_results.get('error')}")
                results["tables"] = page_table_results
            else:
                table_results = extract_tables(bucket, temp_key)
                results["tables"] = table_results
                if table_results.get("error"):
                    textract_failed = True
                    print(f"Textract tables failed for '{section_name}': {table_results.get('error')}")

        # For facility terms, extract tables (commitment amounts, sublimits) from ALL pages (PARALLEL PROCESSING)
        if section_name == "facilityTerms":
            print(f"Running table extraction for '{section_name}' (facility commitments) across {len(page_images) if page_images else 1} page(s)")

            if page_images and len(page_images) > 1:
                # PARALLEL: Process all pages concurrently
                all_tables, _ = process_pages_tables_parallel(page_images, bucket)
                results["tables"] = {"tables": all_tables, "tableCount": len(all_tables)}
            elif page_images:
                # Single page - no parallelism overhead
                page_table_results = extract_tables(bucket, "", image_bytes=page_images[0])
                if page_table_results.get("error"):
                    print(f"Textract tables failed for '{section_name}': {page_table_results.get('error')}")
                results["tables"] = page_table_results
            else:
                table_results = extract_tables(bucket, temp_key)
                results["tables"] = table_results
                if table_results.get("error"):
                    print(f"Textract tables failed for '{section_name}': {table_results.get('error')}")

        # For fees section, extract tables from ALL pages (PARALLEL PROCESSING)
        if section_name == "fees":
            print(f"Running table extraction for '{section_name}' across {len(page_images) if page_images else 1} page(s)")

            if page_images and len(page_images) > 1:
                # PARALLEL: Process all pages concurrently
                all_tables, _ = process_pages_tables_parallel(page_images, bucket)
                results["tables"] = {"tables": all_tables, "tableCount": len(all_tables)}
            elif page_images:
                # Single page - no parallelism overhead
                page_table_results = extract_tables(bucket, "", image_bytes=page_images[0])
                if page_table_results.get("error"):
                    print(f"Textract tables failed for '{section_name}': {page_table_results.get('error')}")
                results["tables"] = page_table_results
            else:
                table_results = extract_tables(bucket, temp_key)
                results["tables"] = table_results
                if table_results.get("error"):
                    print(f"Textract tables failed for '{section_name}': {table_results.get('error')}")

        # For agreementInfo section, also detect signatures (critical for legal docs) (PARALLEL PROCESSING)
        if section_name == "agreementInfo":
            print(f"Running signature detection for '{section_name}' across {len(page_images) if page_images else 1} page(s)")

            if page_images and len(page_images) > 1:
                # PARALLEL: Process all pages concurrently
                all_signatures = process_pages_signatures_parallel(page_images, bucket)
                results["signatures"] = {
                    "signatures": all_signatures,
                    "signatureCount": len(all_signatures),
                    "hasSignatures": len(all_signatures) > 0,
                }
                print(f"Found {len(all_signatures)} signature(s) in agreementInfo section")
            elif page_images:
                # Single page - no parallelism overhead
                page_sig_results = extract_signatures(bucket, "", image_bytes=page_images[0])
                if page_sig_results.get("error"):
                    print(f"Signature detection failed for '{section_name}': {page_sig_results.get('error')}")
                results["signatures"] = page_sig_results
                print(f"Found {page_sig_results.get('signatureCount', 0)} signature(s) in agreementInfo section")
            else:
                sig_results = extract_signatures(bucket, temp_key)
                results["signatures"] = sig_results
                if sig_results.get("signatureCount", 0) > 0:
                    print(f"Found {sig_results['signatureCount']} signature(s) in agreementInfo section")
                else:
                    print(f"No signatures detected in agreementInfo section")

        # If Textract failed, use PyPDF text extraction as fallback
        if textract_failed:
            print(f"Textract failed for '{section_name}', using PyPDF text extraction fallback")
            pdf_stream.seek(0)  # Reset stream position
            fallback_text = extract_text_from_pages(pdf_stream, page_numbers)
            if fallback_text:
                results["rawText"] = fallback_text
                results["extractionMethod"] = "pypdf_fallback"
                print(f"PyPDF extracted {len(fallback_text)} characters for '{section_name}'")
            else:
                print(f"PyPDF fallback also produced no text for '{section_name}'")

        # Clean up temp file if we created one
        if temp_key:
            try:
                s3_client.delete_object(Bucket=bucket, Key=temp_key)
                print(f"Cleaned up temp file for section '{section_name}'")
            except Exception as cleanup_error:
                print(f"Warning: Failed to clean up temp file: {cleanup_error}")

        # Calculate processing time
        processing_time = time.time() - section_start_time
        print(f"Section '{section_name}' completed in {processing_time:.2f}s (parallel processing with {MAX_PARALLEL_WORKERS} workers)")

        return {
            "creditAgreementSection": section_name,
            "status": "EXTRACTED" if not textract_failed else "PARTIAL_EXTRACTION",
            "pageNumbers": page_numbers,
            "pageCount": len(page_numbers),
            "pagesProcessed": len(page_images) if page_images else 1,
            "results": results,
            "textractFailed": textract_failed,
            "fallbackUsed": textract_failed and bool(fallback_text),
            "usedImageRendering": len(page_images) > 0,
            "processingTimeSeconds": round(processing_time, 2),
            "parallelWorkersUsed": MAX_PARALLEL_WORKERS,
        }

    except Exception as e:
        print(f"Error extracting section '{section_name}': {str(e)}")
        # Try PyPDF fallback even on exception
        try:
            pdf_stream.seek(0)
            fallback_text = extract_text_from_pages(pdf_stream, page_numbers)
            if fallback_text:
                print(f"PyPDF fallback recovered {len(fallback_text)} chars after error")
                results["rawText"] = fallback_text
                results["extractionMethod"] = "pypdf_fallback_after_error"
        except Exception as fallback_error:
            print(f"PyPDF fallback also failed: {str(fallback_error)}")

        # Try to clean up temp file if we created one
        if temp_key:
            try:
                s3_client.delete_object(Bucket=bucket, Key=temp_key)
            except Exception:
                pass

        # Calculate processing time even for exceptions
        processing_time = time.time() - section_start_time
        print(f"Section '{section_name}' failed after {processing_time:.2f}s")

        # Return partial results instead of raising
        return {
            "creditAgreementSection": section_name,
            "status": "PARTIAL_EXTRACTION" if fallback_text else "FAILED",
            "pageNumbers": page_numbers,
            "pageCount": len(page_numbers),
            "results": results if results else None,
            "error": str(e),
            "textractFailed": True,
            "fallbackUsed": bool(fallback_text),
            "processingTimeSeconds": round(processing_time, 2),
        }


def upload_temp_page(bucket: str, document_id: str, page_number: int, page_bytes: bytes) -> str:
    """Upload extracted page to S3 for Textract processing.
    
    Args:
        bucket: S3 bucket name
        document_id: Unique document identifier
        page_number: Page number being uploaded
        page_bytes: PDF bytes of the single page
        
    Returns:
        S3 key of the uploaded page
    """
    key = f"temp/{document_id}/page_{page_number}.pdf"
    
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=page_bytes,
        ContentType='application/pdf'
    )
    
    return key


def extract_text_from_pages(pdf_stream: io.BytesIO, page_numbers: List[int]) -> str:
    """Extract text from specific pages of a PDF using PyPDF.

    Args:
        pdf_stream: BytesIO stream containing the PDF
        page_numbers: List of 1-indexed page numbers to extract text from

    Returns:
        Extracted text content from specified pages
    """
    try:
        # Reset stream position
        pdf_stream.seek(0)
        reader = PdfReader(pdf_stream)
        total_pages = len(reader.pages)
        text_parts = []

        for page_num in sorted(set(page_numbers)):
            page_index = page_num - 1  # Convert to 0-indexed
            if 0 <= page_index < total_pages:
                page_text = reader.pages[page_index].extract_text()
                if page_text:
                    text_parts.append(f"--- Page {page_num} ---\n{page_text}")
            else:
                print(f"Warning: Page {page_num} out of range (document has {total_pages} pages)")

        return "\n\n".join(text_parts)
    except Exception as e:
        print(f"PyPDF text extraction failed: {str(e)}")
        return ""


def extract_raw_text_ocr(
    bucket: str,
    key: str,
    image_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Use Textract DetectDocumentText for raw OCR extraction.

    This is the HYBRID APPROACH for scanned documents:
    - Textract handles the OCR (visual text extraction)
    - Claude LLM handles the intelligent data extraction

    Args:
        bucket: S3 bucket name
        key: S3 key of the document
        image_bytes: Optional image bytes for direct inline extraction (preferred)

    Returns:
        Dict with raw text, lines, and confidence metadata
    """
    try:
        # Prefer image bytes if available (more reliable than PyPDF mini-PDFs)
        if image_bytes:
            response = textract_client.detect_document_text(
                Document={'Bytes': image_bytes}
            )
        else:
            response = textract_client.detect_document_text(
                Document={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                }
            )

        # Extract text from blocks
        lines = []
        words = []
        total_confidence = 0
        confidence_count = 0

        for block in response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                text = block.get('Text', '')
                confidence = block.get('Confidence', 0)
                lines.append({
                    'text': text,
                    'confidence': confidence,
                })
                total_confidence += confidence
                confidence_count += 1
            elif block['BlockType'] == 'WORD':
                words.append({
                    'text': block.get('Text', ''),
                    'confidence': block.get('Confidence', 0),
                })

        # Combine lines into full text
        full_text = '\n'.join([line['text'] for line in lines])
        avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 0

        return {
            'rawText': full_text,
            'lineCount': len(lines),
            'wordCount': len(words),
            'averageConfidence': avg_confidence,
            'lines': lines,
            '_extractionMetadata': {
                'method': 'textract_detect_document_text',
                'totalLines': len(lines),
                'totalWords': len(words),
                'avgConfidence': avg_confidence,
            }
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        print(f"Textract DetectDocumentText error ({error_code}): {error_msg}")
        return {"error": error_code, "errorMessage": error_msg, "rawText": "", "lineCount": 0}
    except Exception as e:
        print(f"Textract OCR extraction error: {str(e)}")
        return {"error": str(e), "rawText": "", "lineCount": 0}


def extract_raw_text_ocr_parallel(
    page_images: List[bytes],
    bucket: str,
) -> str:
    """Extract raw OCR text from multiple pages in parallel.

    Uses ThreadPoolExecutor to run Textract DetectDocumentText calls concurrently.
    Combines all page text into a single document.

    Args:
        page_images: List of PNG image bytes, one per page
        bucket: S3 bucket name (for API signature, not used with image bytes)

    Returns:
        Combined raw text from all pages
    """
    all_page_texts = {}
    pages_processed = 0
    pages_failed = 0

    def process_single_page(args):
        page_idx, image_bytes = args
        try:
            result = extract_raw_text_ocr(bucket, "", image_bytes=image_bytes)
            return (page_idx, result)
        except Exception as e:
            print(f"Error processing page {page_idx + 1} OCR: {str(e)}")
            return (page_idx, {"error": str(e), "rawText": ""})

    # Prepare arguments for parallel processing
    task_args = [(idx, img) for idx, img in enumerate(page_images)]

    print(f"  Starting parallel OCR processing for {len(page_images)} pages with {MAX_PARALLEL_WORKERS} workers...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
        futures = {executor.submit(process_single_page, args): args[0] for args in task_args}

        for future in as_completed(futures):
            page_idx = futures[future]
            try:
                result_page_idx, page_result = future.result()

                if page_result.get("error"):
                    print(f"  Page {result_page_idx + 1}: OCR failed - {page_result.get('error')}")
                    pages_failed += 1
                    continue

                pages_processed += 1
                raw_text = page_result.get('rawText', '')
                if raw_text:
                    all_page_texts[result_page_idx] = f"--- PAGE {result_page_idx + 1} ---\n{raw_text}"

            except Exception as e:
                print(f"  Page {page_idx + 1}: future error - {str(e)}")
                pages_failed += 1

    # Combine all pages in order
    combined_text = ""
    for page_idx in sorted(all_page_texts.keys()):
        combined_text += all_page_texts[page_idx] + "\n\n"

    elapsed = time.time() - start_time
    print(f"  Parallel OCR processing completed in {elapsed:.2f}s ({pages_processed} succeeded, {pages_failed} failed)")

    return combined_text.strip()


def extract_with_queries(
    bucket: str,
    key: str,
    queries: List[str],
    image_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Use Textract AnalyzeDocument with Queries feature.

    Handles Textract's 15-query limit by batching queries and merging results.

    Args:
        bucket: S3 bucket name
        key: S3 key of the document
        queries: List of natural language queries
        image_bytes: Optional image bytes for direct inline extraction (preferred)

    Returns:
        Dict with query results including confidence categorization
    """
    # Textract has a 15-query limit per API call
    # Split queries into batches and merge results
    TEXTRACT_QUERY_LIMIT = 15
    all_responses_blocks = []

    query_batches = [queries[i:i + TEXTRACT_QUERY_LIMIT] for i in range(0, len(queries), TEXTRACT_QUERY_LIMIT)]
    print(f"Split {len(queries)} queries into {len(query_batches)} batches of max {TEXTRACT_QUERY_LIMIT}")

    for batch_idx, query_batch in enumerate(query_batches):
        try:
            print(f"Processing query batch {batch_idx + 1}/{len(query_batches)} ({len(query_batch)} queries)")
            # Prefer image bytes if available (more reliable than PyPDF mini-PDFs)
            if image_bytes:
                response = textract_client.analyze_document(
                    Document={'Bytes': image_bytes},
                    FeatureTypes=['QUERIES'],
                    QueriesConfig={
                        'Queries': [{'Text': q} for q in query_batch]
                    }
                )
            else:
                response = textract_client.analyze_document(
                    Document={
                        'S3Object': {
                            'Bucket': bucket,
                            'Name': key
                        }
                    },
                    FeatureTypes=['QUERIES'],
                    QueriesConfig={
                        'Queries': [{'Text': q} for q in query_batch]
                    }
                )
            # Collect blocks from all batches
            all_responses_blocks.extend(response.get('Blocks', []))
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            print(f"Textract ClientError for query batch {batch_idx + 1} ({error_code}): {error_msg}")
            # Continue with other batches even if one fails
            continue
        except Exception as e:
            print(f"Textract query extraction error for batch {batch_idx + 1}: {str(e)}")
            continue

    # Check if we got any results
    if not all_responses_blocks:
        print(f"All query batches failed, no results")
        return {"error": "All query batches failed", "queries": queries, "fallbackUsed": True}

    # Parse query results with confidence categorization
    results = {}
    low_confidence_results = []
    unanswered_queries = []

    # Track which queries got answers
    answered_queries = set()

    for block in all_responses_blocks:
        if block['BlockType'] == 'QUERY':
            query_text = block.get('Query', {}).get('Text', '')
            # Find the corresponding answer
            has_answer = False
            for relationship in block.get('Relationships', []):
                if relationship['Type'] == 'ANSWER':
                    answer_ids = relationship['Ids']
                    for answer_id in answer_ids:
                        answer_block = next(
                            (b for b in all_responses_blocks if b['Id'] == answer_id),
                            None
                        )
                        if answer_block:
                            has_answer = True
                            answered_queries.add(query_text)
                            confidence = answer_block.get('Confidence', 0)
                            answer_text = answer_block.get('Text', '')

                            result_data = {
                                'answer': answer_text,
                                'confidence': confidence,
                                'geometry': answer_block.get('Geometry', {}),
                                'meetsThreshold': confidence >= CONFIDENCE_THRESHOLD,
                            }

                            if confidence >= CONFIDENCE_THRESHOLD:
                                results[query_text] = result_data
                            else:
                                # Still include low-confidence results but flag them
                                results[query_text] = result_data
                                low_confidence_results.append({
                                    'query': query_text,
                                    'answer': answer_text,
                                    'confidence': confidence,
                                    'threshold': CONFIDENCE_THRESHOLD,
                                    'reason': f'Below {CONFIDENCE_THRESHOLD}% confidence threshold'
                                })
                                print(f"Low confidence ({confidence:.1f}%) for query: {query_text}")

            if not has_answer:
                unanswered_queries.append({
                    'query': query_text,
                    'reason': 'no_answer_found'
                })

    # Track queries that weren't even found in response
    for query in queries:
        if query not in answered_queries and not any(uq['query'] == query for uq in unanswered_queries):
            unanswered_queries.append({
                'query': query,
                'reason': 'query_not_processed'
            })

    # Add metadata about extraction quality
    results['_extractionMetadata'] = {
        'totalQueries': len(queries),
        'answeredQueries': len(answered_queries),
        'highConfidenceCount': len([r for r in results.values() if isinstance(r, dict) and r.get('meetsThreshold', False)]),
        'lowConfidenceCount': len(low_confidence_results),
        'unansweredCount': len(unanswered_queries),
        'confidenceThreshold': CONFIDENCE_THRESHOLD,
        'lowConfidenceResults': low_confidence_results,
        'unansweredQueries': unanswered_queries,
    }

    return results


def extract_tables(
    bucket: str,
    key: str,
    image_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Use Textract AnalyzeDocument with Tables feature.

    Args:
        bucket: S3 bucket name
        key: S3 key of the document
        image_bytes: Optional image bytes for direct inline extraction (preferred)

    Returns:
        Dict with table extraction results including confidence metadata
    """
    try:
        # Prefer image bytes if available (more reliable than PyPDF mini-PDFs)
        if image_bytes:
            response = textract_client.analyze_document(
                Document={'Bytes': image_bytes},
                FeatureTypes=['TABLES']
            )
        else:
            response = textract_client.analyze_document(
                Document={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                },
                FeatureTypes=['TABLES']
            )
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        print(f"Textract ClientError for tables ({error_code}): {error_msg}")
        return {"error": error_code, "errorMessage": error_msg, "tables": [], "tableCount": 0, "fallbackUsed": True}
    except Exception as e:
        print(f"Textract table extraction error: {str(e)}")
        return {"error": str(e), "tables": [], "tableCount": 0, "fallbackUsed": True}

    # Parse table results with confidence tracking
    tables = []
    low_confidence_cells = []

    # Build a map of block IDs to blocks
    blocks_map = {block['Id']: block for block in response.get('Blocks', [])}

    for block in response.get('Blocks', []):
        if block['BlockType'] == 'TABLE':
            table_confidence = block.get('Confidence', 0)
            table_data = {
                'rows': [],
                'confidence': table_confidence,
                'meetsThreshold': table_confidence >= CONFIDENCE_THRESHOLD,
            }

            if table_confidence < CONFIDENCE_THRESHOLD:
                print(f"Low confidence table ({table_confidence:.1f}%)")

            # Get cells
            cells = []
            for relationship in block.get('Relationships', []):
                if relationship['Type'] == 'CHILD':
                    for cell_id in relationship['Ids']:
                        cell_block = blocks_map.get(cell_id)
                        if cell_block and cell_block['BlockType'] == 'CELL':
                            # Get cell text
                            cell_text = ''
                            cell_confidence = cell_block.get('Confidence', 0)
                            for cell_rel in cell_block.get('Relationships', []):
                                if cell_rel['Type'] == 'CHILD':
                                    for word_id in cell_rel['Ids']:
                                        word_block = blocks_map.get(word_id)
                                        if word_block and word_block['BlockType'] == 'WORD':
                                            cell_text += word_block.get('Text', '') + ' '

                            cell_data = {
                                'row': cell_block.get('RowIndex', 0),
                                'col': cell_block.get('ColumnIndex', 0),
                                'text': cell_text.strip(),
                                'confidence': cell_confidence
                            }
                            cells.append(cell_data)

                            # Track low confidence cells
                            if cell_confidence < CONFIDENCE_THRESHOLD and cell_text.strip():
                                low_confidence_cells.append({
                                    'row': cell_data['row'],
                                    'col': cell_data['col'],
                                    'text': cell_text.strip(),
                                    'confidence': cell_confidence,
                                    'tableIndex': len(tables)
                                })

            # Organize cells into rows
            if cells:
                max_row = max(c['row'] for c in cells)
                max_col = max(c['col'] for c in cells)

                for row_idx in range(1, max_row + 1):
                    row_data = []
                    for col_idx in range(1, max_col + 1):
                        cell = next(
                            (c for c in cells if c['row'] == row_idx and c['col'] == col_idx),
                            None
                        )
                        row_data.append(cell['text'] if cell else '')
                    table_data['rows'].append(row_data)

            tables.append(table_data)

    # Add extraction metadata
    high_confidence_tables = len([t for t in tables if t.get('meetsThreshold', False)])

    return {
        'tables': tables,
        'tableCount': len(tables),
        '_extractionMetadata': {
            'totalTables': len(tables),
            'highConfidenceTables': high_confidence_tables,
            'lowConfidenceTables': len(tables) - high_confidence_tables,
            'lowConfidenceCellCount': len(low_confidence_cells),
            'confidenceThreshold': CONFIDENCE_THRESHOLD,
            'lowConfidenceCells': low_confidence_cells[:10],  # Limit to first 10 for brevity
        }
    }


def extract_signatures(
    bucket: str,
    key: str,
    image_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Use Textract AnalyzeDocument with SIGNATURES feature.

    Detects signature locations in documents - critical for legal document verification.
    This helps identify if a document has been signed and where signatures appear.

    Args:
        bucket: S3 bucket name
        key: S3 key of the document
        image_bytes: Optional image bytes for direct inline extraction (preferred)

    Returns:
        Dict with signature detection results including locations and confidence
    """
    try:
        # Prefer image bytes if available (more reliable than PyPDF mini-PDFs)
        if image_bytes:
            response = textract_client.analyze_document(
                Document={'Bytes': image_bytes},
                FeatureTypes=['SIGNATURES']
            )
        else:
            response = textract_client.analyze_document(
                Document={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                },
                FeatureTypes=['SIGNATURES']
            )
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        print(f"Textract ClientError for signatures ({error_code}): {error_msg}")
        return {"error": error_code, "errorMessage": error_msg, "signatures": [], "signatureCount": 0}
    except Exception as e:
        print(f"Textract signature extraction error: {str(e)}")
        return {"error": str(e), "signatures": [], "signatureCount": 0}

    # Parse signature blocks
    signatures = []
    low_confidence_signatures = []

    for block in response.get('Blocks', []):
        if block['BlockType'] == 'SIGNATURE':
            confidence = block.get('Confidence', 0)
            geometry = block.get('Geometry', {})

            signature_data = {
                'confidence': confidence,
                'meetsThreshold': confidence >= CONFIDENCE_THRESHOLD,
                'geometry': geometry,
                'boundingBox': geometry.get('BoundingBox', {}),
            }
            signatures.append(signature_data)

            if confidence < CONFIDENCE_THRESHOLD:
                low_confidence_signatures.append({
                    'confidence': confidence,
                    'threshold': CONFIDENCE_THRESHOLD,
                    'boundingBox': geometry.get('BoundingBox', {}),
                })
                print(f"Low confidence signature detected ({confidence:.1f}%)")

    high_confidence_count = len([s for s in signatures if s.get('meetsThreshold', False)])

    return {
        'signatures': signatures,
        'signatureCount': len(signatures),
        'hasSignatures': len(signatures) > 0,
        '_extractionMetadata': {
            'totalSignatures': len(signatures),
            'highConfidenceSignatures': high_confidence_count,
            'lowConfidenceSignatures': len(low_confidence_signatures),
            'confidenceThreshold': CONFIDENCE_THRESHOLD,
            'lowConfidenceSignaturesList': low_confidence_signatures,
        }
    }


def extract_forms(
    bucket: str,
    key: str,
    image_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Use Textract AnalyzeDocument with Forms feature.

    Args:
        bucket: S3 bucket name
        key: S3 key of the document
        image_bytes: Optional image bytes for direct inline extraction (preferred)

    Returns:
        Dict with form key-value extraction results including confidence metadata
    """
    try:
        # Prefer image bytes if available (more reliable than PyPDF mini-PDFs)
        if image_bytes:
            response = textract_client.analyze_document(
                Document={'Bytes': image_bytes},
                FeatureTypes=['FORMS']
            )
        else:
            response = textract_client.analyze_document(
                Document={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                },
                FeatureTypes=['FORMS']
            )
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        print(f"Textract ClientError for forms ({error_code}): {error_msg}")
        return {"error": error_code, "errorMessage": error_msg, "keyValues": {}, "fieldCount": 0, "fallbackUsed": True}
    except Exception as e:
        print(f"Textract form extraction error: {str(e)}")
        return {"error": str(e), "keyValues": {}, "fieldCount": 0, "fallbackUsed": True}

    # Build blocks map
    blocks_map = {block['Id']: block for block in response.get('Blocks', [])}

    # Extract key-value pairs with confidence tracking
    key_values = {}
    low_confidence_fields = []

    for block in response.get('Blocks', []):
        if block['BlockType'] == 'KEY_VALUE_SET' and 'KEY' in block.get('EntityTypes', []):
            key_confidence = block.get('Confidence', 0)

            # Get key text
            key_text = ''
            for rel in block.get('Relationships', []):
                if rel['Type'] == 'CHILD':
                    for child_id in rel['Ids']:
                        child_block = blocks_map.get(child_id)
                        if child_block and child_block['BlockType'] == 'WORD':
                            key_text += child_block.get('Text', '') + ' '

            # Get value
            value_text = ''
            value_confidence = 0
            for rel in block.get('Relationships', []):
                if rel['Type'] == 'VALUE':
                    for value_id in rel['Ids']:
                        value_block = blocks_map.get(value_id)
                        if value_block:
                            value_confidence = value_block.get('Confidence', 0)
                            for value_rel in value_block.get('Relationships', []):
                                if value_rel['Type'] == 'CHILD':
                                    for word_id in value_rel['Ids']:
                                        word_block = blocks_map.get(word_id)
                                        if word_block and word_block['BlockType'] == 'WORD':
                                            value_text += word_block.get('Text', '') + ' '

            if key_text.strip():
                # Use the lower of key and value confidence
                overall_confidence = min(key_confidence, value_confidence) if value_confidence > 0 else key_confidence
                meets_threshold = overall_confidence >= CONFIDENCE_THRESHOLD

                key_values[key_text.strip()] = {
                    'value': value_text.strip(),
                    'confidence': overall_confidence,
                    'keyConfidence': key_confidence,
                    'valueConfidence': value_confidence,
                    'meetsThreshold': meets_threshold,
                }

                if not meets_threshold and value_text.strip():
                    low_confidence_fields.append({
                        'key': key_text.strip(),
                        'value': value_text.strip(),
                        'confidence': overall_confidence,
                        'threshold': CONFIDENCE_THRESHOLD,
                    })
                    print(f"Low confidence form field ({overall_confidence:.1f}%): {key_text.strip()}")

    # Count high confidence fields
    high_confidence_count = len([kv for kv in key_values.values() if kv.get('meetsThreshold', False)])

    return {
        'keyValues': key_values,
        'fieldCount': len(key_values),
        '_extractionMetadata': {
            'totalFields': len(key_values),
            'highConfidenceFields': high_confidence_count,
            'lowConfidenceFields': len(low_confidence_fields),
            'confidenceThreshold': CONFIDENCE_THRESHOLD,
            'lowConfidenceFieldsList': low_confidence_fields[:10],  # Limit to first 10
        }
    }


def extract_loan_agreement_multi_page(
    bucket: str,
    key: str,
    document_id: str,
    start_page: int,
    queries: List[str],
    extraction_type: str,
    content_hash: Optional[str],
    file_size: Optional[int],
    uploaded_at: Optional[str],
    target_pages: Optional[List[int]] = None,
    router_token_usage: Optional[Dict[str, int]] = None,
    low_quality_pages: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Extract data from multiple pages of a Loan Agreement using HYBRID approach.

    HYBRID EXTRACTION STRATEGY:
    1. First try PyPDF text extraction (fast, free, works for native PDFs)
    2. If minimal text (scanned document), use Textract OCR for raw text
    3. If router identified low-quality pages (garbled text from font encoding),
       use Textract OCR specifically for those pages
    4. Pass raw text to normalizer where Claude LLM will extract structured data

    This approach works for BOTH native text PDFs AND scanned/image-based PDFs,
    AND handles PDFs with mixed quality (some pages readable, some garbled).
    The Claude LLM in the normalizer uses detailed extraction prompts to find:
    - Loan amount, interest rate, maturity date
    - Parties, payment terms, fees
    - Covenants, collateral, prepayment terms

    Args:
        bucket: S3 bucket name
        key: S3 key of the document
        document_id: Unique document identifier
        start_page: Starting page number (usually 1) - fallback if target_pages not provided
        queries: List of natural language queries (used as fallback for native PDFs)
        extraction_type: QUERIES, TABLES, or QUERIES_AND_TABLES
        content_hash: Document content hash for pass-through
        file_size: Document size for pass-through
        uploaded_at: Upload timestamp for pass-through
        target_pages: Optional list of specific pages to extract (from router section identification)
        low_quality_pages: Optional list of pages with garbled text that need Textract OCR

    Returns:
        Dict with extraction results including raw text for LLM processing
    """
    # Configuration
    LOAN_AGREEMENT_FALLBACK_MAX_PAGES = 15  # Fallback if router doesn't provide sections
    MIN_TEXT_CHARS_FOR_NATIVE = 500  # Threshold to detect scanned vs native PDF

    print(f"Starting Loan Agreement HYBRID extraction for {document_id}")
    start_time = time.time()

    try:
        # 1. Download full PDF
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_stream = io.BytesIO(s3_response['Body'].read())

        # 2. Determine total pages and pages to extract
        reader = PdfReader(pdf_stream)
        total_pages = len(reader.pages)

        # Use router-provided target pages if available, otherwise fall back to page range
        if target_pages:
            # Use intelligent page selection from router
            pages_to_extract = sorted([p for p in target_pages if 1 <= p <= total_pages])
            if pages_to_extract:
                # end_page is used later for signature detection to check if we need additional pages
                end_page = max(pages_to_extract)
                print(f"Using router-provided target pages: {pages_to_extract}")
            else:
                # All target pages were out of range - fall back to default extraction
                print(f"Warning: All target pages {target_pages} out of range for {total_pages}-page document")
                end_page = min(start_page + LOAN_AGREEMENT_FALLBACK_MAX_PAGES - 1, total_pages)
                pages_to_extract = list(range(start_page, end_page + 1))
                print(f"Falling back to pages {start_page}-{end_page}")
        else:
            # Fallback: extract pages starting from start_page
            end_page = min(start_page + LOAN_AGREEMENT_FALLBACK_MAX_PAGES - 1, total_pages)
            pages_to_extract = list(range(start_page, end_page + 1))
            print(f"No target pages from router - using fallback: pages {start_page}-{end_page}")

        print(f"Loan Agreement: {total_pages} total pages, extracting pages {pages_to_extract}")

        # 3. IDENTIFY PAGES THAT NEED TEXTRACT OCR
        # Low-quality pages have garbled text from font encoding issues
        # These need Textract OCR even if other pages are readable via PyPDF
        low_quality_pages_to_ocr = []
        if low_quality_pages:
            # Filter to only pages we're actually extracting
            low_quality_pages_to_ocr = [p for p in low_quality_pages if p in pages_to_extract]
            if low_quality_pages_to_ocr:
                print(f"Router identified {len(low_quality_pages_to_ocr)} low-quality pages needing OCR: {low_quality_pages_to_ocr}")

        # Separate pages into readable (PyPDF) and low-quality (Textract OCR)
        readable_pages = [p for p in pages_to_extract if p not in low_quality_pages_to_ocr]
        print(f"Page breakdown: {len(readable_pages)} readable (PyPDF), {len(low_quality_pages_to_ocr)} low-quality (Textract OCR)")

        # 4. EXTRACT TEXT FROM READABLE PAGES USING PYPDF (fast, free)
        pypdf_text = ""
        if readable_pages:
            print(f"Attempting PyPDF text extraction for readable pages {readable_pages}...")
            pdf_stream.seek(0)
            pypdf_text = extract_text_from_pages(pdf_stream, readable_pages)
            pypdf_text_length = len(pypdf_text.strip())
            print(f"PyPDF extracted {pypdf_text_length} characters from readable pages")
        else:
            pypdf_text_length = 0
            print("No readable pages - will rely entirely on Textract OCR")

        # 5. DETERMINE IF WE NEED TEXTRACT OCR
        # Use Textract OCR if: (a) scanned document OR (b) has low-quality pages
        is_scanned_document = pypdf_text_length < MIN_TEXT_CHARS_FOR_NATIVE and not low_quality_pages_to_ocr
        needs_ocr_for_low_quality = len(low_quality_pages_to_ocr) > 0

        results = {}
        extraction_method = "pypdf"
        ocr_text = ""
        page_images = []  # Initialize for signature detection later

        if is_scanned_document:
            # FULLY SCANNED DOCUMENT: Use Textract OCR for all pages
            print(f"Document appears to be scanned (only {pypdf_text_length} chars from PyPDF)")
            print("Switching to Textract OCR for raw text extraction...")
            extraction_method = "textract_ocr"

            # Extract pages as a multi-page PDF for rendering
            pdf_stream.seek(0)
            section_bytes = extract_multiple_pages(pdf_stream, pages_to_extract)

            # Render pages to images for Textract
            page_images = []
            if PYMUPDF_AVAILABLE:
                try:
                    print(f"Rendering {len(pages_to_extract)} pages to images for OCR...")
                    page_images = render_pdf_pages_to_images(section_bytes)
                    print(f"Rendered {len(page_images)} page images")
                except Exception as render_error:
                    print(f"Image rendering failed: {render_error}")
                    page_images = []

            if page_images:
                # Use parallel Textract OCR
                print(f"Running Textract OCR on {len(page_images)} pages...")
                ocr_text = extract_raw_text_ocr_parallel(page_images, bucket)
                ocr_text_length = len(ocr_text.strip())
                print(f"Textract OCR extracted {ocr_text_length} characters")

                results['rawText'] = ocr_text
                results['extractionMethod'] = 'textract_ocr'
                results['ocrTextLength'] = ocr_text_length

                # Also try table extraction for payment schedules
                if extraction_type in ['TABLES', 'QUERIES_AND_TABLES']:
                    print(f"Running table extraction across {len(page_images)} pages...")
                    all_tables, _ = process_pages_tables_parallel(page_images, bucket)
                    results['tables'] = {'tables': all_tables, 'tableCount': len(all_tables)}
                    print(f"Table extraction complete: {len(all_tables)} tables found")

            else:
                # Fallback if image rendering fails
                print("Image rendering failed, using PyPDF text as fallback")
                results['rawText'] = pypdf_text
                results['extractionMethod'] = 'pypdf_fallback'
                extraction_method = "pypdf_fallback"

        elif needs_ocr_for_low_quality:
            # MIXED QUALITY DOCUMENT: PyPDF for readable pages, Textract OCR for low-quality pages
            print(f"Mixed quality document: using PyPDF for {len(readable_pages)} pages, Textract OCR for {len(low_quality_pages_to_ocr)} pages")
            extraction_method = "hybrid_pypdf_ocr"

            # Extract low-quality pages for Textract OCR
            pdf_stream.seek(0)
            low_quality_section_bytes = extract_multiple_pages(pdf_stream, low_quality_pages_to_ocr)

            # Render low-quality pages to images for Textract
            low_quality_images = []
            if PYMUPDF_AVAILABLE:
                try:
                    print(f"Rendering {len(low_quality_pages_to_ocr)} low-quality pages to images for OCR...")
                    low_quality_images = render_pdf_pages_to_images(low_quality_section_bytes)
                    print(f"Rendered {len(low_quality_images)} low-quality page images")
                except Exception as render_error:
                    print(f"Image rendering failed for low-quality pages: {render_error}")
                    low_quality_images = []

            if low_quality_images:
                # Use parallel Textract OCR for low-quality pages
                print(f"Running Textract OCR on {len(low_quality_images)} low-quality pages...")
                ocr_text = extract_raw_text_ocr_parallel(low_quality_images, bucket)
                ocr_text_length = len(ocr_text.strip())
                print(f"Textract OCR extracted {ocr_text_length} characters from low-quality pages")

                # COMBINE PyPDF text (readable pages) + OCR text (low-quality pages)
                # Add clear separation so normalizer can see all content
                combined_text = ""
                if pypdf_text.strip():
                    combined_text += f"=== TEXT FROM READABLE PAGES (PyPDF) ===\n{pypdf_text.strip()}\n\n"
                if ocr_text.strip():
                    combined_text += f"=== TEXT FROM OCR PAGES (Textract) ===\n{ocr_text.strip()}"

                results['rawText'] = combined_text.strip()
                results['extractionMethod'] = 'hybrid_pypdf_ocr'
                results['pypdfTextLength'] = pypdf_text_length
                results['ocrTextLength'] = ocr_text_length
                results['readablePages'] = readable_pages
                results['ocrPages'] = low_quality_pages_to_ocr

                # Set page_images for signature detection (use low-quality images we already rendered)
                page_images = low_quality_images

                print(f"Combined text: {len(combined_text)} total chars ({pypdf_text_length} PyPDF + {ocr_text_length} OCR)")

                # Also try table extraction for payment schedules (on low-quality pages)
                if extraction_type in ['TABLES', 'QUERIES_AND_TABLES']:
                    print(f"Running table extraction across {len(low_quality_images)} OCR pages...")
                    all_tables, _ = process_pages_tables_parallel(low_quality_images, bucket)
                    results['tables'] = {'tables': all_tables, 'tableCount': len(all_tables)}
                    print(f"Table extraction complete: {len(all_tables)} tables found")

            else:
                # Fallback if image rendering fails - use PyPDF text only
                print("Image rendering failed for low-quality pages, using PyPDF text only")
                results['rawText'] = pypdf_text
                results['extractionMethod'] = 'pypdf_partial'
                extraction_method = "pypdf_partial"

        else:
            # NATIVE TEXT PDF: Use PyPDF text
            print(f"Document is native text PDF ({pypdf_text_length} chars)")
            results['rawText'] = pypdf_text
            results['extractionMethod'] = 'pypdf'

            # For native PDFs, also try Textract queries as supplemental extraction
            # This provides structured answers that can validate LLM extraction
            pdf_stream.seek(0)
            section_bytes = extract_multiple_pages(pdf_stream, pages_to_extract)

            page_images = []
            if PYMUPDF_AVAILABLE:
                try:
                    page_images = render_pdf_pages_to_images(section_bytes)
                except Exception:
                    pass

            if page_images and queries and extraction_type in ['QUERIES', 'QUERIES_AND_TABLES']:
                print(f"Running supplemental Textract queries ({len(queries)} queries)...")
                if len(page_images) > 1:
                    all_query_results = process_pages_queries_parallel(page_images, queries, bucket)
                else:
                    all_query_results = extract_with_queries(bucket, "", queries, image_bytes=page_images[0])

                query_metadata = all_query_results.pop('_extractionMetadata', {}) if all_query_results else {}
                results['queries'] = all_query_results
                results['_queryMetadata'] = query_metadata

                answered_count = len([k for k in all_query_results.keys() if not k.startswith('_') and not k.startswith('error')])
                print(f"Supplemental query extraction: {answered_count} queries answered")

            # Also try table extraction
            if page_images and extraction_type in ['TABLES', 'QUERIES_AND_TABLES']:
                print(f"Running table extraction...")
                if len(page_images) > 1:
                    all_tables, _ = process_pages_tables_parallel(page_images, bucket)
                    results['tables'] = {'tables': all_tables, 'tableCount': len(all_tables)}
                else:
                    table_results = extract_tables(bucket, "", image_bytes=page_images[0])
                    results['tables'] = table_results

        # Ensure tables key exists
        if 'tables' not in results:
            results['tables'] = {'tables': [], 'tableCount': 0}

        # 5. SIGNATURE DETECTION (critical for legal document validation)
        # Loan Agreements require signature validation for legal enforceability
        # IMPORTANT: Signatures are often on the LAST pages, so we must check those too
        signatures_result = {'signatures': [], 'signatureCount': 0, 'hasSignatures': False}

        # Collect all page images for signature detection
        # Include both content pages AND last pages (where signatures typically appear)
        signature_page_images = list(page_images) if page_images else []
        signature_page_numbers = list(pages_to_extract)

        # Check if we need to render additional LAST pages for signature detection
        SIGNATURE_LAST_PAGES = 3  # Check last 3 pages for signatures
        last_pages_to_check = []
        if total_pages > end_page:
            # There are pages beyond our content extraction range
            last_page_start = max(end_page + 1, total_pages - SIGNATURE_LAST_PAGES + 1)
            last_pages_to_check = list(range(last_page_start, total_pages + 1))
            print(f"Document has {total_pages} pages, adding last pages {last_pages_to_check} for signature detection")

            if PYMUPDF_AVAILABLE:
                try:
                    # Extract and render the last pages for signature detection
                    pdf_stream.seek(0)
                    last_section_bytes = extract_multiple_pages(pdf_stream, last_pages_to_check)
                    last_page_images = render_pdf_pages_to_images(last_section_bytes)

                    if last_page_images:
                        # Add to signature detection pages
                        signature_page_images.extend(last_page_images)
                        signature_page_numbers.extend(last_pages_to_check)
                        print(f"Rendered {len(last_page_images)} additional last page(s) for signature detection")
                except Exception as last_page_error:
                    print(f"Warning: Could not render last pages for signature detection: {last_page_error}")

        if signature_page_images:
            print(f"Running signature detection across {len(signature_page_images)} page(s) (pages {signature_page_numbers})...")
            try:
                if len(signature_page_images) > 1:
                    all_signatures = process_pages_signatures_parallel(signature_page_images, bucket)

                    # Remap page numbers: process_pages_signatures_parallel uses image indices (1-based)
                    # but our images might be from non-contiguous pages (e.g., 1-10 AND 13-15)
                    # So sourcePage=1 -> signature_page_numbers[0], sourcePage=2 -> signature_page_numbers[1], etc.
                    for sig in all_signatures:
                        img_idx = sig.get('sourcePage', 1) - 1  # Convert 1-based to 0-based index
                        if 0 <= img_idx < len(signature_page_numbers):
                            sig['sourcePage'] = signature_page_numbers[img_idx]

                    signatures_result = {
                        'signatures': all_signatures,
                        'signatureCount': len(all_signatures),
                        'hasSignatures': len(all_signatures) > 0,
                    }
                else:
                    sig_results = extract_signatures(bucket, "", image_bytes=signature_page_images[0])
                    if not sig_results.get('error'):
                        # Add source page number
                        for sig in sig_results.get('signatures', []):
                            sig['sourcePage'] = signature_page_numbers[0] if signature_page_numbers else 1
                        signatures_result = sig_results
                print(f"Signature detection: found {signatures_result.get('signatureCount', 0)} signature(s)")
            except Exception as sig_error:
                print(f"Signature detection failed: {sig_error}")

        results['signatures'] = signatures_result

        # Build combined metadata
        results['_extractionMetadata'] = {
            'queries': results.pop('_queryMetadata', {}),
            'tables': results['tables'].get('_extractionMetadata', {}),
            'signatures': signatures_result.get('_extractionMetadata', {}),
            'extractionMethod': extraction_method,
            'isScannedDocument': is_scanned_document,
            'pypdfTextLength': pypdf_text_length,
        }

        # 6. Calculate processing time
        processing_time = time.time() - start_time
        print(f"Loan Agreement HYBRID extraction completed in {processing_time:.2f}s (method: {extraction_method})")

        # 7. CRITICAL: Truncate rawText to prevent Step Functions DataLimitExceeded error
        # Step Functions has 256KB payload limit; with many pages, rawText can exceed this
        raw_text = results.get('rawText', '')
        original_raw_text_length = len(raw_text)
        if original_raw_text_length > MAX_RAW_TEXT_CHARS:
            truncated_chars = original_raw_text_length - MAX_RAW_TEXT_CHARS
            results['rawText'] = raw_text[:MAX_RAW_TEXT_CHARS] + f"\n\n... [TRUNCATED: {truncated_chars} chars omitted to fit Step Functions payload limit]"
            print(f"WARNING: Truncated rawText from {original_raw_text_length} to {MAX_RAW_TEXT_CHARS} chars (-{truncated_chars})")
            results['rawTextTruncated'] = True
            results['originalRawTextLength'] = original_raw_text_length
        else:
            results['rawTextTruncated'] = False

        return {
            'documentId': document_id,
            'contentHash': content_hash,
            'size': file_size,
            'key': key,
            'uploadedAt': uploaded_at,
            'extractionType': extraction_type,
            'pageNumber': start_page,
            'pagesProcessed': len(pages_to_extract),
            'pageRange': pages_to_extract,
            'status': 'EXTRACTED',
            'results': results,
            'usedImageRendering': PYMUPDF_AVAILABLE,
            'isLoanAgreement': True,
            'isScannedDocument': is_scanned_document,
            'extractionMethod': extraction_method,
            'processingTimeSeconds': round(processing_time, 2),
            'routerTokenUsage': router_token_usage,  # Pass through for cost calculation
            'metadata': {
                'sourceKey': key,
                'sourcePage': start_page,
                'totalPagesInDocument': total_pages,
                'pagesExtracted': len(pages_to_extract),
                'extractionApproach': 'hybrid_ocr_llm' if is_scanned_document else 'native_text_llm',
            },
        }

    except Exception as e:
        print(f"Error in Loan Agreement HYBRID extraction: {str(e)}")
        raise


def lambda_handler(event, context):
    """Main Lambda handler for targeted document extraction.

    Supports two modes:
    1. Single-page extraction (mortgage docs): pageNumber + extractionType + queries
    2. Credit Agreement section extraction: creditAgreementSection + sectionPages

    Args:
        event: Input event containing documentId, bucket, key, and extraction parameters
        context: Lambda context

    Returns:
        Dict with extraction results
    """
    print(f"Extractor Lambda received event: {json.dumps(event)}")

    # Extract common parameters
    document_id = event['documentId']
    bucket = event.get('bucket', BUCKET_NAME)
    key = event['key']

    # ============================================================
    # MODE 0: Plugin-driven section extraction (Phase 4 Map state)
    # ============================================================
    section_config = event.get('sectionConfig')
    if section_config:
        print(f"Plugin-driven section extraction: {section_config.get('sectionId', 'unknown')}")
        result = extract_section_generic(
            bucket=bucket, key=key, document_id=document_id,
            section_config=section_config,
        )
        # Pass through metadata
        result['documentId'] = document_id
        result['contentHash'] = event.get('contentHash')
        result['size'] = event.get('size')
        result['key'] = key
        result['routerTokenUsage'] = event.get('routerTokenUsage')
        return result

    # Pass through metadata for downstream processing
    content_hash = event.get('contentHash')
    file_size = event.get('size')

    # CRITICAL: Pass through REAL router token usage for accurate cost calculation
    router_token_usage = event.get('routerTokenUsage')

    # Check if this is Credit Agreement section extraction
    credit_agreement_section = event.get('creditAgreementSection')
    section_pages = event.get('sectionPages', [])

    if credit_agreement_section:
        # Credit Agreement section extraction mode
        print(f"Credit Agreement section extraction: {credit_agreement_section}")

        if not section_pages:
            print(f"No pages for section '{credit_agreement_section}'")
            return {
                'documentId': document_id,
                'contentHash': content_hash,
                'size': file_size,
                'key': key,
                'creditAgreementSection': credit_agreement_section,
                'status': 'SKIPPED',
                'reason': f"No pages identified for section '{credit_agreement_section}'",
                'results': None,
                'routerTokenUsage': router_token_usage,  # Pass through for cost calculation
            }

        try:
            # Download full PDF
            s3_response = s3_client.get_object(Bucket=bucket, Key=key)
            pdf_stream = io.BytesIO(s3_response['Body'].read())

            # Extract the section
            result = extract_credit_agreement_section(
                bucket=bucket,
                key=key,
                document_id=document_id,
                section_name=credit_agreement_section,
                page_numbers=section_pages,
                pdf_stream=pdf_stream,
            )

            # Add pass-through metadata
            result['documentId'] = document_id
            result['contentHash'] = content_hash
            result['size'] = file_size
            result['key'] = key
            result['routerTokenUsage'] = router_token_usage  # Pass through for cost calculation
            result['metadata'] = {
                'sourceKey': key,
                'sectionName': credit_agreement_section,
                'sourcePages': section_pages,
            }

            return result

        except Exception as e:
            print(f"Error in Credit Agreement section extraction: {str(e)}")
            raise

    # Single-page extraction mode (existing behavior for mortgage docs)
    page_number = event.get('pageNumber')
    extraction_type = event.get('extractionType', 'QUERIES')
    queries = event.get('queries', [])
    is_loan_agreement = event.get('isLoanAgreement', False)  # Marker for loan agreement docs
    uploaded_at = event.get('uploadedAt')

    # Handle null page number (document type not found)
    if page_number is None:
        print(f"Page number is null - document type not found in classification")
        return {
            'documentId': document_id,
            'contentHash': content_hash,
            'size': file_size,
            'key': key,
            'extractionType': extraction_type,
            'pageNumber': None,
            'status': 'SKIPPED',
            'reason': 'Document type not found in classification',
            'results': None,
            'routerTokenUsage': router_token_usage,  # Pass through for cost calculation
        }

    # LOAN AGREEMENT MULTI-PAGE EXTRACTION
    # Use router-provided section page ranges for intelligent extraction
    # Falls back to first N pages if router didn't provide sections
    if is_loan_agreement:
        print(f"Loan Agreement detected - using multi-page extraction mode")

        # Extract target pages from router-provided loanAgreementSections
        loan_agreement_sections = event.get('loanAgreementSections', {})
        sections = loan_agreement_sections.get('sections', {})

        target_pages = None
        if sections:
            # Collect all unique pages from all sections
            all_section_pages = set()
            for section_name, page_list in sections.items():
                if isinstance(page_list, list):
                    all_section_pages.update(page_list)
                    print(f"  Section '{section_name}': pages {page_list}")

            if all_section_pages:
                target_pages = sorted(list(all_section_pages))
                print(f"Loan Agreement: Router identified {len(target_pages)} target pages: {target_pages}")
        else:
            print("Loan Agreement: No sections from router - will use fallback page range")

        # Extract low-quality pages from router output (top-level field)
        # These pages have garbled text (font encoding issues) and need Textract OCR
        low_quality_pages = event.get('lowQualityPages', [])
        if low_quality_pages:
            print(f"Loan Agreement: Router identified {len(low_quality_pages)} low-quality pages needing OCR: {low_quality_pages}")

        return extract_loan_agreement_multi_page(
            bucket=bucket,
            key=key,
            document_id=document_id,
            start_page=page_number,
            queries=queries,
            extraction_type=extraction_type,
            content_hash=content_hash,
            file_size=file_size,
            uploaded_at=uploaded_at,
            target_pages=target_pages,
            router_token_usage=router_token_usage,  # Pass through for cost calculation
            low_quality_pages=low_quality_pages,  # Pages needing Textract OCR
        )

    print(f"Extracting page {page_number} from s3://{bucket}/{key} using {extraction_type}")

    try:
        # 1. Download full PDF
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_stream = io.BytesIO(s3_response['Body'].read())

        # 2. Extract the single page
        print(f"Extracting page {page_number}...")
        page_bytes = extract_single_page(pdf_stream, page_number)

        # 3. Try to render page to image for more reliable Textract processing
        image_bytes = None
        temp_key = None
        used_image_rendering = False

        if PYMUPDF_AVAILABLE:
            try:
                print(f"Rendering page {page_number} to image for Textract...")
                image_bytes = render_pdf_to_image(page_bytes)
                used_image_rendering = True
                print(f"Rendered page {page_number} to image ({len(image_bytes)} bytes)")
            except Exception as render_error:
                print(f"Image rendering failed: {render_error}. Falling back to S3 upload.")
                image_bytes = None

        # 4. If image rendering failed, fall back to S3 upload
        if not image_bytes:
            temp_key = upload_temp_page(bucket, document_id, page_number, page_bytes)
            print(f"Uploaded temp page to s3://{bucket}/{temp_key}")

        # 5. Run appropriate extraction
        results = None

        if extraction_type == 'QUERIES':
            if not queries:
                raise ValueError("QUERIES extraction requires a list of queries")
            print(f"Running Textract Queries: {queries}")
            if image_bytes:
                results = extract_with_queries(bucket, "", queries, image_bytes=image_bytes)
            else:
                results = extract_with_queries(bucket, temp_key, queries)

        elif extraction_type == 'TABLES':
            print("Running Textract Tables extraction...")
            if image_bytes:
                results = extract_tables(bucket, "", image_bytes=image_bytes)
            else:
                results = extract_tables(bucket, temp_key)

        elif extraction_type == 'FORMS':
            print("Running Textract Forms extraction...")
            if image_bytes:
                results = extract_forms(bucket, "", image_bytes=image_bytes)
            else:
                results = extract_forms(bucket, temp_key)

        elif extraction_type == 'QUERIES_AND_TABLES':
            # Combined extraction for documents that need both queries and tables
            # (e.g., Closing Disclosure which has structured tables AND specific fields)
            if not queries:
                raise ValueError("QUERIES_AND_TABLES extraction requires a list of queries")
            print(f"Running combined Textract Queries + Tables extraction...")

            # Run queries extraction
            if image_bytes:
                query_results = extract_with_queries(bucket, "", queries, image_bytes=image_bytes)
            else:
                query_results = extract_with_queries(bucket, temp_key, queries)

            # Run tables extraction
            if image_bytes:
                table_results = extract_tables(bucket, "", image_bytes=image_bytes)
            else:
                table_results = extract_tables(bucket, temp_key)

            # Combine results
            # Note: extract_with_queries returns a flat dict where keys are query texts
            # and values are {answer, confidence, ...} dicts, plus _extractionMetadata
            # extract_tables returns {'tables': [...], 'tableCount': N, ...}
            query_metadata = query_results.pop('_extractionMetadata', {}) if query_results else {}
            table_metadata = table_results.get('_extractionMetadata', {}) if table_results else {}

            results = {
                'queries': query_results if query_results else {},  # Dict of query_text -> result
                'tables': table_results if table_results else {'tables': [], 'tableCount': 0},
                '_extractionMetadata': {
                    'queries': query_metadata,
                    'tables': table_metadata,
                },
            }
            query_count = len([k for k in results['queries'].keys() if not k.startswith('_')])
            table_count = results['tables'].get('tableCount', 0)
            print(f"Combined extraction: {query_count} queries, {table_count} tables")

        else:
            raise ValueError(f"Unknown extraction type: {extraction_type}")

        # 6. SIGNATURE DETECTION (critical for legal document validation)
        # All financial documents (promissory notes, etc.) require signature validation
        signatures_result = {'signatures': [], 'signatureCount': 0, 'hasSignatures': False}
        print("Running signature detection for document validation...")
        try:
            if image_bytes:
                sig_results = extract_signatures(bucket, "", image_bytes=image_bytes)
            else:
                sig_results = extract_signatures(bucket, temp_key)

            if not sig_results.get('error'):
                signatures_result = sig_results
                print(f"Signature detection: found {signatures_result.get('signatureCount', 0)} signature(s)")
            else:
                print(f"Signature detection warning: {sig_results.get('error')}")
        except Exception as sig_error:
            print(f"Signature detection failed: {sig_error}")

        # Add signatures to results
        if results is None:
            results = {}
        results['signatures'] = signatures_result

        # 7. Clean up temp file if we created one
        if temp_key:
            s3_client.delete_object(Bucket=bucket, Key=temp_key)
            print("Cleaned up temp file")

        # 8. Return results
        return {
            'documentId': document_id,
            'contentHash': content_hash,
            'size': file_size,
            'key': key,
            'uploadedAt': uploaded_at,
            'extractionType': extraction_type,
            'pageNumber': page_number,
            'status': 'EXTRACTED',
            'results': results,
            'usedImageRendering': used_image_rendering,
            'isLoanAgreement': is_loan_agreement,  # Pass through marker for normalizer
            'routerTokenUsage': router_token_usage,  # Pass through for cost calculation
            'metadata': {
                'sourceKey': key,
                'sourcePage': page_number,
            },
        }

    except Exception as e:
        print(f"Error in Extractor Lambda: {str(e)}")
        raise
