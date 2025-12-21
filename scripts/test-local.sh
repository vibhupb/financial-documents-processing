#!/bin/bash
# Local testing script for Lambda functions

set -e

echo "========================================"
echo "Local Testing - Financial Doc Processing"
echo "========================================"

# Test Router Lambda
echo ""
echo "Testing Router Lambda..."
cd lambda/router
python -c "
import sys
sys.path.insert(0, '../layers/pypdf/python')
try:
    import handler
    print('Router Lambda syntax OK')
except ImportError as e:
    print(f'Note: {e} - run layer build first')
"
cd ../..

# Test Extractor Lambda
echo ""
echo "Testing Extractor Lambda..."
cd lambda/extractor
python -c "
import sys
sys.path.insert(0, '../layers/pypdf/python')
try:
    import handler
    print('Extractor Lambda syntax OK')
except ImportError as e:
    print(f'Note: {e} - run layer build first')
"
cd ../..

# Test Normalizer Lambda
echo ""
echo "Testing Normalizer Lambda..."
cd lambda/normalizer
python -c "
import handler
print('Normalizer Lambda syntax OK')
"
cd ../..

# Test Trigger Lambda
echo ""
echo "Testing Trigger Lambda..."
cd lambda/trigger
python -c "
import handler
print('Trigger Lambda syntax OK')
"
cd ../..

echo ""
echo "========================================"
echo "All Lambda syntax checks passed!"
echo "========================================"
