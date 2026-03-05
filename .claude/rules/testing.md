---
paths:
  - "tests/**"
  - "frontend/**/*.test.*"
  - "frontend/**/*.spec.*"
---
# Testing Guidelines

## Unit Tests
```bash
npm test                    # CDK tests
uv run pytest tests/        # Python tests (47 plugin + 33 compliance)
cd frontend && npx vitest run  # Frontend tests (MUST run from frontend/ dir)
```

## Integration Testing
```bash
./scripts/deploy.sh
./scripts/upload-test-doc.sh path/to/test.pdf
aws stepfunctions list-executions --state-machine-arn <arn>
```

## Compliance E2E Testing
```bash
./scripts/test-compliance-e2e.sh  # baseline → requirements → publish → upload → evaluate
```

## Common Gotchas
- Frontend tests **MUST run from `frontend/` directory** -- vitest jsdom configured in `frontend/vite.config.ts`
- "document is not defined" error = wrong directory
- Always use `uv run python` for Python test commands (never bare `python`)
