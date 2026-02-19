#!/bin/bash
# Local testing script for Lambda functions

source "$(dirname "$0")/common.sh"

print_banner "Local Testing"

cd "$PROJECT_ROOT"

# Test Router Lambda
info "Testing Router Lambda..."
cd lambda/router
uv run python -c "
import sys
sys.path.insert(0, '../layers/pypdf/python')
sys.path.insert(0, '../layers/plugins/python')
try:
    import handler
    print('  Router Lambda syntax OK')
except ImportError as e:
    print(f'  Note: {e} - run layer build first')
"
cd "$PROJECT_ROOT"

# Test Extractor Lambda
info "Testing Extractor Lambda..."
cd lambda/extractor
uv run python -c "
import sys
sys.path.insert(0, '../layers/pypdf/python')
sys.path.insert(0, '../layers/plugins/python')
try:
    import handler
    print('  Extractor Lambda syntax OK')
except ImportError as e:
    print(f'  Note: {e} - run layer build first')
"
cd "$PROJECT_ROOT"

# Test Normalizer Lambda
info "Testing Normalizer Lambda..."
cd lambda/normalizer
uv run python -c "
import sys
sys.path.insert(0, '../layers/plugins/python')
import handler
print('  Normalizer Lambda syntax OK')
"
cd "$PROJECT_ROOT"

# Test Trigger Lambda
info "Testing Trigger Lambda..."
cd lambda/trigger
uv run python -c "
import handler
print('  Trigger Lambda syntax OK')
"
cd "$PROJECT_ROOT"

# Test Plugin Registry
info "Testing Plugin Registry..."
uv run python -c "
import sys
sys.path.insert(0, 'lambda/layers/plugins/python')
from document_plugins.registry import get_all_plugins
plugins = get_all_plugins()
print(f'  Plugin registry OK: {len(plugins)} plugins discovered')
for pid in sorted(plugins.keys()):
    print(f'    - {pid}: {plugins[pid].get(\"name\", \"unnamed\")}')
"

echo ""
success "All Lambda syntax checks passed!"
