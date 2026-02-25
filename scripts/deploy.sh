#!/bin/bash
# Deployment script for Financial Documents Processing
#
# Usage: ./scripts/deploy.sh [--force] [--dry-run]

source "$(dirname "$0")/common.sh"

cd "$PROJECT_ROOT"

# Check additional prerequisites
command -v npm >/dev/null 2>&1 || fail "npm is required but not installed."
command -v cdk >/dev/null 2>&1 || fail "AWS CDK is required. Install with: npm install -g aws-cdk"

print_banner "Deploy"
confirm_action "Deploy to AWS Account $AWS_ACCOUNT_ID in $AWS_REGION?"

# Install Node dependencies
echo ""
info "[1/6] Installing Node.js dependencies..."
npm install

# Setup Python environment
echo ""
info "[2/6] Setting up Python environment..."
uv sync --dev

# Build Lambda layers
echo ""
info "[3/6] Building Lambda layers..."
cd lambda/layers/pypdf
chmod +x build.sh
./build.sh
cd "$PROJECT_ROOT"

# Build TypeScript
echo ""
info "[4/6] Building TypeScript CDK..."
npm run build

# Build Frontend
echo ""
info "[5/6] Building Frontend..."
cd frontend
npm install
npm run build
cd "$PROJECT_ROOT"

# Deploy
echo ""
info "[6/6] Deploying to AWS..."
cdk deploy --all --require-approval never --outputs-file cdk-outputs.json

# Deploy frontend to S3 (after CDK deployment)
echo ""
echo "Deploying frontend to S3..."
FRONTEND_BUCKET=$(cat cdk-outputs.json | grep FrontendBucketName | cut -d'"' -f4)
if [ -n "$FRONTEND_BUCKET" ]; then
    aws s3 sync frontend/dist/ "s3://$FRONTEND_BUCKET/" --delete
    echo "Frontend deployed to S3 bucket: $FRONTEND_BUCKET"

    # Invalidate CloudFront cache
    DISTRIBUTION_ID=$(aws cloudfront list-distributions \
        --query "DistributionList.Items[?Origins.Items[?contains(DomainName, '$FRONTEND_BUCKET')]].Id" \
        --output text 2>/dev/null) || true
    if [ -n "$DISTRIBUTION_ID" ] && [ "$DISTRIBUTION_ID" != "None" ]; then
        echo "Invalidating CloudFront cache ($DISTRIBUTION_ID)..."
        aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths "/*" > /dev/null 2>&1
        echo "CloudFront invalidation started (takes ~30-60s)"
    fi
fi

# Display outputs
echo ""
echo "========================================"
echo "Deployment complete!"
echo "========================================"
echo ""
echo "Stack Outputs:"
if [ -f cdk-outputs.json ]; then
    cat cdk-outputs.json | grep -E "(CloudFrontUrl|ApiEndpoint|DocumentBucketName)" | sed 's/[",]//g'
fi
echo ""
echo "Next steps:"
echo "1. Upload a document: aws s3 cp your-doc.pdf s3://<DocumentBucketName>/ingest/"
echo "2. Access dashboard: Open CloudFrontUrl in your browser"
