#!/bin/bash
# Deployment script for Financial Documents Processing

set -e

echo "========================================"
echo "Financial Documents Processing - Deploy"
echo "========================================"

# Check prerequisites
command -v npm >/dev/null 2>&1 || { echo "npm is required but not installed."; exit 1; }
command -v cdk >/dev/null 2>&1 || { echo "AWS CDK is required. Install with: npm install -g aws-cdk"; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "AWS CLI is required but not installed."; exit 1; }

# Install dependencies
echo ""
echo "[1/4] Installing dependencies..."
npm install

# Build Lambda layers
echo ""
echo "[2/4] Building Lambda layers..."
cd lambda/layers/pypdf
chmod +x build.sh
./build.sh
cd ../../..

# Build TypeScript
echo ""
echo "[3/4] Building TypeScript..."
npm run build

# Deploy
echo ""
echo "[4/4] Deploying to AWS..."
cdk deploy --all --require-approval never

echo ""
echo "========================================"
echo "Deployment complete!"
echo "========================================"
