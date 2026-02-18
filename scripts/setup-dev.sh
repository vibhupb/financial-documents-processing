#!/bin/bash
# Development environment setup script

source "$(dirname "$0")/common.sh"

cd "$PROJECT_ROOT"

print_banner "Dev Setup"

echo ""
info "[1/5] Installing Node.js dependencies..."
npm install

echo ""
info "[2/5] Setting up Python environment with UV..."
uv sync --dev

echo ""
info "[3/5] Installing pre-commit hooks..."
if [ -f .pre-commit-config.yaml ]; then
    uv run pre-commit install
fi

echo ""
info "[4/5] Building Lambda layers..."
cd lambda/layers/pypdf
chmod +x build.sh
./build.sh
cd "$PROJECT_ROOT"

echo ""
info "[5/5] Setting up frontend..."
cd frontend
npm install
cd "$PROJECT_ROOT"

echo ""
success "Development environment ready!"
echo ""
info "Available commands:"
echo "  npm run build        - Build CDK TypeScript"
echo "  npm run synth        - Synthesize CloudFormation"
echo "  npm run deploy       - Deploy to AWS"
echo "  uv run pytest        - Run Python tests"
echo "  cd frontend && npm run dev  - Start frontend dev server"
