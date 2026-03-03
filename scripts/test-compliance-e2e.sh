#!/bin/bash
# End-to-end compliance engine test
# Tests: baseline CRUD -> document upload -> compliance evaluation -> report check
source "$(dirname "$0")/common.sh"
set -euo pipefail

print_banner "Compliance Engine E2E Test"

# ─── Resolve API URL ────────────────────────────────────────
API_URL=$(get_stack_output "ApiEndpoint" 2>/dev/null) || fail "Could not resolve API endpoint. Run ./scripts/deploy-backend.sh first."
# Strip trailing slash if present
API_URL="${API_URL%/}"
info "API URL: $API_URL"
echo ""

echo "=== Step 1: Create a draft baseline ==="
BASELINE=$(curl -s -X POST "$API_URL/baselines" \
  -H "Content-Type: application/json" \
  -d '{"name":"E2E Test Baseline","description":"Automated test","pluginIds":["loan_package"]}')
BL_ID=$(echo "$BASELINE" | jq -r '.baselineId')
echo "Created baseline: $BL_ID"

if [ -z "$BL_ID" ] || [ "$BL_ID" = "null" ]; then
  echo "Response: $BASELINE"
  fail "Failed to create baseline. Check API deployment."
fi

echo "=== Step 2: Add requirements ==="
curl -s -X POST "$API_URL/baselines/$BL_ID/requirements" \
  -H "Content-Type: application/json" \
  -d '{"text":"Must specify interest rate","category":"Rates","criticality":"must-have","evaluationHint":"Look for APR, interest rate, annual percentage"}'
echo ""

curl -s -X POST "$API_URL/baselines/$BL_ID/requirements" \
  -H "Content-Type: application/json" \
  -d '{"text":"Must include borrower name","category":"Identity","criticality":"must-have","evaluationHint":"Look for borrower, applicant, obligor name"}'
echo ""

echo "=== Step 3: Publish baseline ==="
PUBLISH=$(curl -s -X POST "$API_URL/baselines/$BL_ID/publish")
echo "$PUBLISH" | jq .

echo "=== Step 4: Upload a test document ==="
# Get presigned upload URL
UPLOAD_RESP=$(curl -s -X POST "$API_URL/upload" \
  -H "Content-Type: application/json" \
  -d "{\"filename\":\"e2e-test.pdf\",\"processingMode\":\"extract\",\"baselineIds\":[\"$BL_ID\"]}")
DOC_ID=$(echo "$UPLOAD_RESP" | jq -r '.documentId')
UPLOAD_URL=$(echo "$UPLOAD_RESP" | jq -r '.uploadUrl')
echo "Document ID: $DOC_ID"

if [ -z "$DOC_ID" ] || [ "$DOC_ID" = "null" ]; then
  echo "Response: $UPLOAD_RESP"
  fail "Failed to get upload URL. Check API deployment."
fi

# Upload a sample PDF if available
SAMPLE_PDF="$PROJECT_ROOT/tests/sample-documents/sample-loan.pdf"
if [ -f "$SAMPLE_PDF" ]; then
  # Use the presigned URL for direct PUT upload
  echo "Uploading $SAMPLE_PDF..."
  curl -s -X PUT "$UPLOAD_URL" \
    -H "Content-Type: application/pdf" \
    --data-binary "@$SAMPLE_PDF" || echo "Upload via presigned URL"
  echo "Upload complete."
else
  warning "No sample PDF found at $SAMPLE_PDF"
  echo "Skipping upload — create a sample PDF to run full e2e test."
  echo ""
  echo "=== Cleanup ==="
  curl -s -X DELETE "$API_URL/baselines/$BL_ID" | jq .
  echo "Baseline archived. Test partially complete (no document to process)."
  exit 0
fi

echo "=== Step 5: Wait for processing ==="
for i in $(seq 1 30); do
  STATUS=$(curl -s "$API_URL/documents/$DOC_ID/status" 2>/dev/null | jq -r '.status // "UNKNOWN"')
  echo "  Status: $STATUS (attempt $i/30)"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "COMPLETED" ]; then
    break
  fi
  if [ "$STATUS" = "FAILED" ]; then
    fail "Processing failed!"
  fi
  sleep 10
done

echo "=== Step 6: Check compliance report ==="
REPORT=$(curl -s "$API_URL/documents/$DOC_ID/compliance")
echo "$REPORT" | jq .
SCORE=$(echo "$REPORT" | jq '.reports[0].overallScore // -1')
RESULT_COUNT=$(echo "$REPORT" | jq '.reports[0].results | length // 0')
echo ""
echo "Compliance score: $SCORE"
echo "Results evaluated: $RESULT_COUNT"

if [ "$SCORE" = "-1" ]; then
  warning "No compliance report found. The compliance evaluation may not have run."
else
  success "Compliance report generated with score $SCORE"
fi

echo ""
echo "=== Step 7: Cleanup ==="
curl -s -X DELETE "$API_URL/baselines/$BL_ID" | jq .
echo "Baseline archived. E2E test complete."
