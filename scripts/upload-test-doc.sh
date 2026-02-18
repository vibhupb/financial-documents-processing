#!/bin/bash
# Upload a test document to trigger the processing pipeline

source "$(dirname "$0")/common.sh"

if [ -z "$1" ]; then
    fail "Usage: $0 <path-to-pdf-file>"
fi

PDF_FILE="$1"

if [ ! -f "$PDF_FILE" ]; then
    fail "File not found: $PDF_FILE"
fi

BUCKET_NAME=$(get_bucket_name)

print_banner "Upload Test Document"
info "File: $PDF_FILE"
info "Bucket: s3://$BUCKET_NAME/ingest/"

aws s3 cp "$PDF_FILE" "s3://$BUCKET_NAME/ingest/"

echo ""
success "Document uploaded! The Step Functions workflow should start automatically."
echo ""
info "Monitor processing with:"
STATE_MACHINE_ARN=$(get_stack_output "StateMachineArn" 2>/dev/null || echo "<state-machine-arn>")
echo "  aws stepfunctions list-executions --state-machine-arn $STATE_MACHINE_ARN"
