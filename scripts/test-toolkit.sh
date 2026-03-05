#!/bin/bash
# Testing Toolkit Orchestrator
# Usage:
#   ./scripts/test-toolkit.sh                    # Run all tests
#   ./scripts/test-toolkit.sh --integration      # Integration tests only
#   ./scripts/test-toolkit.sh --e2e              # Playwright E2E only
#   ./scripts/test-toolkit.sh -k compliance      # Only compliance-related tests
#   ./scripts/test-toolkit.sh --headed           # Playwright with visible browser

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

REPORTS_DIR="$PROJECT_ROOT/reports"
SCREENSHOTS_DIR="$REPORTS_DIR/screenshots"
STACK_NAME="${STACK_NAME:-FinancialDocProcessingStack}"
MODE="${1:---all}"

# Setup
mkdir -p "$REPORTS_DIR" "$SCREENSHOTS_DIR"

echo "============================================"
echo "  Testing Toolkit"
echo "============================================"
echo "Stack:    $STACK_NAME"
echo "Mode:     $MODE"
echo "Reports:  $REPORTS_DIR"
echo ""

# Verify stack deployed
if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME" > /dev/null 2>&1; then
    echo "ERROR: Stack '$STACK_NAME' not deployed."
    echo "Run: ./scripts/deploy.sh first"
    exit 1
fi
echo "Stack verified."

PYTEST_COMMON_ARGS="-v --tb=short"
EXIT_CODE=0

run_integration() {
    echo ""
    echo "=== Integration Tests ==="
    run_python -m pytest tests/integration/ \
        -m integration \
        --html="$REPORTS_DIR/integration.html" --self-contained-html \
        $PYTEST_COMMON_ARGS "$@" || EXIT_CODE=$?
}

run_e2e() {
    echo ""
    echo "=== E2E Tests (Playwright) ==="
    SCREENSHOT_DIR="$SCREENSHOTS_DIR" \
    run_python -m pytest tests/e2e/ \
        -m e2e \
        --html="$REPORTS_DIR/e2e.html" --self-contained-html \
        $PYTEST_COMMON_ARGS "$@" || EXIT_CODE=$?
}

case "$MODE" in
    --integration)
        run_integration "${@:2}"
        ;;
    --e2e)
        run_e2e "${@:2}"
        ;;
    --all)
        run_integration "${@:2}"
        run_e2e "${@:2}"
        ;;
    -k)
        # Pass -k filter to both suites
        run_integration "$@"
        run_e2e "$@"
        ;;
    --headed)
        PLAYWRIGHT_HEADLESS=false run_e2e "${@:2}"
        ;;
    -h|--help)
        echo "Usage: $0 [--all|--integration|--e2e|-k <filter>|--headed|-h]"
        exit 0
        ;;
    *)
        echo "Unknown option: $MODE"
        echo "Usage: $0 [--all|--integration|--e2e|-k <filter>|--headed|-h]"
        exit 1
        ;;
esac

echo ""
echo "============================================"
echo "  Results"
echo "============================================"

# Show reports
for report in "$REPORTS_DIR"/*.html; do
    [ -f "$report" ] && echo "  Report: $report"
done

# Show screenshots
SCREENSHOT_COUNT=$(find "$SCREENSHOTS_DIR" -name "*.png" 2>/dev/null | wc -l | tr -d ' ')
echo "  Screenshots: $SCREENSHOT_COUNT captured in $SCREENSHOTS_DIR/"

# Show learning loop comparison
if [ -f "$REPORTS_DIR/learning-loop-comparison.json" ]; then
    echo "  Learning loop: $REPORTS_DIR/learning-loop-comparison.json"
fi

echo ""

# Open report on macOS
if [[ "$(uname)" == "Darwin" ]]; then
    for report in "$REPORTS_DIR"/*.html; do
        [ -f "$report" ] && open "$report" 2>/dev/null || true
        break
    done
fi

exit $EXIT_CODE
