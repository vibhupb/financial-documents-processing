---
name: testing-toolkit
description: Comprehensive testing toolkit design reference — integration tests, Playwright E2E, compliance learning loop proof, plugin lifecycle testing
---
# Testing Toolkit Reference

## Design Doc
Full design: `docs/plans/2026-03-05-testing-toolkit-design.md`

## Test Coverage Matrix

| Capability | Integration Test | E2E Test | What It Proves |
|-----------|-----------------|----------|----------------|
| New plugin lifecycle | `test_plugin_lifecycle.py` | `test_plugin_rendering.py` | Plugin discovery → routing → extraction → normalization → UI rendering |
| Plugin enhancement | `test_plugin_enhancement.py` | — | Updated plugin fields appear on reprocess |
| PageIndex ↔ Extraction | `test_pageindex_summary.py` | — | Q&A answers match extracted values, no hallucination |
| Baseline CRUD | `test_compliance_baseline_crud.py` | `test_compliance_baseline_management.py` | Full lifecycle: draft → publish → archive |
| Compliance evaluation | `test_compliance_evaluation.py` | `test_compliance_evaluation_ui.py` | Verdicts + evidence + char-offset grounding |
| Reviewer override | `test_compliance_learning_loop.py` | `test_compliance_reviewer_override.py` | Override stored → badge changes |
| Few-shot learning (prompt) | `test_compliance_learning_loop.py` | — | Feedback injected into LLM prompt |
| Few-shot learning (score) | `test_compliance_learning_loop.py` | `test_compliance_learning_proof.py` | Score delta measurable after override |
| Multi-baseline | `test_compliance_multi_baseline.py` | — | Independent reports, no cross-contamination |
| Work queue badges | — | `test_compliance_work_queue.py` | Compliance column + color-coded scores |
| Evidence navigation | — | `test_compliance_evidence_navigation.py` | Click evidence → PDF jumps to page |

## Dependencies
```toml
# pyproject.toml [project.optional-dependencies]
test-toolkit = ["pytest-playwright>=0.5.0", "pytest-html>=4.0.0", "requests>=2.31.0"]
```

## Quick Start
```bash
uv pip install -e ".[test-toolkit]"
uv run playwright install chromium
./scripts/test-toolkit.sh
```
