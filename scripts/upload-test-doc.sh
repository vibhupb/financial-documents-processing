#!/bin/bash
# Upload a test document to trigger the processing pipeline

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <path-to-pdf-file>"
    echo "Example: $0 ./test-documents/sample-loan-package.pdf"
    exit 1
fi

PDF_FILE="$1"

if [ ! -f "$PDF_FILE" ]; then
    echo "Error: File not found: $PDF_FILE"
    exit 1
fi

# Get bucket name from CloudFormation exports
BUCKET_NAME=$(aws cloudformation list-exports \
    --query "Exports[?Name=='FinancialDocBucket'].Value" \
    --output text 2>/dev/null)

if [ -z "$BUCKET_NAME" ]; then
    echo "Error: Could not find bucket name. Make sure the stack is deployed."
    echo "Run: ./scripts/deploy.sh first"
    exit 1
fi

echo "Uploading $PDF_FILE to s3://$BUCKET_NAME/ingest/..."
aws s3 cp "$PDF_FILE" "s3://$BUCKET_NAME/ingest/"

echo ""
echo "Document uploaded! The Step Functions workflow should start automatically."
echo ""
echo "Monitor processing with:"
echo "  aws stepfunctions list-executions --state-machine-arn \$(aws cloudformation list-exports --query \"Exports[?Name=='FinancialDocStateMachine'].Value\" --output text)"
