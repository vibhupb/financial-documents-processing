#!/bin/bash
# Deployment script for Financial Documents Processing

set -e

echo "========================================"
echo "Financial Documents Processing - Deploy"
echo "========================================"

# Change to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check prerequisites
echo ""
echo "[0/6] Checking prerequisites..."
command -v npm >/dev/null 2>&1 || { echo "npm is required but not installed."; exit 1; }
command -v cdk >/dev/null 2>&1 || { echo "AWS CDK is required. Install with: npm install -g aws-cdk"; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "AWS CLI is required but not installed."; exit 1; }

# Check for UV (Python package manager)
if command -v uv >/dev/null 2>&1; then
    PYTHON_PKG_MGR="uv"
    echo "Using UV for Python package management"
else
    PYTHON_PKG_MGR="pip"
    echo "UV not found, using pip for Python package management"
fi

# Install Node dependencies
echo ""
echo "[1/6] Installing Node.js dependencies..."
npm install

# Setup Python environment
echo ""
echo "[2/6] Setting up Python environment..."
if [ "$PYTHON_PKG_MGR" = "uv" ]; then
    uv sync --dev
else
    python3 -m pip install -e ".[dev]" --quiet
fi

# Build Lambda layers
echo ""
echo "[3/6] Building Lambda layers..."
cd lambda/layers/pypdf
chmod +x build.sh
./build.sh
cd "$PROJECT_ROOT"

# Build TypeScript
echo ""
echo "[4/6] Building TypeScript CDK..."
npm run build

# Build Frontend
echo ""
echo "[5/6] Building Frontend..."
cd frontend
npm install
npm run build
cd "$PROJECT_ROOT"

# Deploy
echo ""
echo "[6/6] Deploying to AWS..."
cdk deploy --all --require-approval never --outputs-file cdk-outputs.json

# Deploy frontend to S3 (after CDK deployment)
echo ""
echo "Deploying frontend to S3..."
FRONTEND_BUCKET=$(cat cdk-outputs.json | grep FrontendBucketName | cut -d'"' -f4)
if [ -n "$FRONTEND_BUCKET" ]; then
    aws s3 sync frontend/dist/ "s3://$FRONTEND_BUCKET/" --delete
    echo "Frontend deployed to S3 bucket: $FRONTEND_BUCKET"
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
