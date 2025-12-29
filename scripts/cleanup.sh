#!/bin/bash
# cleanup.sh - Reset S3 and DynamoDB for fresh testing/demo
#
# Usage: ./scripts/cleanup.sh [--keep-source]
#   --keep-source: Keep the original PDFs in ingest/, only clean processed data
#
# This script will:
# 1. Delete all items from DynamoDB table
# 2. Clean S3 bucket (temp/, audit/, processed/ folders)
# 3. Optionally clean ingest/ folder (unless --keep-source)

set -e

# Configuration
BUCKET_NAME="financial-docs-211125568838-us-west-2"
TABLE_NAME="financial-documents"
REGION="us-west-2"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
KEEP_SOURCE=false
for arg in "$@"; do
    case $arg in
        --keep-source)
            KEEP_SOURCE=true
            shift
            ;;
    esac
done

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Financial Documents Processing - Cleanup           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Confirmation prompt
echo -e "${YELLOW}⚠️  WARNING: This will delete all processed documents!${NC}"
echo ""
echo "  Bucket: $BUCKET_NAME"
echo "  Table:  $TABLE_NAME"
echo "  Region: $REGION"
if [ "$KEEP_SOURCE" = true ]; then
    echo -e "  Mode:   ${GREEN}Keep source PDFs${NC} (only clean processed data)"
else
    echo -e "  Mode:   ${RED}Full cleanup${NC} (delete everything including source PDFs)"
fi
echo ""
read -p "Are you sure you want to continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Cleanup cancelled.${NC}"
    exit 0
fi

echo ""

# ============================================
# Step 1: Clean DynamoDB Table
# ============================================
echo -e "${BLUE}[1/3] Cleaning DynamoDB table...${NC}"

# Get all items and delete them
ITEMS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --projection-expression "documentId, documentType" \
    --region "$REGION" \
    --output json 2>/dev/null)

ITEM_COUNT=$(echo "$ITEMS" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('Items', [])))" 2>/dev/null || echo "0")

if [ "$ITEM_COUNT" -gt 0 ]; then
    echo "  Found $ITEM_COUNT items to delete..."

    # Delete each item
    echo "$ITEMS" | python3 -c "
import sys, json, subprocess

data = json.load(sys.stdin)
items = data.get('Items', [])
deleted = 0

for item in items:
    doc_id = item.get('documentId', {}).get('S', '')
    doc_type = item.get('documentType', {}).get('S', '')

    if doc_id and doc_type:
        key = json.dumps({
            'documentId': {'S': doc_id},
            'documentType': {'S': doc_type}
        })

        result = subprocess.run([
            'aws', 'dynamodb', 'delete-item',
            '--table-name', '$TABLE_NAME',
            '--key', key,
            '--region', '$REGION'
        ], capture_output=True)

        if result.returncode == 0:
            deleted += 1
            print(f'  ✓ Deleted: {doc_id[:8]}... ({doc_type})')
        else:
            print(f'  ✗ Failed: {doc_id[:8]}...')

print(f'  Deleted {deleted}/{len(items)} items')
"
    echo -e "${GREEN}  ✓ DynamoDB cleanup complete${NC}"
else
    echo -e "${GREEN}  ✓ DynamoDB table already empty${NC}"
fi

# ============================================
# Step 2: Clean S3 Bucket (processed data)
# ============================================
echo ""
echo -e "${BLUE}[2/3] Cleaning S3 processed data...${NC}"

# Clean temp/ folder
TEMP_COUNT=$(aws s3 ls "s3://$BUCKET_NAME/temp/" --recursive 2>/dev/null | wc -l | tr -d ' ')
if [ "$TEMP_COUNT" -gt 0 ]; then
    echo "  Deleting $TEMP_COUNT files from temp/..."
    aws s3 rm "s3://$BUCKET_NAME/temp/" --recursive --quiet
    echo -e "${GREEN}  ✓ Cleaned temp/ folder${NC}"
else
    echo "  ✓ temp/ folder already empty"
fi

# Clean audit/ folder
AUDIT_COUNT=$(aws s3 ls "s3://$BUCKET_NAME/audit/" --recursive 2>/dev/null | wc -l | tr -d ' ')
if [ "$AUDIT_COUNT" -gt 0 ]; then
    echo "  Deleting $AUDIT_COUNT files from audit/..."
    aws s3 rm "s3://$BUCKET_NAME/audit/" --recursive --quiet
    echo -e "${GREEN}  ✓ Cleaned audit/ folder${NC}"
else
    echo "  ✓ audit/ folder already empty"
fi

# Clean processed/ folder
PROCESSED_COUNT=$(aws s3 ls "s3://$BUCKET_NAME/processed/" --recursive 2>/dev/null | wc -l | tr -d ' ')
if [ "$PROCESSED_COUNT" -gt 0 ]; then
    echo "  Deleting $PROCESSED_COUNT files from processed/..."
    aws s3 rm "s3://$BUCKET_NAME/processed/" --recursive --quiet
    echo -e "${GREEN}  ✓ Cleaned processed/ folder${NC}"
else
    echo "  ✓ processed/ folder already empty"
fi

# ============================================
# Step 3: Clean S3 Bucket (source files)
# ============================================
echo ""
echo -e "${BLUE}[3/3] Cleaning S3 source files...${NC}"

if [ "$KEEP_SOURCE" = true ]; then
    echo -e "${YELLOW}  ⏭  Skipping ingest/ folder (--keep-source flag)${NC}"
    INGEST_COUNT=$(aws s3 ls "s3://$BUCKET_NAME/ingest/" 2>/dev/null | grep -v "PRE" | wc -l | tr -d ' ')
    echo "  📁 $INGEST_COUNT source PDFs preserved in ingest/"
else
    INGEST_COUNT=$(aws s3 ls "s3://$BUCKET_NAME/ingest/" --recursive 2>/dev/null | wc -l | tr -d ' ')
    if [ "$INGEST_COUNT" -gt 0 ]; then
        echo "  Deleting $INGEST_COUNT files from ingest/..."
        aws s3 rm "s3://$BUCKET_NAME/ingest/" --recursive --quiet
        echo -e "${GREEN}  ✓ Cleaned ingest/ folder${NC}"
    else
        echo "  ✓ ingest/ folder already empty"
    fi
fi

# ============================================
# Summary
# ============================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Cleanup Complete! ✓                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  DynamoDB items deleted: $ITEM_COUNT"
echo "  S3 files cleaned: temp($TEMP_COUNT) + audit($AUDIT_COUNT) + processed($PROCESSED_COUNT)"
if [ "$KEEP_SOURCE" = false ]; then
    echo "  S3 source files deleted: $INGEST_COUNT"
fi
echo ""
echo -e "${BLUE}Ready for fresh testing!${NC}"
echo ""
echo "To upload a test document:"
echo "  aws s3 cp your-document.pdf s3://$BUCKET_NAME/ingest/"
echo ""
