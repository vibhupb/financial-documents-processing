#!/bin/bash
# Development environment setup script

set -e

echo "========================================"
echo "Financial Documents - Dev Setup"
echo "========================================"

# Change to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check for UV
if ! command -v uv >/dev/null 2>&1; then
    echo ""
    echo "Installing UV (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

echo ""
echo "[1/5] Installing Node.js dependencies..."
npm install

echo ""
echo "[2/5] Setting up Python environment with UV..."
uv sync --dev

echo ""
echo "[3/5] Installing pre-commit hooks..."
if [ -f .pre-commit-config.yaml ]; then
    uv run pre-commit install
fi

echo ""
echo "[4/5] Building Lambda layers..."
cd lambda/layers/pypdf
chmod +x build.sh
./build.sh
cd "$PROJECT_ROOT"

echo ""
echo "[5/5] Setting up frontend..."
cd frontend
npm install
cd "$PROJECT_ROOT"

echo ""
echo "========================================"
echo "Development environment ready!"
echo "========================================"
echo ""
echo "Available commands:"
echo "  npm run build        - Build CDK TypeScript"
echo "  npm run synth        - Synthesize CloudFormation"
echo "  npm run deploy       - Deploy to AWS"
echo "  uv run pytest        - Run Python tests"
echo "  cd frontend && npm run dev  - Start frontend dev server"
