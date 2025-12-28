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
# 5 workers provides ~5x speedup while staying within typical Textract rate limits
MAX_PARALLEL_WORKERS = int(os.environ.get('MAX_PARALLEL_WORKERS', '5'))

# Credit Agreement section-specific queries with synonyms for better extraction
# Based on loan_prompts_map.py terminology and legal document variations
# Legal documents use varied terminology, so we include alternative phrasings
CREDIT_AGREEMENT_QUERIES = {
    "agreementInfo": [
        # Document identification (from loan_prompts_map: instrument_type)
        "What is the document title or type?",
        "What type of agreement is this?",
        "What is the name of this credit facility?",
        "What is the Instrument Type?",
        "What is the Loan Type?",
        "What is the Product Type?",
        # Dates - multiple phrasings (from loan_prompts_map: loan_effective_date, maturity_date)
        "What is the agreement date?",
        "What is the effective date?",
        "What is the closing date?",
        "What is the date of this agreement?",
        "What is the Note Date?",
        "What is the Loan Date?",
        "What is the Origination Date?",
        # Maturity variations (from loan_prompts_map: maturity_date extraction_logic)
        "What is the Maturity Date?",
        "What is the Due Date?",
        "What is the Final Repayment date?",
        "What is the Expiry date?",
        "What is the Termination Date?",
        "When is the Last Installment due?",
        # Parties - Borrower variations
        "Who is the Borrower?",
        "Who is the Company?",
        "Who is the Credit Party?",
        "Who is the obligor?",
        "Who is the Primary Obligor?",
        # Agent variations
        "Who is the Administrative Agent?",
        "Who is the Agent?",
        "Who is the Collateral Agent?",
        # Amendment tracking
        "What is the amendment number if any?",
        "Is this an amendment and restatement?",
        "What is the restatement date?",
        # Currency (from loan_prompts_map: currency)
        "What is the currency of this loan?",
        "In what currency is the loan denominated?",
    ],
    "applicableRates": [
        # Rate/Margin variations (from loan_prompts_map: spread_rate, base_rate)
        "What is the Applicable Rate or Applicable Margin?",
        "What is the interest rate margin?",
        "What is the spread over the benchmark rate?",
        "What is the Spread Rate?",
        "What is the Margin?",
        "What is the Floating Rate Spread?",
        "What is the Loan Spread?",
        "How many basis points is the spread?",
        # Base Rate (from loan_prompts_map: base_rate)
        "What is the Base Rate?",
        "What is the Index Rate?",
        "What is the Reference Rate?",
        # SOFR variations (from loan_prompts_map: rate_index with SOFR codes)
        "What is the Term SOFR spread or margin?",
        "What is the SOFR margin?",
        "What is the Adjusted Term SOFR spread?",
        "What is the SOFR Rate?",
        "What is the 30 Day SOFR Average rate?",
        "What is the 90 Day SOFR Average rate?",
        "What is the Daily Simple SOFR spread?",
        "What is the CME Term SOFR rate?",
        # Rate Index identification (from loan_prompts_map: rate_index must_be list)
        "What is the Rate Index?",
        "What benchmark rate is used?",
        "What is the Reference Index?",
        "What is the Rate Index Name?",
        # Interest Rate Type (from loan_prompts_map: interest_rate_type)
        "Is this a Fixed or Variable rate loan?",
        "What is the Interest Rate Type?",
        "Is the rate SOFR-based, LIBOR-based, or Prime-based?",
        # ABR/Prime variations
        "What is the ABR spread?",
        "What is the Base Rate spread?",
        "What is the Prime Rate margin?",
        "What is the Alternate Base Rate margin?",
        "What is the Texas Capital Bank Prime rate?",
        # Day Count / Year Basis (from loan_prompts_map: year_basis)
        "What is the Year Basis or Day Count Convention?",
        "Is interest calculated on Actual/360 or Actual/365?",
        "What day count convention is used?",
        "How many days in a year for interest calculation?",
        # Fees within rates section
        "What is the commitment fee rate?",
        "What is the unused commitment fee?",
        "What is the LC fee rate?",
        "What is the letter of credit fee?",
        # Floor
        "What is the floor rate?",
        "What is the interest rate floor?",
        "What is the SOFR floor?",
        # Pricing tiers
        "What are the pricing levels or tiers?",
        "What is the pricing grid?",
        "What are the applicable margins by tier?",
        # Index Frequency (from loan_prompts_map: index_frequency)
        "How often does the rate adjust?",
        "What is the rate adjustment frequency?",
        "Is the rate adjusted Monthly, Quarterly, or Annually?",
    ],
    "facilityTerms": [
        # Credit Facility/Commitment Amount (primary focus - from loan_prompts_map)
        "What is the Total Credit Facility amount?",
        "What is the Credit Commitment amount?",
        "What is the Facility Amount?",
        "What is the Total Commitment Amount?",
        "What is the Aggregate Commitment?",
        # Revolving Credit - multiple phrasings
        "What is the Aggregate Maximum Revolving Credit Amount?",
        "What is the Total Revolving Credit Facility?",
        "What is the Maximum Credit Amount?",
        "What is the total revolving commitment?",
        "What is the Revolving Loan amount?",
        "What is the Revolving Credit Facility amount?",
        # Elected Commitment
        "What is the Aggregate Elected Revolving Credit Commitment?",
        "What is the Initial Revolving Credit Commitment?",
        "What is the Revolving Credit Commitment amount?",
        "What is the Initial Commitment?",
        # LC variations
        "What is the LC Commitment?",
        "What is the Letter of Credit Sublimit?",
        "What is the LC Facility amount?",
        "What is the maximum letter of credit amount?",
        "What is the LC Subfacility?",
        # Swingline
        "What is the Swingline Sublimit?",
        "What is the Swingline Commitment?",
        "What is the Swing Line Sublimit?",
        "What is the Swingline Subfacility?",
        # Term Loan variations
        "What is the Term Loan Commitment?",
        "What is the Term Loan A Commitment?",
        "What is the Term Loan B Commitment?",
        "What is the Term Facility amount?",
        "What is the Initial Term Loan amount?",
        "What is the Term Loan principal amount?",
        # Delayed Draw
        "What is the Delayed Draw Term Loan amount?",
        "What is the DDTL Commitment?",
        # Incremental Facility
        "What is the Incremental Facility amount?",
        "What is the Accordion amount?",
        "What is the maximum incremental commitment?",
        # Maturity variations (duplicated from agreementInfo for facility context)
        "What is the Maturity Date?",
        "What is the Termination Date?",
        "What is the Revolving Credit Maturity Date?",
        "When does the facility mature?",
        "What is the Stated Maturity Date?",
        # Principal amounts from Schedule
        "What amounts are shown in Schedule 1.01?",
        "What is in the Schedule of Commitments?",
    ],
    "lenderCommitments": [
        # Lender identification
        "What is each Lender's name?",
        "Who are the Lenders?",
        "List all Lender names",
        "Who are the Banks?",
        "Who are the financial institutions?",
        # Percentage/Pro Rata
        "What is each Lender's Applicable Percentage?",
        "What is each Lender's Pro Rata Share?",
        "What is each Lender's Ratable Percentage?",
        "What percentage does each Lender hold?",
        "What is each Lender's Commitment Percentage?",
        # Commitment amounts
        "What is each Lender's Revolving Credit Commitment?",
        "What is each Lender's Commitment amount?",
        "What is each Lender's share of the facility?",
        "What is each Lender's Term Commitment?",
        "What is each Lender's Term Loan Commitment?",
        "What is each Lender's Revolving Commitment amount?",
        # Schedule references
        "What commitments are shown in Schedule 1.01?",
        "What is in the Schedule of Lenders and Commitments?",
        "What amounts are in the Commitment Schedule?",
        # Total
        "What is the total commitment amount?",
        "What is the aggregate commitment?",
        "What is the sum of all Lender Commitments?",
        "What is the Aggregate Revolving Commitment?",
    ],
    "covenants": [
        # Fixed Charge Coverage Ratio
        "What is the Fixed Charge Coverage Ratio requirement?",
        "What is the minimum Fixed Charge Coverage Ratio?",
        "What is the FCCR requirement?",
        "What Fixed Charge Coverage Ratio must be maintained?",
        # Leverage Ratio variations
        "What is the Leverage Ratio requirement?",
        "What is the maximum Leverage Ratio?",
        "What is the Debt to EBITDA ratio requirement?",
        "What is the Total Net Leverage Ratio?",
        "What is the Consolidated Leverage Ratio?",
        "What is the Total Leverage Ratio?",
        "What is the Senior Leverage Ratio?",
        "What is the First Lien Leverage Ratio?",
        # Interest Coverage
        "What is the Interest Coverage Ratio requirement?",
        "What is the minimum Interest Coverage Ratio?",
        # Liquidity
        "What is the minimum Liquidity requirement?",
        "What is the minimum Cash requirement?",
        # General financial covenants
        "What financial covenants are required?",
        "What are the financial maintenance covenants?",
        "What financial tests must be satisfied?",
        "What are the affirmative covenants?",
        "What are the negative covenants?",
        # Testing period
        "What is the testing period for covenants?",
        "How often are covenants tested?",
        "When are financial covenants measured?",
        "Are covenants tested quarterly?",
    ],
    "fees": [
        # Commitment Fee variations (from loan_prompts_map fee types)
        "What is the Commitment Fee?",
        "What is the Unused Commitment Fee?",
        "What is the Facility Fee?",
        "What is the unused line fee?",
        "What is the Ticking Fee?",
        # LC Fee variations
        "What is the Letter of Credit Fee?",
        "What is the LC Participation Fee?",
        "What is the LC Commission?",
        "What is the LC Issuance Fee?",
        # Fronting Fee
        "What is the Fronting Fee?",
        "What is the Issuing Bank Fee?",
        "What is the LC Fronting Fee?",
        # Agency Fee
        "What is the Agency Fee?",
        "What is the Administrative Agent Fee?",
        "What annual agency fees are payable?",
        "What is the Agent Fee?",
        # Arrangement/Upfront Fees
        "What arrangement fees are required?",
        "What is the Upfront Fee?",
        "What is the Closing Fee?",
        "What are the structuring fees?",
        "What is the Origination Fee?",
        # Other fees (from loan_prompts_map: accrual_category must_be list)
        "What is the Prepayment Penalty?",
        "What is the Late Charge fee?",
        "What is the Default Interest rate?",
        "What are the Amendment Fees?",
        "What is the Syndication Fee?",
    ],
    "definitions": [
        # Rate definitions
        "What is the definition of Applicable Rate?",
        "What is the definition of Applicable Margin?",
        "How is Applicable Rate determined?",
        "What is the definition of Base Rate?",
        # EBITDA variations (from loan_prompts_map logic)
        "What is the definition of EBITDA?",
        "What is the definition of Adjusted EBITDA?",
        "What is the definition of Consolidated EBITDA?",
        "What adjustments are made to EBITDA?",
        "How is EBITDA calculated?",
        # Borrowing Base
        "What is the definition of Borrowing Base?",
        "How is Borrowing Base calculated?",
        "What assets are included in Borrowing Base?",
        "What is the Borrowing Base formula?",
        # Maturity Date - specific definition
        "What is the definition of Maturity Date?",
        "How is Maturity Date defined?",
        "What date is the Maturity Date?",
        "When is the Maturity Date?",
        # Guarantors
        "Who are the Guarantors?",
        "Who are the Subsidiary Guarantors?",
        "What entities provide guarantees?",
        "Who are the Credit Parties?",
        # Business Day - calculation method (highlighted on page 8)
        "What is the definition of Business Day?",
        "How are Business Day adjustments handled?",
        "What days are considered Business Days?",
        "How is Business Day calculated?",
        # Interest Payment Date and Interest Period (highlighted on page 22)
        "What is the definition of Interest Payment Date?",
        "When are Interest Payment Dates?",
        "How is Interest Payment Date calculated?",
        "What is the definition of Interest Period?",
        "How long is each Interest Period?",
        "How is Interest Period calculated?",
        # Lead Arranger (highlighted on page 23)
        "Who is the Lead Arranger?",
        "Who is the Joint Lead Arranger?",
        "Who are the Lead Bookrunners?",
        "What is the Lead Commitment amount?",
        # Unused Revolving Credit Commitment (highlighted on page 40)
        "What is the definition of Unused Revolving Credit Commitment?",
        "How is Unused Revolving Credit Commitment calculated?",
        "What is the Unused Commitment?",
        "How is unused commitment determined?",
        # Letter of Credit definitions (highlighted on pages 48-49)
        "What is the definition of Letter of Credit?",
        "What is the LC Expiration Date?",
        "What is the Letter of Credit Expiration Date?",
        "When do Letters of Credit expire?",
        "What is the definition of LC Commitment?",
        "What is the maximum LC amount?",
        # Commitment Fee definition (highlighted on page 59)
        "What is the definition of Commitment Fee?",
        "How is Commitment Fee calculated?",
        "What is the Unused Commitment Fee Rate?",
        "How is the Unused Revolving Credit Commitment Fee calculated?",
        # Material Adverse Effect
        "What is the definition of Material Adverse Effect?",
        "What is the definition of Material Adverse Change?",
    ],
}


def render_pdf_to_image(pdf_bytes: bytes, dpi: int = 200) -> bytes:
    """Render PDF page(s) to a PNG image using PyMuPDF.

    Textract works more reliably with images than with PyPDF-manipulated PDFs.
    This function converts the PDF to a high-resolution PNG image.

    Args:
        pdf_bytes: Raw bytes of the PDF document (typically a single page)
        dpi: Resolution for rendering (200 DPI provides good quality/size balance)

    Returns:
        PNG image bytes suitable for Textract AnalyzeDocument

    Raises:
        RuntimeError: If PyMuPDF is not available
    """
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF not available for image rendering")

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


def render_pdf_pages_to_images(pdf_bytes: bytes, dpi: int = 200) -> List[bytes]:
    """Render all pages of a PDF to individual PNG images.

    Args:
        pdf_bytes: Raw bytes of the PDF document
        dpi: Resolution for rendering

    Returns:
        List of PNG image bytes, one per page
    """
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF not available for image rendering")

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
                page_images = render_pdf_pages_to_images(section_bytes, dpi=200)
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

    # Pass through metadata for downstream processing
    content_hash = event.get('contentHash')
    file_size = event.get('size')

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
        }

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
                image_bytes = render_pdf_to_image(page_bytes, dpi=200)
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

        else:
            raise ValueError(f"Unknown extraction type: {extraction_type}")

        # 6. Clean up temp file if we created one
        if temp_key:
            s3_client.delete_object(Bucket=bucket, Key=temp_key)
            print("Cleaned up temp file")

        # 7. Return results
        return {
            'documentId': document_id,
            'contentHash': content_hash,
            'size': file_size,
            'key': key,
            'extractionType': extraction_type,
            'pageNumber': page_number,
            'status': 'EXTRACTED',
            'results': results,
            'usedImageRendering': used_image_rendering,
            'metadata': {
                'sourceKey': key,
                'sourcePage': page_number,
            },
        }

    except Exception as e:
        print(f"Error in Extractor Lambda: {str(e)}")
        raise
