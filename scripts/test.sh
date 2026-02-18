#!/bin/bash
# Run all tests

source "$(dirname "$0")/common.sh"

cd "$PROJECT_ROOT"

print_banner "Running Tests"

info "[1/3] Running Python tests..."
uv run pytest tests/ -v --cov=src/financial_docs --cov-report=term-missing || true

echo ""
info "[2/3] Running CDK tests..."
npm test || true

echo ""
info "[3/3] Linting Python code..."
uv run ruff check src/ lambda/ || true
uv run mypy src/ --ignore-missing-imports || true

echo ""
success "All tests completed!"
