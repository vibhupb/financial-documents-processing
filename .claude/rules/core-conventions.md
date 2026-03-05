# Core Conventions

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| CDK Constructs | PascalCase | `DocumentBucket` |
| Lambda Functions | kebab-case | `doc-processor-router` |
| Environment Variables | SCREAMING_SNAKE | `BUCKET_NAME` |
| Python functions | snake_case | `extract_page_snippets` |
| TypeScript functions | camelCase | `createStateMachine` |
| React Components | PascalCase | `DocumentViewer` |
| CSS Classes | kebab-case | `btn-primary` |

## AWS Resource Naming

- S3 Bucket: `financial-docs-{account}-{region}`
- S3 Frontend Bucket: `financial-docs-frontend-{account}-{region}`
- DynamoDB Table: `financial-documents`
- Step Functions: `financial-doc-processor`
- Lambda: `doc-processor-{function}`
- API Gateway: `doc-processor-api`
- CloudFront: For frontend distribution
- DynamoDB (Compliance): `compliance-baselines`, `compliance-reports`, `compliance-feedback`

## DynamoDB Gotcha

DynamoDB rejects Python `float` types — always wrap numeric values with `Decimal(str(value))` before `put_item`/`update_item`. This applies to `confidenceThreshold` and any other numeric fields.

## AI Assistant Rules

### DO:
- **Use plugin architecture** for new document types (never hardcode in router/normalizer/frontend)
- **All scripts must source `common.sh`** for AWS env validation, `uv run python`, and helpers
- Maintain cost-optimization as a primary concern (Router Pattern)
- Use `safe_log()` for any logging that might contain PII — never `print()` raw financial data
- Follow the established code patterns and naming conventions
- Keep Lambda functions focused and single-purpose
- Ensure error handling is comprehensive
- Consider audit trail requirements for financial compliance

### DON'T:
- **Don't add document-type-specific code to router, normalizer, or frontend** — use plugin configs
- **Don't use bare `python` or `python3`** — always use `uv run python` via `run_python()`
- **Don't deploy frontend with `--skip-build`** — always rebuild before syncing to S3
- Don't introduce dependencies without justification
- Don't store PII in logs (use safe_log module)
- Don't hardcode AWS account IDs or regions (use `common.sh` helpers)
- Don't skip error handling in Lambda functions

### When Adding Features:
1. **New document type?** Create 2 files: `types/{type}.py` + `prompts/{type}.txt`
2. Consider impact on cost (is there a cheaper way?)
3. Update CLAUDE.md if architecture changes
4. Ensure backward compatibility with existing documents
5. Run `uv run pytest tests/` to verify plugin registry tests pass
