"""Normalizer Lambda - Data Refinement and Storage

This Lambda function implements the "Closer" pattern:
1. Receives raw Textract output from parallel extractions
2. Uses Claude 3.5 Sonnet to normalize and validate the data
3. Stores clean JSON to DynamoDB (for app) and S3 (for audit)
4. Ensures data conforms to expected schema

This is the QUALITY layer - we use a sophisticated model
to ensure data accuracy and consistency.
"""

import json
import os
import boto3
from datetime import datetime
from typing import Dict, List, Any, Optional
from decimal import Decimal

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock_client = boto3.client('bedrock-runtime')

# Configuration
BUCKET_NAME = os.environ.get('BUCKET_NAME')
TABLE_NAME = os.environ.get('TABLE_NAME')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types for DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def convert_floats_to_decimal(obj):
    """Recursively convert floats to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(i) for i in obj]
    return obj


def normalize_with_bedrock(raw_extractions: List[Dict[str, Any]], document_id: str) -> Dict[str, Any]:
    """Use Claude 3.5 Sonnet to normalize and validate extracted data.
    
    Args:
        raw_extractions: List of extraction results from parallel Textract operations
        document_id: Unique document identifier
        
    Returns:
        Normalized and validated data dictionary
    """
    # Format the raw extractions for the prompt
    extractions_json = json.dumps(raw_extractions, indent=2, cls=DecimalEncoder)
    
    prompt = f"""You are a financial data normalizer for mortgage loan documents. 

You have received raw OCR extraction results from different parts of a loan document package.
Your job is to normalize, validate, and structure this data into a clean, consistent format.

RAW EXTRACTION DATA:
{extractions_json}

NORMALIZATION RULES:

1. **Interest Rates**: 
   - Convert to decimal format (e.g., "5.5%" or "5.500%" -> 0.055)
   - Handle text formats ("Five and a half percent" -> 0.055)

2. **Currency/Dollar Amounts**:
   - Convert to numeric format without symbols (e.g., "$250,000.00" -> 250000.00)
   - Handle text formats ("Two hundred fifty thousand" -> 250000.00)

3. **Names**:
   - Convert to Title Case ("SMITH, JOHN A" -> "John A Smith")
   - Handle various formats consistently

4. **Dates**:
   - Convert to ISO 8601 format (YYYY-MM-DD)
   - Handle various input formats ("01/15/2024", "January 15, 2024", etc.)

5. **Percentages (non-rates)**:
   - Convert to decimal (e.g., "80%" -> 0.80)

6. **Missing/Unclear Data**:
   - If data cannot be confidently extracted, use null
   - NEVER hallucinate or guess missing values
   - Add a note in the validation_notes field

OUTPUT SCHEMA:
{{
  "loanData": {{
    "promissoryNote": {{
      "interestRate": <decimal or null>,
      "principalAmount": <number or null>,
      "borrowerName": <string or null>,
      "coBorrowerName": <string or null>,
      "maturityDate": <ISO date string or null>,
      "monthlyPayment": <number or null>,
      "firstPaymentDate": <ISO date string or null>
    }},
    "closingDisclosure": {{
      "loanAmount": <number or null>,
      "interestRate": <decimal or null>,
      "monthlyPrincipalAndInterest": <number or null>,
      "estimatedTotalMonthlyPayment": <number or null>,
      "closingCosts": <number or null>,
      "cashToClose": <number or null>,
      "fees": [
        {{
          "name": <string>,
          "amount": <number>
        }}
      ]
    }},
    "form1003": {{
      "borrowerInfo": {{
        "name": <string or null>,
        "ssn": <string or null>,
        "dateOfBirth": <ISO date string or null>,
        "phone": <string or null>,
        "email": <string or null>
      }},
      "propertyAddress": {{
        "street": <string or null>,
        "city": <string or null>,
        "state": <string or null>,
        "zipCode": <string or null>
      }},
      "employmentInfo": {{
        "employerName": <string or null>,
        "position": <string or null>,
        "yearsEmployed": <number or null>,
        "monthlyIncome": <number or null>
      }}
    }}
  }},
  "validation": {{
    "isValid": <boolean>,
    "confidence": "high" | "medium" | "low",
    "crossReferenceChecks": [
      {{
        "field1": <string>,
        "field2": <string>,
        "match": <boolean>,
        "note": <string or null>
      }}
    ],
    "validationNotes": [<string>],
    "missingRequiredFields": [<string>]
  }},
  "audit": {{
    "extractionSources": [
      {{
        "field": <string>,
        "sourceDocument": <string>,
        "sourcePage": <number>,
        "rawValue": <string>,
        "normalizedValue": <any>
      }}
    ]
  }}
}}

IMPORTANT:
- Cross-reference interest rates and loan amounts between Promissory Note and Closing Disclosure
- Flag any discrepancies in the validation section
- Include audit trail showing original values and normalized values
- Be conservative - better to return null than incorrect data

Respond with ONLY valid JSON matching the schema above."""

    # Call Bedrock
    response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType='application/json',
        accept='application/json',
        body=json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': 4096,
            'temperature': 0,  # Deterministic for consistency
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
        
        normalized_data = json.loads(content.strip())
        return normalized_data
    except json.JSONDecodeError as e:
        print(f"Error parsing normalization response: {content}")
        raise ValueError(f"Failed to parse Bedrock response: {str(e)}")


def store_to_dynamodb(document_id: str, normalized_data: Dict[str, Any]) -> None:
    """Store normalized data to DynamoDB.
    
    Args:
        document_id: Unique document identifier
        normalized_data: Normalized loan data
    """
    table = dynamodb.Table(TABLE_NAME)
    
    timestamp = datetime.utcnow().isoformat()
    
    # Store main loan data record
    item = {
        'documentId': document_id,
        'documentType': 'LOAN_PACKAGE',
        'data': convert_floats_to_decimal(normalized_data.get('loanData', {})),
        'validation': convert_floats_to_decimal(normalized_data.get('validation', {})),
        'status': 'PROCESSED',
        'createdAt': timestamp,
        'updatedAt': timestamp,
        'ttl': int(datetime.utcnow().timestamp()) + (365 * 24 * 60 * 60)  # 1 year TTL
    }
    
    table.put_item(Item=item)
    print(f"Stored normalized data to DynamoDB: {document_id}")


def store_audit_to_s3(bucket: str, document_id: str, raw_extractions: List[Dict], normalized_data: Dict) -> str:
    """Store complete audit trail to S3.
    
    Args:
        bucket: S3 bucket name
        document_id: Unique document identifier
        raw_extractions: Original extraction results
        normalized_data: Normalized data
        
    Returns:
        S3 key of the audit file
    """
    timestamp = datetime.utcnow().isoformat()
    
    audit_record = {
        'documentId': document_id,
        'processedAt': timestamp,
        'rawExtractions': raw_extractions,
        'normalizedData': normalized_data,
        'processingMetadata': {
            'normalizerModel': BEDROCK_MODEL_ID,
            'version': '1.0.0'
        }
    }
    
    key = f"audit/{document_id}/{timestamp.replace(':', '-')}.json"
    
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(audit_record, indent=2, cls=DecimalEncoder),
        ContentType='application/json'
    )
    
    print(f"Stored audit trail to s3://{bucket}/{key}")
    return key


def lambda_handler(event, context):
    """Main Lambda handler for data normalization and storage.
    
    Args:
        event: Input event containing documentId and extraction results
        context: Lambda context
        
    Returns:
        Dict with processing results and storage locations
    """
    print(f"Normalizer Lambda received event: {json.dumps(event, cls=DecimalEncoder)}")
    
    # Extract document ID from the classification step
    # The event structure depends on Step Functions output
    document_id = None
    bucket = BUCKET_NAME
    
    # Handle different event structures
    if 'documentId' in event:
        document_id = event['documentId']
    elif isinstance(event, list) and len(event) > 0:
        # Coming from parallel state - extractions are in array
        for item in event:
            if isinstance(item, dict) and 'documentId' in item:
                document_id = item['documentId']
                break
    
    if not document_id:
        raise ValueError("Could not find documentId in event")
    
    # Get extractions - they come from the parallel state
    extractions = event.get('extractions', event if isinstance(event, list) else [event])
    
    print(f"Processing {len(extractions)} extractions for document: {document_id}")
    
    try:
        # 1. Normalize data with Bedrock
        print("Normalizing data with Claude 3.5 Sonnet...")
        normalized_data = normalize_with_bedrock(extractions, document_id)
        print(f"Normalization complete. Validation: {normalized_data.get('validation', {})}")
        
        # 2. Store to DynamoDB
        print("Storing to DynamoDB...")
        store_to_dynamodb(document_id, normalized_data)
        
        # 3. Store audit trail to S3
        print("Storing audit trail to S3...")
        audit_key = store_audit_to_s3(bucket, document_id, extractions, normalized_data)
        
        # 4. Return results
        return {
            'documentId': document_id,
            'status': 'COMPLETED',
            'validation': normalized_data.get('validation', {}),
            'storage': {
                'dynamodbTable': TABLE_NAME,
                'auditS3Key': audit_key
            },
            'summary': {
                'loanAmount': normalized_data.get('loanData', {}).get('promissoryNote', {}).get('principalAmount'),
                'interestRate': normalized_data.get('loanData', {}).get('promissoryNote', {}).get('interestRate'),
                'borrowerName': normalized_data.get('loanData', {}).get('promissoryNote', {}).get('borrowerName'),
                'isValid': normalized_data.get('validation', {}).get('isValid', False),
                'confidence': normalized_data.get('validation', {}).get('confidence', 'low')
            }
        }
        
    except Exception as e:
        print(f"Error in Normalizer Lambda: {str(e)}")
        raise
