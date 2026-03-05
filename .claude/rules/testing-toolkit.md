---
paths:
  - "tests/integration/**"
  - "tests/e2e/**"
  - "tests/fixtures/**"
  - "scripts/test-toolkit.sh"
---
# Testing Toolkit Rules

## Test Structure
- `tests/integration/` — Real-AWS pytest tests (no mocking)
- `tests/e2e/` — Playwright browser tests with Page Object Models
- `tests/fixtures/` — Synthetic test data (PDFs, plugin configs, baselines)
- `scripts/test-toolkit.sh` — Orchestrator script

## Integration Test Patterns
- All tests use fixtures from `conftest.py`: `stack_config`, `api`, `upload_and_wait`, `create_published_baseline`
- Stack config auto-discovered from CloudFormation outputs
- `upload_and_wait` polls every 10s with 5-min timeout
- Cleanup fixture auto-archives baselines after each test
- Use `@pytest.mark.integration` + scenario-specific markers

## Playwright E2E Patterns
- Page Object Models in `tests/e2e/pages/` — one class per page
- `authenticated_page` fixture handles Cognito login
- Always take screenshots as evidence: `page.screenshot(path=f"reports/screenshots/{name}.png")`
- Use `@pytest.mark.e2e` marker

## Running Tests
```bash
./scripts/test-toolkit.sh                # All tests
./scripts/test-toolkit.sh --integration  # API-level only
./scripts/test-toolkit.sh --e2e          # Browser only
./scripts/test-toolkit.sh -k compliance  # Compliance subset
uv run pytest tests/integration/ -v      # Direct pytest
```

## Key Fixtures
| Fixture | Scope | Returns |
|---------|-------|---------|
| `stack_config` | session | dict: api_url, bucket_name, table names |
| `api` | session | requests.Session with base_url |
| `upload_and_wait` | function | callable → (doc_id, status, duration) |
| `create_published_baseline` | function | callable → baseline_id |
| `authenticated_page` | function | Playwright page with auth |

## Compliance Learning Loop Test
The most important test (`test_compliance_learning_loop.py`) proves:
1. Baseline scores recorded (RUN 1)
2. Reviewer override submitted → feedback stored
3. Prompt injection verified (few-shot example in LLM prompt)
4. Re-evaluation produces different scores (RUN 2)
5. Comparison report saved to `reports/learning-loop-comparison.json`
