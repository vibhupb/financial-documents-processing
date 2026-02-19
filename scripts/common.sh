#!/bin/bash
# common.sh — Shared environment preamble for all project scripts
#
# Source this file at the top of every script:
#   source "$(dirname "$0")/common.sh"
#
# Provides:
#   - AWS environment validation and banner
#   - Helper functions: get_bucket_name, get_table_name, get_stack_output, run_python
#   - Color output: fail, success, info, warning
#   - Safety: confirm_action, --dry-run, --force flags

set -e
set -o pipefail

# ─── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Project Root ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR" && cd .. && pwd)"
# Handle case where common.sh is sourced from project root scripts/
if [ "$(basename "$SCRIPT_DIR")" = "scripts" ]; then
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
elif [ -f "$SCRIPT_DIR/../scripts/common.sh" ]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

# ─── Global Flags ─────────────────────────────────────────────
DRY_RUN=false
FORCE=false
VERBOSE=false

for arg in "$@"; do
    case "$arg" in
        --dry-run)  DRY_RUN=true ;;
        --force)    FORCE=true ;;
        --verbose)  VERBOSE=true ;;
    esac
done

# ─── Output Helpers ───────────────────────────────────────────

fail() {
    echo -e "${RED}✗ $1${NC}" >&2
    exit 1
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

info() {
    echo -e "${BLUE}→ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# ─── Tool Validation ──────────────────────────────────────────

command -v aws >/dev/null 2>&1 || fail "AWS CLI not installed. Install: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
command -v uv >/dev/null 2>&1 || fail "uv not installed. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"

# ─── AWS Environment ─────────────────────────────────────────

# Validate AWS credentials and extract identity
_AWS_IDENTITY_JSON=$(aws sts get-caller-identity --output json 2>/dev/null) || fail "AWS credentials not configured or expired. Check ~/.zshrc or run 'aws configure'."

AWS_ACCOUNT_ID=$(echo "$_AWS_IDENTITY_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['Account'])" 2>/dev/null)
AWS_IAM_ARN=$(echo "$_AWS_IDENTITY_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['Arn'])" 2>/dev/null)
AWS_REGION="${AWS_REGION:-us-west-2}"

if [ -z "$AWS_ACCOUNT_ID" ]; then
    fail "Could not determine AWS Account ID. Check credentials."
fi

# ─── Resource Helpers ─────────────────────────────────────────

get_bucket_name() {
    echo "financial-docs-${AWS_ACCOUNT_ID}-${AWS_REGION}"
}

get_table_name() {
    echo "financial-documents"
}

get_stack_output() {
    local output_key="$1"
    local outputs_file="$PROJECT_ROOT/cdk-outputs.json"

    # Try cdk-outputs.json first
    if [ -f "$outputs_file" ]; then
        local value
        value=$(python3 -c "
import json, sys
with open('$outputs_file') as f:
    outputs = json.load(f)
for stack in outputs.values():
    if isinstance(stack, dict) and '$output_key' in stack:
        print(stack['$output_key'])
        sys.exit(0)
sys.exit(1)
" 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$value" ]; then
            echo "$value"
            return 0
        fi
    fi

    # Fallback: CloudFormation exports
    local export_name="FinancialDoc${output_key}"
    local value
    value=$(aws cloudformation list-exports \
        --query "Exports[?Name=='${export_name}'].Value" \
        --output text \
        --region "$AWS_REGION" 2>/dev/null)

    if [ -n "$value" ] && [ "$value" != "None" ]; then
        echo "$value"
        return 0
    fi

    return 1
}

run_python() {
    uv run python "$@"
}

# ─── Safety ───────────────────────────────────────────────────

confirm_action() {
    local message="$1"
    if [ "$FORCE" = "true" ]; then
        return 0
    fi
    echo ""
    read -p "$(echo -e "${YELLOW}${message} (y/N): ${NC}")" -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        fail "Operation cancelled."
    fi
}

# ─── Banner ───────────────────────────────────────────────────

print_banner() {
    local script_name="$1"
    local python_version
    python_version=$(python3 --version 2>/dev/null | awk '{print $2}' || echo "unknown")
    local node_version
    node_version=$(node --version 2>/dev/null || echo "unknown")

    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD}Financial Documents Processing — ${script_name}${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "  AWS Account:  ${BOLD}${AWS_ACCOUNT_ID}${NC}"
    echo -e "  AWS Region:   ${AWS_REGION}"
    echo -e "  IAM Identity: ${AWS_IAM_ARN}"
    echo -e "  S3 Bucket:    $(get_bucket_name)"
    echo -e "  DynamoDB:     $(get_table_name)"
    echo -e "  Python:       ${python_version} (via uv)"
    echo -e "  Node.js:      ${node_version} (via nvm)"
    if [ "$DRY_RUN" = "true" ]; then
        echo -e "  Mode:         ${YELLOW}DRY RUN${NC}"
    fi
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}
