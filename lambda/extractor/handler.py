"""Extractor Lambda - Targeted Textract Extraction

This Lambda function implements the "Surgeon" pattern:
1. Receives specific page numbers from the Router
2. Extracts ONLY those pages from the PDF
3. Uses Amazon Textract with targeted queries/tables/forms
4. Returns structured extraction results

This is the PRECISION layer - we use Textract's visual grounding
for accurate extraction of specific document elements.
"""

import json
import os
import io
import boto3
from pypdf import PdfReader, PdfWriter
from typing import Dict, List, Any, Optional
import time

# Initialize AWS clients
s3_client = boto3.client('s3')
textract_client = boto3.client('textract')

# Configuration
BUCKET_NAME = os.environ.get('BUCKET_NAME')


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


def extract_with_queries(bucket: str, key: str, queries: List[str]) -> Dict[str, Any]:
    """Use Textract AnalyzeDocument with Queries feature.
    
    Args:
        bucket: S3 bucket name
        key: S3 key of the document
        queries: List of natural language queries
        
    Returns:
        Dict with query results
    """
    response = textract_client.analyze_document(
        Document={
            'S3Object': {
                'Bucket': bucket,
                'Name': key
            }
        },
        FeatureTypes=['QUERIES'],
        QueriesConfig={
            'Queries': [{'Text': q} for q in queries]
        }
    )
    
    # Parse query results
    results = {}
    
    for block in response.get('Blocks', []):
        if block['BlockType'] == 'QUERY':
            query_text = block.get('Query', {}).get('Text', '')
            # Find the corresponding answer
            for relationship in block.get('Relationships', []):
                if relationship['Type'] == 'ANSWER':
                    answer_ids = relationship['Ids']
                    for answer_id in answer_ids:
                        answer_block = next(
                            (b for b in response['Blocks'] if b['Id'] == answer_id),
                            None
                        )
                        if answer_block:
                            results[query_text] = {
                                'answer': answer_block.get('Text', ''),
                                'confidence': answer_block.get('Confidence', 0),
                                'geometry': answer_block.get('Geometry', {})
                            }
    
    return results


def extract_tables(bucket: str, key: str) -> Dict[str, Any]:
    """Use Textract AnalyzeDocument with Tables feature.
    
    Args:
        bucket: S3 bucket name
        key: S3 key of the document
        
    Returns:
        Dict with table extraction results
    """
    response = textract_client.analyze_document(
        Document={
            'S3Object': {
                'Bucket': bucket,
                'Name': key
            }
        },
        FeatureTypes=['TABLES']
    )
    
    # Parse table results
    tables = []
    
    # Build a map of block IDs to blocks
    blocks_map = {block['Id']: block for block in response.get('Blocks', [])}
    
    for block in response.get('Blocks', []):
        if block['BlockType'] == 'TABLE':
            table_data = {
                'rows': [],
                'confidence': block.get('Confidence', 0)
            }
            
            # Get cells
            cells = []
            for relationship in block.get('Relationships', []):
                if relationship['Type'] == 'CHILD':
                    for cell_id in relationship['Ids']:
                        cell_block = blocks_map.get(cell_id)
                        if cell_block and cell_block['BlockType'] == 'CELL':
                            # Get cell text
                            cell_text = ''
                            for cell_rel in cell_block.get('Relationships', []):
                                if cell_rel['Type'] == 'CHILD':
                                    for word_id in cell_rel['Ids']:
                                        word_block = blocks_map.get(word_id)
                                        if word_block and word_block['BlockType'] == 'WORD':
                                            cell_text += word_block.get('Text', '') + ' '
                            
                            cells.append({
                                'row': cell_block.get('RowIndex', 0),
                                'col': cell_block.get('ColumnIndex', 0),
                                'text': cell_text.strip(),
                                'confidence': cell_block.get('Confidence', 0)
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
    
    return {'tables': tables, 'tableCount': len(tables)}


def extract_forms(bucket: str, key: str) -> Dict[str, Any]:
    """Use Textract AnalyzeDocument with Forms feature.
    
    Args:
        bucket: S3 bucket name
        key: S3 key of the document
        
    Returns:
        Dict with form key-value extraction results
    """
    response = textract_client.analyze_document(
        Document={
            'S3Object': {
                'Bucket': bucket,
                'Name': key
            }
        },
        FeatureTypes=['FORMS']
    )
    
    # Build blocks map
    blocks_map = {block['Id']: block for block in response.get('Blocks', [])}
    
    # Extract key-value pairs
    key_values = {}
    
    for block in response.get('Blocks', []):
        if block['BlockType'] == 'KEY_VALUE_SET' and 'KEY' in block.get('EntityTypes', []):
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
            for rel in block.get('Relationships', []):
                if rel['Type'] == 'VALUE':
                    for value_id in rel['Ids']:
                        value_block = blocks_map.get(value_id)
                        if value_block:
                            for value_rel in value_block.get('Relationships', []):
                                if value_rel['Type'] == 'CHILD':
                                    for word_id in value_rel['Ids']:
                                        word_block = blocks_map.get(word_id)
                                        if word_block and word_block['BlockType'] == 'WORD':
                                            value_text += word_block.get('Text', '') + ' '
            
            if key_text.strip():
                key_values[key_text.strip()] = {
                    'value': value_text.strip(),
                    'confidence': block.get('Confidence', 0)
                }
    
    return {'keyValues': key_values, 'fieldCount': len(key_values)}


def lambda_handler(event, context):
    """Main Lambda handler for targeted document extraction.
    
    Args:
        event: Input event containing documentId, bucket, key, pageNumber, extractionType, and optional queries
        context: Lambda context
        
    Returns:
        Dict with extraction results
    """
    print(f"Extractor Lambda received event: {json.dumps(event)}")
    
    # Extract input parameters
    document_id = event['documentId']
    bucket = event.get('bucket', BUCKET_NAME)
    key = event['key']
    page_number = event.get('pageNumber')
    extraction_type = event.get('extractionType', 'QUERIES')
    queries = event.get('queries', [])
    
    # Handle null page number (document type not found)
    if page_number is None:
        print(f"Page number is null - document type not found in classification")
        return {
            'documentId': document_id,
            'extractionType': extraction_type,
            'pageNumber': None,
            'status': 'SKIPPED',
            'reason': 'Document type not found in classification',
            'results': None
        }
    
    print(f"Extracting page {page_number} from s3://{bucket}/{key} using {extraction_type}")
    
    try:
        # 1. Download full PDF
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_stream = io.BytesIO(s3_response['Body'].read())
        
        # 2. Extract the single page
        print(f"Extracting page {page_number}...")
        page_bytes = extract_single_page(pdf_stream, page_number)
        
        # 3. Upload extracted page for Textract
        temp_key = upload_temp_page(bucket, document_id, page_number, page_bytes)
        print(f"Uploaded temp page to s3://{bucket}/{temp_key}")
        
        # 4. Run appropriate extraction
        results = None
        
        if extraction_type == 'QUERIES':
            if not queries:
                raise ValueError("QUERIES extraction requires a list of queries")
            print(f"Running Textract Queries: {queries}")
            results = extract_with_queries(bucket, temp_key, queries)
            
        elif extraction_type == 'TABLES':
            print("Running Textract Tables extraction...")
            results = extract_tables(bucket, temp_key)
            
        elif extraction_type == 'FORMS':
            print("Running Textract Forms extraction...")
            results = extract_forms(bucket, temp_key)
            
        else:
            raise ValueError(f"Unknown extraction type: {extraction_type}")
        
        # 5. Clean up temp file
        s3_client.delete_object(Bucket=bucket, Key=temp_key)
        print("Cleaned up temp file")
        
        # 6. Return results
        return {
            'documentId': document_id,
            'extractionType': extraction_type,
            'pageNumber': page_number,
            'status': 'EXTRACTED',
            'results': results,
            'metadata': {
                'sourceKey': key,
                'sourcePage': page_number
            }
        }
        
    except Exception as e:
        print(f"Error in Extractor Lambda: {str(e)}")
        raise
