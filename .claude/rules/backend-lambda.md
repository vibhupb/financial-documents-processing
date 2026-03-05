---
paths:
  - "lambda/**/*.py"
  - "lib/stacks/**/*.ts"
---
# Backend Lambda Development

## Code Style (Python)
- Follow PEP 8 style guide
- Use type hints for function signatures
- Document functions with docstrings
- Handle errors explicitly with try/except

## PII Security
- Use `safe_log()` for any logging that might contain PII
- Never `print()` raw financial data
- Use `pii_crypto.py` for KMS envelope encryption (AES-256-GCM per field)
- PII paths defined in plugin configs (`beneficialOwners[*].ssn`)

## Lambda Environment Variables
1. Add to CDK stack in `document-processing-stack.ts`:
```typescript
environment: {
  NEW_VAR: 'value',
},
```
2. Access in Lambda handler:
```python
new_var = os.environ.get('NEW_VAR')
```

## Key Design Decisions
- **PyPDF for text extraction**: Faster/cheaper than OCR for text-based PDFs; fallback to Textract for scanned
- **Content-Based Deduplication**: SHA-256 hash stored in DynamoDB GSI
- **Parallel Extraction**: Step Functions Parallel runs Queries, Tables, Forms concurrently
- **Blue/Green Step Functions**: ExtractionRouteChoice checks `extractionPlan` first, falls back to legacy
- **2GB Lambda memory** for Router/Normalizer/Extractor (1 vCPU for CPU-bound ops)
- **MAX_PARALLEL_WORKERS=30** for Textract (utilizes ~60% of 50 TPS quota)
