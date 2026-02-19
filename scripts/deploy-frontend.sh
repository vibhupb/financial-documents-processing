#!/bin/bash
# Deploy frontend to S3 + CloudFront invalidation
#
# Usage: ./scripts/deploy-frontend.sh [--force] [--skip-build]

source "$(dirname "$0")/common.sh"

print_banner "Deploy Frontend"

SKIP_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=true ;;
    esac
done

FRONTEND_BUCKET=$(get_stack_output "FrontendBucketName")
if [ -z "$FRONTEND_BUCKET" ]; then
    FRONTEND_BUCKET="financial-docs-frontend-${AWS_ACCOUNT_ID}-${AWS_REGION}"
fi

CLOUDFRONT_URL=$(get_stack_output "CloudFrontUrl")

info "Frontend bucket: $FRONTEND_BUCKET"
info "CloudFront URL:  $CLOUDFRONT_URL"
confirm_action "Deploy frontend to $FRONTEND_BUCKET?"

cd "$PROJECT_ROOT/frontend"

# Build
if [ "$SKIP_BUILD" = "false" ]; then
    info "[1/3] Installing dependencies..."
    npm install

    info "[2/3] Building frontend..."
    npm run build
    if [ ! -d "dist" ]; then
        fail "Frontend build failed - dist/ directory not found"
    fi
    success "Frontend built: $(du -sh dist | cut -f1)"
else
    info "[1/3] Skipping install (--skip-build)"
    info "[2/3] Skipping build (--skip-build)"
fi

# Sync to S3
info "[3/3] Syncing to S3..."
aws s3 sync dist/ "s3://$FRONTEND_BUCKET/" --delete --region "$AWS_REGION"
success "Synced to s3://$FRONTEND_BUCKET/"

# CloudFront invalidation
DIST_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Origins.Items[?Id=='S3-${FRONTEND_BUCKET}']].Id" \
    --output text --region "$AWS_REGION" 2>/dev/null)

if [ -z "$DIST_ID" ] || [ "$DIST_ID" = "None" ]; then
    # Try alternate lookup
    DIST_ID=$(aws cloudfront list-distributions \
        --query "DistributionList.Items[?Comment=='Financial Documents Dashboard'].Id" \
        --output text --region "$AWS_REGION" 2>/dev/null)
fi

if [ -n "$DIST_ID" ] && [ "$DIST_ID" != "None" ]; then
    info "Invalidating CloudFront cache (distribution: $DIST_ID)..."
    aws cloudfront create-invalidation \
        --distribution-id "$DIST_ID" \
        --paths "/*" --region "$AWS_REGION" > /dev/null
    success "CloudFront invalidation created"
else
    warning "Could not find CloudFront distribution ID - cache not invalidated"
    info "Hard refresh (Cmd+Shift+R) may be needed"
fi

echo ""
success "Frontend deployed!"
info "Dashboard: $CLOUDFRONT_URL"
