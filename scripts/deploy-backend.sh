#!/bin/bash
# Deploy backend (CDK stack) to AWS
#
# Usage: ./scripts/deploy-backend.sh [--force] [--dry-run]

source "$(dirname "$0")/common.sh"

print_banner "Deploy Backend (CDK)"

cd "$PROJECT_ROOT"

confirm_action "Deploy CDK stack to AWS Account $AWS_ACCOUNT_ID in $AWS_REGION?"

# Prerequisites
command -v cdk >/dev/null 2>&1 || fail "AWS CDK not installed. Run: npm install -g aws-cdk"

# Build layers
info "[1/5] Building Lambda layers..."
cd lambda/layers/pypdf && chmod +x build.sh && ./build.sh && cd "$PROJECT_ROOT"

# Python deps
info "[2/5] Syncing Python environment..."
uv sync --dev

# Build TypeScript
info "[3/5] Building CDK TypeScript..."
npm run build

# CDK diff preview
info "[4/5] CDK diff preview..."
npx cdk diff --all 2>&1 | grep -E "^\[+\]|\[-\]|\[~\]|^Stack|Resources" | head -20
echo ""

if [ "$DRY_RUN" = "true" ]; then
    info "[DRY RUN] Skipping actual deployment"
    exit 0
fi

# Deploy
info "[5/5] Deploying CDK stack..."
npx cdk deploy --all --require-approval never --outputs-file cdk-outputs.json

if [ -f cdk-outputs.json ]; then
    success "Backend deployed!"
    echo ""
    info "Stack outputs:"
    uv run python -c "
import json
with open('cdk-outputs.json') as f:
    for stack, outputs in json.load(f).items():
        for k, v in outputs.items():
            if any(x in k for x in ['Endpoint', 'Url', 'Bucket', 'Table', 'Arn', 'UserPool', 'PIIEncryption']):
                print(f'  {k}: {v}')
"
else
    warning "cdk-outputs.json not found - deployment may have issues"
fi
