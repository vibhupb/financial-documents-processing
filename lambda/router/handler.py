"""Router Lambda - Document Classification

This Lambda function implements the "Router" pattern:
1. Downloads the PDF from S3 (streaming to minimize memory)
2. Extracts text snippets from each page using PyPDF
3. Uses Claude 3 Haiku to classify and identify key pages
4. Returns the page numbers for targeted extraction

This is the COST OPTIMIZATION layer - we use fast, cheap Haiku
to find the needles in the haystack before expensive extraction.
"""

import json
import os
import io
import boto3
from pypdf import PdfReader
from typing import Dict, List, Any

# Initialize AWS clients
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime')

# Configuration
BUCKET_NAME = os.environ.get('BUCKET_NAME')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')

# Text extraction settings
MAX_CHARS_PER_PAGE = 1000  # Only extract first 1000 chars for classification
BATCH_SIZE = 50  # Pages per Bedrock request


def extract_page_snippets(pdf_stream: io.BytesIO) -> List[Dict[str, Any]]:
    """Extract text snippets from each page of the PDF.
    
    Args:
        pdf_stream: BytesIO stream containing the PDF
        
    Returns:
        List of dicts with page number and text snippet
    """
    reader = PdfReader(pdf_stream)
    page_snippets = []
    
    for i, page in enumerate(reader.pages):
        try:
            # Extract text (PyPDF is fast for text extraction)
            text = page.extract_text() or ""
            
            # Take only the first N characters for classification
            snippet = text[:MAX_CHARS_PER_PAGE].strip()
            
            page_snippets.append({
                'page_number': i + 1,  # 1-indexed for human readability
                'snippet': snippet,
                'has_text': len(snippet) > 50  # Flag if page has meaningful text
            })
        except Exception as e:
            print(f"Error extracting page {i + 1}: {str(e)}")
            page_snippets.append({
                'page_number': i + 1,
                'snippet': '',
                'has_text': False,
                'error': str(e)
            })
    
    return page_snippets


def classify_pages_with_bedrock(page_snippets: List[Dict[str, Any]]) -> Dict[str, int]:
    """Use Claude Haiku to classify pages and identify document types.
    
    Args:
        page_snippets: List of page snippets from extract_page_snippets
        
    Returns:
        Dict mapping document type to page number
    """
    # Filter to only pages with text
    text_pages = [p for p in page_snippets if p['has_text']]
    
    # Format pages for the prompt
    formatted_pages = "\n\n".join([
        f"=== PAGE {p['page_number']} ===\n{p['snippet']}"
        for p in text_pages
    ])
    
    prompt = f"""You are a mortgage document classifier specializing in loan packages.

Analyze the following page snippets from a loan document package. Your task is to identify the FIRST page number where each of these key documents begins:

1. **Promissory Note** - The legal document where borrower promises to repay the loan
   - Look for: "PROMISSORY NOTE", "NOTE", "promise to pay", "interest rate", "principal amount"
   
2. **Closing Disclosure** - The 5-page TILA-RESPA form with loan terms and costs
   - Look for: "CLOSING DISCLOSURE", "Closing Cost Details", "Loan Terms", "Projected Payments"
   
3. **Form 1003** - Uniform Residential Loan Application
   - Look for: "Uniform Residential Loan Application", "1003", "Borrower Information", "Employment Information"

PAGE SNIPPETS:
{formatted_pages}

IMPORTANT RULES:
- Return ONLY the page number where each document STARTS
- If a document type is not found, use null
- Be conservative - only identify if you're confident

Respond with ONLY valid JSON in this exact format:
{{
  "promissoryNote": <page_number or null>,
  "closingDisclosure": <page_number or null>,
  "form1003": <page_number or null>,
  "confidence": "high" | "medium" | "low",
  "totalPagesAnalyzed": <number>
}}"""

    # Call Bedrock
    response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType='application/json',
        accept='application/json',
        body=json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': 500,
            'temperature': 0,  # Deterministic for classification
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
        })
    )
    
    # Parse response
    response_body = json.loads(response['body'].read())
    content = response_body['content'][0]['text']
    
    # Extract JSON from response
    try:
        # Handle potential markdown code blocks
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]
        
        classification = json.loads(content.strip())
        return classification
    except json.JSONDecodeError as e:
        print(f"Error parsing classification response: {content}")
        raise ValueError(f"Failed to parse Bedrock response: {str(e)}")


def lambda_handler(event, context):
    """Main Lambda handler for document classification.
    
    Args:
        event: Input event containing documentId, bucket, and key
        context: Lambda context
        
    Returns:
        Dict with classification results and metadata for next steps
    """
    print(f"Router Lambda received event: {json.dumps(event)}")
    
    # Extract input parameters
    document_id = event['documentId']
    bucket = event.get('bucket', BUCKET_NAME)
    key = event['key']
    
    print(f"Processing document: {document_id} from s3://{bucket}/{key}")
    
    try:
        # 1. Download PDF from S3 as stream
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_stream = io.BytesIO(s3_response['Body'].read())
        
        # 2. Extract page snippets (fast, no OCR)
        print("Extracting page snippets...")
        page_snippets = extract_page_snippets(pdf_stream)
        total_pages = len(page_snippets)
        print(f"Extracted snippets from {total_pages} pages")
        
        # 3. Classify pages using Bedrock
        print("Classifying pages with Claude Haiku...")
        classification = classify_pages_with_bedrock(page_snippets)
        print(f"Classification result: {json.dumps(classification)}")
        
        # 4. Prepare output for Step Functions
        return {
            'documentId': document_id,
            'bucket': bucket,
            'key': key,
            'totalPages': total_pages,
            'classification': classification,
            'status': 'CLASSIFIED',
            'metadata': {
                'routerModel': BEDROCK_MODEL_ID,
                'pagesWithText': len([p for p in page_snippets if p['has_text']]),
                'costEstimate': {
                    'classificationTokens': total_pages * 100,  # Rough estimate
                    'targetedPages': sum(1 for v in [
                        classification.get('promissoryNote'),
                        classification.get('closingDisclosure'),
                        classification.get('form1003')
                    ] if v is not None)
                }
            }
        }
        
    except Exception as e:
        print(f"Error in Router Lambda: {str(e)}")
        raise
