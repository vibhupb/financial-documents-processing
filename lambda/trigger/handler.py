"""S3 Event Trigger Lambda

This Lambda function is triggered by S3 events when a new document
is uploaded to the ingest/ prefix. It starts the Step Functions
state machine for document processing.
"""

import json
import os
import uuid
import boto3
from datetime import datetime

# Initialize AWS clients
sfn_client = boto3.client('stepfunctions')

STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']


def lambda_handler(event, context):
    """Handle S3 event and start Step Functions execution.
    
    Args:
        event: S3 event containing information about the uploaded file
        context: Lambda context object
        
    Returns:
        dict: Response with execution details
    """
    print(f"Received event: {json.dumps(event)}")
    
    responses = []
    
    for record in event.get('Records', []):
        # Extract S3 object information
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        size = record['s3']['object'].get('size', 0)
        
        # Generate unique document ID
        document_id = str(uuid.uuid4())
        
        # Prepare input for Step Functions
        sfn_input = {
            'documentId': document_id,
            'bucket': bucket,
            'key': key,
            'size': size,
            'uploadedAt': datetime.utcnow().isoformat(),
            'source': 's3-trigger'
        }
        
        # Start Step Functions execution
        execution_name = f"doc-{document_id[:8]}-{int(datetime.utcnow().timestamp())}"
        
        try:
            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=execution_name,
                input=json.dumps(sfn_input)
            )
            
            print(f"Started execution: {response['executionArn']}")
            
            responses.append({
                'documentId': document_id,
                'executionArn': response['executionArn'],
                'status': 'STARTED'
            })
            
        except Exception as e:
            print(f"Error starting execution: {str(e)}")
            responses.append({
                'documentId': document_id,
                'error': str(e),
                'status': 'FAILED'
            })
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Processed {len(responses)} documents',
            'executions': responses
        })
    }
