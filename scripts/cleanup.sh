#!/bin/bash
# cleanup.sh - Reset S3 and DynamoDB for fresh testing/demo
#
# Usage: ./scripts/cleanup.sh [--keep-source] [--force] [--dry-run]
#   --keep-source: Keep the original PDFs in ingest/, only clean processed data
#   --force:       Skip confirmation prompt
#   --dry-run:     Show what would be deleted without deleting

source "$(dirname "$0")/common.sh"

# Configuration (derived from environment)
BUCKET_NAME=$(get_bucket_name)
TABLE_NAME=$(get_table_name)
PLUGIN_TABLE="document-plugin-configs"
PII_AUDIT_TABLE="financial-documents-pii-audit"
REGION="$AWS_REGION"

# Parse arguments
KEEP_SOURCE=false
for arg in "$@"; do
    case $arg in
        --keep-source)
            KEEP_SOURCE=true
            ;;
    esac
done

print_banner "Cleanup"

# Confirmation prompt
warning "This will delete all processed documents!"
echo ""
info "Bucket:     $BUCKET_NAME"
info "Tables:     $TABLE_NAME, $PLUGIN_TABLE, $PII_AUDIT_TABLE"
info "Region:     $REGION"
if [ "$KEEP_SOURCE" = true ]; then
    echo -e "  Mode:       ${GREEN}Keep source PDFs${NC} (only clean processed data)"
else
    echo -e "  Mode:       ${RED}Full cleanup${NC} (delete everything including source PDFs)"
fi
if [ "$DRY_RUN" = true ]; then
    echo -e "  Dry Run:    ${YELLOW}YES — no changes will be made${NC}"
fi

confirm_action "Are you sure you want to continue?"

echo ""

# ─── Helper: count objects under an S3 prefix ────────────────
# Returns 0 count safely even if prefix doesn't exist (avoids set -e / pipefail death)
s3_count() {
    local prefix="$1"
    local count
    count=$(aws s3 ls "s3://$BUCKET_NAME/$prefix" --recursive --region "$REGION" 2>/dev/null | wc -l | tr -d ' ') || true
    echo "${count:-0}"
}

# ─── Helper: delete all objects under an S3 prefix ───────────
s3_clean() {
    local prefix="$1"
    local label="$2"
    local count
    count=$(s3_count "$prefix")

    if [ "$count" -gt 0 ]; then
        echo "  Found $count files in $label"
        if [ "$DRY_RUN" = true ]; then
            echo -e "  ${YELLOW}[DRY RUN] Would delete $count files from $prefix${NC}"
        else
            aws s3 rm "s3://$BUCKET_NAME/$prefix" --recursive --quiet --region "$REGION"
            echo -e "${GREEN}  ✓ Cleaned $label ($count files)${NC}"
        fi
    else
        echo "  ✓ $label already empty"
    fi
}

# ─── Helper: scan and delete all items in a DynamoDB table ───
dynamo_clean() {
    local table="$1"
    local label="$2"

    # Check if table exists
    if ! aws dynamodb describe-table --table-name "$table" --region "$REGION" &>/dev/null; then
        echo "  ✓ $label table does not exist — skipping"
        return
    fi

    # Get key schema
    local key_schema
    key_schema=$(aws dynamodb describe-table \
        --table-name "$table" \
        --region "$REGION" \
        --query 'Table.KeySchema[].AttributeName' \
        --output json 2>/dev/null) || true

    local key_names
    key_names=$(echo "$key_schema" | python3 -c "import sys,json; print(' '.join(json.load(sys.stdin)))" 2>/dev/null) || true

    if [ -z "$key_names" ]; then
        echo -e "  ${RED}✗ Could not determine key schema for $table${NC}"
        return
    fi

    # Build projection expression from key attributes
    local projection
    projection=$(echo "$key_names" | tr ' ' ',')

    # Scan all items
    local items
    items=$(aws dynamodb scan \
        --table-name "$table" \
        --projection-expression "$projection" \
        --region "$REGION" \
        --output json 2>/dev/null) || true

    local item_count
    item_count=$(echo "$items" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('Items',[])))" 2>/dev/null || echo "0")

    if [ "$item_count" -gt 0 ]; then
        echo "  Found $item_count items in $label"
        if [ "$DRY_RUN" = true ]; then
            echo -e "  ${YELLOW}[DRY RUN] Would delete $item_count items from $table${NC}"
        else
            echo "$items" | python3 -c "
import sys, json, subprocess

data = json.load(sys.stdin)
items = data.get('Items', [])
key_names = '$key_names'.split()
deleted = 0

for item in items:
    key = {k: item[k] for k in key_names if k in item}
    if len(key) == len(key_names):
        result = subprocess.run([
            'aws', 'dynamodb', 'delete-item',
            '--table-name', '$table',
            '--key', json.dumps(key),
            '--region', '$REGION'
        ], capture_output=True)
        if result.returncode == 0:
            deleted += 1
        else:
            print(f'  ✗ Failed to delete item from $table')

print(f'  Deleted {deleted}/{len(items)} items from $label')
"
            echo -e "${GREEN}  ✓ $label cleanup complete${NC}"
        fi
    else
        echo "  ✓ $label already empty"
    fi
}

# ============================================
# Step 1: Clean DynamoDB Tables
# ============================================
echo -e "${BLUE}[1/3] Cleaning DynamoDB tables...${NC}"

dynamo_clean "$TABLE_NAME" "Documents ($TABLE_NAME)"
dynamo_clean "$PLUGIN_TABLE" "Plugin Configs ($PLUGIN_TABLE)"
dynamo_clean "$PII_AUDIT_TABLE" "PII Audit ($PII_AUDIT_TABLE)"

# ============================================
# Step 2: Clean S3 Bucket (processed data)
# ============================================
echo ""
echo -e "${BLUE}[2/3] Cleaning S3 processed data...${NC}"

s3_clean "temp/" "temp/"
s3_clean "audit/" "audit/"
s3_clean "processed/" "processed/"

# ============================================
# Step 3: Clean S3 Bucket (source files)
# ============================================
echo ""
echo -e "${BLUE}[3/3] Cleaning S3 source files...${NC}"

if [ "$KEEP_SOURCE" = true ]; then
    echo -e "${YELLOW}  Skipping ingest/ folder (--keep-source flag)${NC}"
    INGEST_COUNT=$(s3_count "ingest/")
    echo "  $INGEST_COUNT source PDFs preserved in ingest/"
else
    s3_clean "ingest/" "ingest/"
fi

# Catch-all: check for any remaining objects in unexpected prefixes
TOTAL_REMAINING=$(s3_count "")
if [ "$TOTAL_REMAINING" -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}  Found $TOTAL_REMAINING objects in unexpected prefixes:${NC}"
    aws s3 ls "s3://$BUCKET_NAME/" --region "$REGION" 2>/dev/null || true
    if [ "$DRY_RUN" = false ]; then
        if [ "$KEEP_SOURCE" = true ]; then
            # Only remove non-ingest prefixes
            aws s3 ls "s3://$BUCKET_NAME/" --region "$REGION" 2>/dev/null | awk '{print $NF}' | grep -v '^ingest/$' | while read -r prefix; do
                aws s3 rm "s3://$BUCKET_NAME/$prefix" --recursive --quiet --region "$REGION" 2>/dev/null || true
            done
            echo -e "${GREEN}  ✓ Cleaned unexpected prefixes (kept ingest/)${NC}"
        else
            aws s3 rm "s3://$BUCKET_NAME/" --recursive --quiet --region "$REGION" 2>/dev/null || true
            echo -e "${GREEN}  ✓ Cleaned all remaining objects${NC}"
        fi
    fi
fi

# ============================================
# Summary
# ============================================
FINAL_S3=$(s3_count "")
FINAL_DYNAMO=$(aws dynamodb scan --table-name "$TABLE_NAME" --select COUNT --region "$REGION" --output text --query 'Count' 2>/dev/null || echo "?")

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
if [ "$DRY_RUN" = true ]; then
echo -e "${GREEN}║                   Dry Run Complete (no changes)              ║${NC}"
else
echo -e "${GREEN}║                    Cleanup Complete!                         ║${NC}"
fi
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  S3 objects remaining:       $FINAL_S3"
echo "  DynamoDB items remaining:   $FINAL_DYNAMO"
echo ""
echo -e "${BLUE}Ready for fresh testing!${NC}"
echo ""
echo "To upload a test document:"
echo "  aws s3 cp your-document.pdf s3://$BUCKET_NAME/ingest/"
echo ""
