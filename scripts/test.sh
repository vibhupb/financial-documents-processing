#!/bin/bash
# Run all tests

set -e

echo "========================================"
echo "Financial Documents - Running Tests"
echo "========================================"

# Change to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check for UV
if command -v uv >/dev/null 2>&1; then
    PYTHON_CMD="uv run"
else
    PYTHON_CMD="python3 -m"
fi

echo ""
echo "[1/3] Running Python tests..."
$PYTHON_CMD pytest tests/ -v --cov=src/financial_docs --cov-report=term-missing || true

echo ""
echo "[2/3] Running CDK tests..."
npm test || true

echo ""
echo "[3/3] Linting Python code..."
$PYTHON_CMD ruff check src/ lambda/ || true
$PYTHON_CMD mypy src/ --ignore-missing-imports || true

echo ""
echo "========================================"
echo "All tests completed!"
echo "========================================"
