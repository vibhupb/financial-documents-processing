---
title: "refactor: Plugin Architecture for Financial Document Processing Platform"
type: refactor
date: 2026-02-17
brainstorm: docs/brainstorms/2026-02-17-financial-document-processing-plugin-architecture-brainstorm.md
---

## Enhancement Summary

**Deepened on:** 2026-02-17
**Deepened (Round 2) on:** 2026-02-17
**Deepened (Round 3) on:** 2026-02-17
**Deepened (Round 4) on:** 2026-02-17
**Deepened (Round 5) on:** 2026-02-17
**Deepened (Round 6) on:** 2026-02-18
**Deepened (Round 7) on:** 2026-02-18
**Deepened (Round 8) on:** 2026-02-18
**Deepened (Round 9) on:** 2026-02-18
**Deepened (Round 10) on:** 2026-02-18
**Sections enhanced:** 7 phases + architecture + acceptance criteria (Round 1); Phases 1, 3, 4, 6 deep implementation details (Round 2); Phases 0, 2, 5, 7 deep implementation details (Round 3); Cross-cutting concerns, testing strategy, BSA extraction accuracy (Round 4); Generated implementation files — plugin contract+registry, CDK Map state replacement, normalization prompt templates (Round 5); Generated all 3 plugin config files + 3 normalization prompt templates — complete plugin layer (Round 6); Implementation-ready code validated against real CDK v2 API, complete Lambda handler refactoring designs, golden file test infrastructure (Round 7); Loan agreement plugin config, normalizer handler refactoring, PII encryption implementation, complete CDK stack annotated diff (Round 8); Complete function implementations for router+normalizer handlers, loan agreement prompt template, frontend Cognito auth integration (Round 9); Trigger Lambda analysis (no changes), frontend BSA components, DynamoDB schema evolution, deployment runbook, E2E test matrix, script environment standardization (Round 10)
**Research agents used:** Architecture Strategist, Security Sentinel, Performance Oracle, Pattern Recognition Specialist, Best Practices Researcher (Round 1); Plugin Registry TypedDict Designer, CDK Map State Researcher, Textract FORMS/Checkbox Specialist, KMS PII Encryption Architect (Round 2); Normalizer Prompt Architect, Frontend BSA Component Designer, Router Dynamic Classification Specialist, Golden File Testing Architect (Round 3); Cross-Cutting Concerns Analyst, Testing Strategy Architect, BSA Extraction Accuracy Specialist (Round 4); Plugin Config File Generator, CDK Map State Code Generator, BSA Normalization Prompt Generator (Round 5); Credit Agreement Plugin Config Writer, BSA Profile Plugin Config Writer, Normalization Prompt Template Writer (Round 6); CDK Map State API Validator, Router Handler Refactoring Specialist, Extractor Handler Refactoring Specialist, Golden File Test Infrastructure Designer (Round 7); Loan Agreement Plugin Config Writer, Normalizer Handler Refactoring Specialist, PII Encryption Implementation Specialist, CDK Stack Complete Diff Generator (Round 8); Loan Agreement Prompt Template Writer, Frontend Cognito Integration Designer, Router Handler Implementation Specialist, Normalizer Handler Implementation Specialist (Round 9); Trigger Lambda Plugin Analyst, Frontend BSA Component Designer, DynamoDB Schema Evolution Analyst, Deployment Runbook Designer, E2E Test Matrix Specialist, Script Environment Standardization Specialist (Round 10)

### Key Improvements

1. **Plugin contract formalized** — Added TypedDict hierarchy requirement with per-section extraction configs, Textract queries, and JSON path-based PII field markers (Architecture + Pattern agents)
2. **Security hardening prerequisites identified** — 2 CRITICAL findings: API has zero authentication and PII is logged to CloudWatch in plaintext. Both must be addressed before Phase 6 (Security agent)
3. **Performance optimizations specified** — KMS envelope encryption (1 API call vs 12), parallel FORMS extraction for BSA, 256KB payload size budgeting for Map state (Performance agent)
4. **~930 lines of duplicated code mapped** — Exact locations identified for consolidation during refactor: 4 identical table extraction branches, 2 identical section identification algorithms, 3 copies of classification keywords (Pattern agent)
5. **Phase 0 added** — Golden file capture as a blocking prerequisite with explicit task list
6. **Phase 6 prerequisites added** — API authentication and PII log sanitization must happen before encrypted data flows through the system
7. **Implementation files generated (Round 5)** — Complete `contract.py` (170 lines, 10 TypedDicts), `registry.py` (144 lines, auto-discovery), `common_preamble.txt` (47 lines, shared normalization rules), `common_footer.txt` (18 lines, critical instructions). CDK Map state replacement code produced with blue/green Choice, per-iteration error handling, S3 intermediate storage.
8. **Complete plugin layer generated (Rounds 5-6)** — All 10 core files written to disk (3,090 lines total):
   - `contract.py` (169 lines): 10 TypedDicts forming the plugin contract hierarchy
   - `registry.py` (144 lines): Auto-discovery with 6 public functions, `pkgutil.iter_modules` pattern
   - `types/credit_agreement.py` (914 lines): 7 sections, 153 Textract queries migrated from extractor handler, 19 classification keywords, full output schema
   - `types/bsa_profile.py` (390 lines): Single FORMS+TABLES section, 5 PII path markers with array wildcards, 200 DPI for handwritten forms, $0.065/page cost
   - `types/loan_package.py` (478 lines): 3 sub-document sections (promissory_note queries, closing_disclosure queries+tables, form_1003 FORMS)
   - `prompts/credit_agreement.txt` (302 lines): 9 normalization rules, field-by-field instructions, full JSON schema with `{{`/`}}` escaping
   - `prompts/bsa_profile.txt` (247 lines): Checkbox confidence tiers, SELECTION_ELEMENT interpretation, beneficial owner array rules, PII handling notes
   - `prompts/loan_package.txt` (382 lines): Sub-document normalization with promissory note, closing disclosure, and Form 1003 rules
   - `prompts/common_preamble.txt` (47 lines) + `prompts/common_footer.txt` (17 lines): Shared normalization infrastructure
9. **Implementation-ready code validated (Round 7)** — CDK Map state API verified against real `aws-cdk-lib` v2 source (15 findings: 10 validated correct, 5 corrections needed). Complete handler refactoring designs with function signatures, line-by-line diff strategies, and risk analysis. Key findings:
   - **CDK:** `sfn.Chain(this, id)` constructor doesn't exist; use `LambdaInvoke` directly with `itemProcessor()`. `addRetry` overlaps `retryOnServiceExceptions` (compound retries). Round 5 `itemSelector` (nested `sectionConfig.$`) is correct over Round 2 (flat fields).
   - **Router (CRITICAL):** `loan_agreement` ≠ `loan_package` — these are different document types. `LOAN_AGREEMENT_SECTIONS` (275 lines) has no plugin and must be retained. Net Phase 2 change: -103 lines. 7 risk areas including BSA-cannot-work-in-dual-mode.
   - **Extractor:** 981 lines (41%) of dead code identified. Generic `extract_section()` replaces 3 hardcoded extraction functions. Complete `process_pages_forms_parallel()` and SELECTION_ELEMENT bug fix code.
   - **Golden Files:** Complete capture/compare/pytest infrastructure design. 24 IGNORE_PATHS, dual numeric tolerance (0.001/0.0001), order-insensitive arrays. No external dependencies (stdlib only). 10-step Phase 0 execution checklist.
10. **Complete implementation coverage (Round 8)** — All remaining gaps filled:
   - **Loan Agreement plugin**: Complete `types/loan_agreement.py` with 8 sections, 63 Textract queries, `_extractedCodes` banking system integration, $0.18-$0.60 cost budget. Resolves P0 `loan_agreement ≠ loan_package` gap.
   - **Normalizer refactoring**: Complete `build_normalization_prompt()` function (~80 lines), `resolve_s3_extraction_refs()` function, dead code analysis (1,342 lines / 52% removable), 5-step diff strategy. Normalizer shrinks from ~2,577 to ~1,575 lines.
   - **PII encryption**: Complete `safe_log.py` (PII-aware logging with redaction), `pii_crypto.py` (envelope encryption using KMS GenerateDataKey), `encrypt-existing-pii.py` migration script, `decrypt-for-rollback.py` rollback script, 28-step deployment checklist.
   - **CDK stack diff**: Complete construct inventory (45+ constructs mapped with line ranges), Phase 3 annotated diff (blue/green Choice + Map state + plugins layer), Phase 4 S3 lifecycle rule, Phase 6 constructs (KMS key, Cognito User Pool + 3 groups, audit DynamoDB table, API Gateway authorizer). Full dependency graph and deployment safety analysis per phase.
11. **Implementation-complete function bodies (Round 9)** — All critical function implementations now have complete, tested code:
   - **Loan Agreement prompt template**: Complete `prompts/loan_agreement.txt` (~500 lines) with 55 extraction fields, 8 coded field enumerations (instrumentType, interestRateType, rateIndex, rateCalculationMethod, billingType, billingFrequency, prepaymentIndicator, currency), default value rules, cross-reference validation (loanAmount × interestRate ≈ annualInterestCost), `{{`/`}}` JSON escaping. Covers all 27 field definitions from `build_loan_agreement_prompt()` (handler lines 321-728).
   - **Router handler**: Complete function bodies for 6 new functions + refactored `lambda_handler`. `build_classification_prompt()` builds dynamic prompt from plugin registry. `identify_sections()` with `_evaluate_bonus_rule()` handles keyword_density scoring. `build_extraction_plan()` supports 3 strategies (target_all_pages, section_names, keyword_density). `_resolve_plugin()` uses 3-strategy resolution (direct match → section name match → legacy fallback). Credit Agreement reclassification to loan_agreement preserved. Dead code analysis: 5 functions deletable immediately, 2 kept temporarily until loan_agreement plugin.
   - **Normalizer handler**: Complete function bodies for 5 new functions + `_handle_plugin_path()`. `resolve_s3_extraction_refs()` uses ThreadPoolExecutor for parallel S3 downloads. `build_normalization_prompt()` implements 4-layer composable architecture. `invoke_bedrock_normalize()` returns partial result on JSON parse failure instead of crashing. `apply_field_overrides()` uses dot-path navigation for plugin-defined defaults. `_build_plugin_summary()` generates per-type summaries. Full DynamoDB write integration preserving `extractedData = normalized_data['loanData']` mapping.
   - **Frontend Cognito**: Complete `auth.ts` (AWS Amplify v6), `AuthContext.tsx` (React context + `useAuth` hook), `Login.tsx` (form with Cognito challenge handling), modified `api.ts` (Authorization header injection + 401 redirect), modified `App.tsx` (ProtectedRoute + RoleGuard). Role-based access matrix: Viewer=read-only, Reviewer=upload+review, Admin=all. PII masking is server-side (backend returns masked values for Viewer role). ReviewDocument.tsx reviewer name auto-populated from Cognito identity.
12. **Operational readiness validated (Round 10)** — All deployment, testing, schema, and scripting gaps closed:
   - **Trigger Lambda**: Confirmed ZERO changes needed across all phases — fully decoupled from plugin architecture. Input/output contract (`documentId`, `bucket`, `key`, `contentHash`, `size`, `uploadedAt`) passes through Step Functions unchanged.
   - **DynamoDB schema**: 4 new attributes (`pluginId`, `pluginVersion`, `_pii_envelope`, `retentionPolicy`) with backward-compatible defaults. Multi-tier TTL (365d/3yr/7yr). 2 new GSIs (`PluginIdIndex`, `RetentionPolicyIndex`). One-time backfill script. No breaking changes.
   - **Frontend BSA**: 8 new components designed (BSAProfileFields, BeneficialOwnerCard, RiskAssessmentPanel, BooleanFlag, PIIIndicator, GenericDataFields). TypeScript interfaces for BSAProfile, PluginRegistry, FieldDefinition. PII masking is server-side only.
   - **Deployment runbook**: 8-phase runbook with exact CLI commands, pre/post checks, rollback procedures, go/no-go criteria, CloudWatch monitoring queries. Phase grouping: 0 (independent), 1-2 (low risk), 3-4 (atomic), 5 (independent), 6 (HIGH risk, irreversible), 7 (depends on 3).
   - **E2E test matrix**: 30+ test cases across 6 phase transitions. 10-step Phase 0 golden file capture checklist. 24 IGNORE_PATHS, dual numeric tolerance, order-insensitive arrays. 7 missing test documents identified.
   - **Script standardization**: `scripts/common.sh` with 11 helper functions, AWS identity validation, environment banners, `uv run python`. 8 new scripts for phase deployment, golden files, DynamoDB backfill, PII encryption/rollback. Safety guards: `--dry-run`, `--force`, double confirmation, account validation.

### Critical Findings Requiring Plan Adjustments

| Priority | Finding | Source | Plan Impact |
|----------|---------|--------|-------------|
| P0 | API Gateway has zero authentication — decrypted PII will be publicly accessible | Security | Add auth prerequisite before Phase 6 |
| P0 | PII logged to CloudWatch in plaintext across all Lambda handlers | Security | Add log sanitization task |
| P1 | Plugin contract needs per-section query lists (300+ Textract queries currently in CDK) | Architecture | Expand Phase 1 contract definition |
| P1 | Map state 256KB payload limit — combined extraction results can exceed this | Architecture + Performance | Add S3 intermediate storage in Phase 4 |
| P1 | Need `process_pages_forms_parallel()` for BSA multi-page extraction | Performance | Add to Phase 4 tasks |
| P2 | Use KMS envelope encryption, not per-field direct calls (60-180ms → 10-20ms) | Performance | Update Phase 6 approach |
| P2 | Existing Form 1003 SSN/DOB already stored unencrypted in DynamoDB | Security | Add retroactive encryption task |
| P2 | pii_fields needs JSON path patterns for nested arrays (beneficial owners) | Security | Update plugin contract |
| P1 | `toleratedFailurePercentage` only available on `DistributedMap`, not `Map` | CDK Map Research | Use per-iteration `addCatch` instead |
| P1 | `extract_tables()` also drops SELECTION_ELEMENT blocks (same bug as forms) | Textract Research | Fix both functions in Phase 4 |
| P1 | BSA needs FORMS + TABLES combined ($0.065/page) for checkboxes in table cells | Textract Research | Update cost projection to ~$0.36 |
| P2 | FinCEN BSA/KYC requires 5-year data retention + access audit trail | KMS/PII Research | Add DynamoDB audit table + S3 Object Lock |
| P2 | Cognito User Pool with Admin/Reviewer/Viewer groups needed for RBAC | KMS/PII Research | Add CDK code to Phase 6 prerequisites |
| P1 | Router needs dual-format output (extractionPlan + legacy keys) during transition | Router Research | Add `add_backward_compatible_keys()` to Phase 2 |
| P1 | 305 Textract queries across CDK + extractor must migrate to plugin configs | Router Research | Add query migration subtask to Phase 2 |
| P2 | Golden file comparison needs numeric tolerance (0.001 financial, 0.0001 rates) and order-insensitive arrays | Golden File Research | Complete compare.py with field-level diff |
| P2 | LLM non-determinism: validation notes, audit rawValue, token counts all vary between runs | Golden File Research | Add IGNORE_PATHS + SOFT_MATCH_PATHS to compare.py |
| P2 | Normalizer has 3 prompt builders totaling ~700 lines — need composable fragment approach, not monolithic templates | Normalizer Research | Use schema-driven field instructions + plugin-specific fragments |
| P2 | Frontend needs PII masking, BooleanFlag component, collapsible BeneficialOwnerCard, GenericDataFields fallback | Frontend Research | Full component hierarchy for Phase 7 |
| P0 | 266 `print()` statements across Lambdas — 6 CRITICAL log PII (SSN, extracted financial data) to CloudWatch | Cross-Cutting Concerns | Replace all with `safe_log()` before Phase 6 |
| P1 | Phase 6 has HIGH rollback risk — already-encrypted DynamoDB records need decryption migration script | Cross-Cutting Concerns | Prepare migration script before deploying Phase 6 |
| P1 | Phases 3+4 must deploy atomically — Map state and extractor event format are coupled | Cross-Cutting Concerns | Two-step deploy: Phase 2 first (dual-format), then Phases 3+4 together |
| P1 | Step Functions log level `ALL` logs full state I/O including extracted PII | Cross-Cutting Concerns | Switch to `ERROR` level before Phase 6 |
| P2 | SIGNATURES needed only on page 5 (certification) — saves $0.060/doc | BSA Extraction Research | Limit SIGNATURES feature to last page in BSA plugin config |
| P2 | Current 150 DPI may be insufficient for handwritten BSA forms — recommend 200 DPI per plugin config | BSA Extraction Research | Add `render_dpi` to plugin extraction config |
| P2 | QUERIES not needed for BSA initial implementation — FORMS sufficient for standardized KYC labels | BSA Extraction Research | Defer QUERIES as targeted enhancement if accuracy gaps found |
| P2 | Test documents are in `docs/` not `test-documents/` — plan references non-existent directory | Testing Strategy | Update all test references to use `docs/` paths |
| P2 | No scanned/handwritten BSA test PDF exists — must create one for OCR fallback testing | Testing Strategy | Create by printing + scanning BSA form with handwritten entries |
| P1 | Generated `contract.py` uses `NotRequired` import (Python 3.11+) but Lambda runs 3.13 — verify runtime | Plugin Config Generator | Confirm Python 3.13 runtime; `NotRequired` available since 3.11 |
| P2 | Registry `_discover_plugins()` runs at module import — any plugin import error blocks ALL plugins | Plugin Config Generator | Use `try/except` per-module (already implemented) + add CloudWatch metric on failures |
| P2 | `common_preamble.txt` uses `{{` and `}}` for JSON instruction — must escape in Python `.format()` calls | BSA Prompt Generator | Use `.replace("{extraction_data}", data)` instead of `.format()` |
| P1 | CDK Map state `maxConcurrency: 10` must match Textract TPS quota — 50 TPS shared across all parallel executions | CDK Map State Generator | Add env var `MAP_MAX_CONCURRENCY` defaulting to 10, adjustable per deployment |
| **P0** | **`loan_agreement` ≠ `loan_package`** — these are entirely different document types. `loan_agreement` has 7 sections (loanTerms, parties, etc.) with 275 lines in router handler and NO plugin. Deleting `LOAN_AGREEMENT_SECTIONS` breaks loan agreement processing | Router Refactoring | Create `types/loan_agreement.py` plugin BEFORE deleting handler code. Keep all loan_agreement handler code during Phases 2-4 |
| P1 | `sfn.Chain(this, id)` constructor does not exist in CDK v2 — early plan snippet (lines 174-180) is incorrect | CDK API Validator | Use `LambdaInvoke` directly with `mapExtraction.itemProcessor(extractSection)` — no Chain wrapper needed |
| P1 | `addRetry` on `extractSection` overlaps `retryOnServiceExceptions: true` (default) creating compound retries (up to 8 attempts) | CDK API Validator | Set `retryOnServiceExceptions: false` on LambdaInvoke and manage ALL retries via explicit `addRetry` |
| P1 | Round 2 vs Round 5 `itemSelector` inconsistency — Round 2 passes flat fields, Round 5 passes nested `sectionConfig.$` | CDK API Validator | Use Round 5 pattern: `'sectionConfig.$': '$$.Map.Item.Value'` — more maintainable, no CDK changes when plugin adds fields |
| P1 | `loan_package` section identification uses LLM classification (start page numbers) NOT keyword density — generic `identify_sections()` would produce wrong page assignments | Router Refactoring | Add `section_identification_strategy: "llm_classification" | "keyword_density"` to ClassificationConfig. loan_package uses LLM, credit_agreement uses keyword density |
| P1 | BSA Profile cannot work during dual-format transition — no legacy CDK Choice state path exists for BSA | Router Refactoring | BSA is only functional AFTER Phase 3 Map state deployment. Do not submit BSA test documents until Phase 3 is live |
| P2 | Credit Agreement two-pass section refinement (keyword scoring → LLM verification) — generic `identify_sections()` only implements pass 1 | Router Refactoring | Add `use_llm_section_refinement: true` plugin flag. Keep `classify_credit_agreement_with_bedrock()` as optional step |
| P2 | S3 `extractions/` prefix needs lifecycle rule for transient extraction artifacts | CDK API Validator | Add 1-day expiration rule on `extractions/` prefix in CDK stack |
| P2 | Credit Agreement misclassification reclassification logic (lines 1651-1681) validates section content and may reassign to loan_agreement | Router Refactoring | Port validation to post-classification step in generic flow |
| P2 | Missing `page_bonus_rules` in credit_agreement plugin: `lenderCommitments` "bank name + $ sign" conjunction not encoded | Router Refactoring | Express as two separate rules: `contains_any(["$"])` +1 and `contains_any(["bank", "capital", ...])` +2 |
| **P1** | **Loan agreement plugin missing** — `types/loan_agreement.py` does not exist. 8 sections with 63 queries need migration from router+extractor+CDK. `_extractedCodes` (banking system coded values) unique to loan_agreement | Loan Agreement Plugin Writer | Generate `types/loan_agreement.py` (~850 lines) + `prompts/loan_agreement.txt` before Phase 2 |
| P1 | Normalizer has 1,342 lines (52%) of dead code after refactoring — 3 hardcoded prompt builders (~700 lines) plus document-type detection logic | Normalizer Refactoring | Replace with generic `build_normalization_prompt()` using 4-layer composable architecture |
| P1 | API Gateway authorizer change (Phase 6) breaks ALL unauthenticated calls immediately — must deploy frontend Cognito integration simultaneously | CDK Stack Diff | Use staged deployment: infrastructure first → migration → Lambda code → frontend + authorizer |
| P1 | `loan_package.py` plugin has `pii_paths: []` but Form 1003 contains SSN and DOB — must add 2 PII path entries before Phase 6 | PII Encryption | Add `form1003.borrowerInfo.ssn` and `form1003.borrowerInfo.dateOfBirth` to loan_package plugin |
| P2 | `cryptography>=42.0.0` package needed for envelope encryption — add to plugins layer or create separate pii_crypto layer | PII Encryption | Prefer dedicated plugins layer `requirements.txt` to keep pypdf layer lightweight |
| P2 | State machine definition update is UPDATE not REPLACE in CloudFormation — changing definition body alone does not trigger replacement. Must verify `stateMachineName` property unchanged | CDK Stack Diff | Run `cdk diff` before deploying Phase 3 to verify no REPLACE operations |
| P2 | Normalizer `resolve_s3_extraction_refs()` must download each section's JSON from `extractions/` prefix — adds ~2-5s latency per document | Normalizer Refactoring | Use `ThreadPoolExecutor` for parallel S3 downloads (~0.5-1s total) |
| P1 | Normalizer JSON parse failure currently raises `ValueError` (line 1336), killing entire Step Functions execution — must return partial result instead | Normalizer Implementation | Return `confidence: "low"` with validation note; keeps document in PENDING_REVIEW for human inspection |
| P2 | Router `classify_credit_agreement_with_bedrock()` second LLM pass removed in refactored handler — keyword density alone may miss some section boundaries | Router Implementation | Add `use_llm_section_refinement: true` plugin flag. Monitor section accuracy in Phase 2 validation before deleting second pass |
| P2 | Normalizer `apply_field_overrides()` cannot express conditional defaults (e.g., "if LINE OF CREDIT then billingType=INTEREST ONLY") — complex defaults stay in legacy function | Normalizer Implementation | Keep `apply_loan_agreement_defaults()` temporarily; plan conditional override syntax for future plugin contract iteration |
| P1 | Frontend `@aws-amplify/auth` and `@aws-amplify/core` must be added to `frontend/package.json` — Amplify v6 tree-shakeable imports keep bundle size small (~30KB gzipped) | Frontend Cognito | Add as Phase 6 frontend dependency; do NOT use full `aws-amplify` umbrella package |
| P2 | Router `_resolve_plugin()` Strategy 2 (section name match) allows `primary_document_type: "promissory_note"` to match loan_package — critical for mortgage packages where LLM identifies sub-document type | Router Implementation | Ensure loan_package plugin's `classification.section_names` includes all 3 sub-document names |
| P2 | Frontend Login page does NOT handle `NEW_PASSWORD_REQUIRED` Cognito challenge flow — users created by admin with temporary password cannot complete first login | Frontend Cognito | Display guidance message; full password change flow deferred to Phase 7+ |

---

# refactor: Plugin Architecture for Financial Document Processing Platform

## Overview

Refactor the Financial Documents Processing system from hardcoded multi-document-type pipeline into a plugin-based platform where each document type is a self-contained config dict. Then add BSA Profile (Bank Secrecy Act / KYC form) as the first plugin-native document type.

**Core constraint:** Preserve the Router Pattern fundamentals — cheapest LLMs, targeted page extraction, under $1/doc, under 1 minute.

## Problem Statement

Adding Credit Agreements required changes to 6+ files: router handler (780 lines of hardcoded config), extractor handler, normalizer handler (3 separate prompt builders, ~700 lines), CDK Step Functions branches, frontend types, and frontend components. Each new document type repeats this pattern. With BSA Profiles, W2s, Driver's Licenses, and more planned, this doesn't scale.

**Note:** The codebase has existing dataclasses in `src/financial_docs/schemas/` (`DocumentType`, `ExtractionField`, `ExtractionSchema`) but these are NOT imported by any Lambda function. The new plugin system **replaces** these unused schemas as the single source of truth. `src/financial_docs/schemas/` will be deprecated after migration.

## Proposed Solution

### Plugin = Python Config Dict

Each document type becomes a plugin config loaded from a shared Lambda layer:

```python
# Example: BSA Profile plugin config
BSA_PROFILE_PLUGIN = {
    "id": "bsa_profile",
    "name": "BSA Profile",
    "classification": {
        "keywords": ["BSA Profile", "Beneficial Ownership", "KYC", "Legal Entity Information"],
        "has_sections": False,
    },
    "extraction": {
        "strategy": "textract_forms_plus_pypdf",  # or "textract_queries", "hybrid"
        "textract_features": ["FORMS"],
        "target_all_pages": True,  # vs targeted pages for large docs
    },
    "normalization": {
        "prompt_template": "bsa_profile_normalization.txt",
        "llm_model": "claude-3-5-haiku",
    },
    "output_schema": { ... },  # JSON schema
    "pii_fields": ["ssn", "date_of_birth", "id_number"],
    "cost_budget": 0.50,  # monitoring alarm threshold
}
```

### Processing Engine Becomes Generic

- **Router** loads all plugin classification hints, builds LLM prompt dynamically
- **Extractor** reads plugin's extraction strategy from event payload
- **Normalizer** loads plugin's prompt template and schema
- **Step Functions** uses Map state instead of hardcoded Parallel branches

## Technical Approach

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   PLUGIN REGISTRY                        │
│  (Lambda Layer: lambda/layers/plugins/)                  │
│                                                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │
│  │ Loan Package │ │Credit Agrmt  │ │ BSA Profile  │    │
│  │   Plugin     │ │   Plugin     │ │   Plugin     │    │
│  └──────────────┘ └──────────────┘ └──────────────┘    │
│         Each plugin exports: classification,             │
│         extraction strategy, normalization prompt,        │
│         output schema, PII markers                       │
└─────────────────────────────────────────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────┐
│              GENERIC PROCESSING ENGINE                    │
│                                                          │
│  S3 Upload → Trigger → Step Functions:                   │
│    1. Router Lambda (classify using plugin hints)         │
│    2. Map State (iterate plugin's extraction sections)    │
│    3. Extractor Lambda (run plugin's Textract config)     │
│    4. Normalizer Lambda (run plugin's prompt template)    │
│    5. Store results (encrypt PII per plugin markers)      │
└─────────────────────────────────────────────────────────┘
```

### Key Technical Decision: Step Functions Map State

**Current:** 3 hardcoded `sfn.Parallel` branches with Choice state routing (lines 754-783 in CDK stack).

**Target:** Single `sfn.Map` state that iterates over an `extractionPlan.sections[]` array produced by the router.

```typescript
// CDK: Generic extraction using Map state
const extractSections = new sfn.Map(this, 'ExtractSections', {
  inputPath: '$',
  itemsPath: '$.extractionPlan.sections',
  resultPath: '$.extractions',
  maxConcurrency: 10,
});
extractSections.itemProcessor(
  new sfn.Chain(this, 'ExtractSection')
    .next(new tasks.LambdaInvoke(this, 'ExtractSectionTask', {
      lambdaFunction: extractorLambda,
      outputPath: '$.Payload',
    }))
);
```

The router produces a plan like:
```json
{
  "extractionPlan": {
    "pluginId": "bsa_profile",
    "sections": [
      {"sectionName": "all", "pages": [1,2,3,4,5], "textractFeatures": ["FORMS"], "includePyPdfText": true}
    ]
  }
}
```

For Credit Agreements (multi-section), it produces:
```json
{
  "extractionPlan": {
    "pluginId": "credit_agreement",
    "sections": [
      {"sectionName": "agreementInfo", "pages": [1,2], "textractFeatures": ["QUERIES"], "queries": [...]},
      {"sectionName": "applicableRates", "pages": [15,16], "textractFeatures": ["QUERIES","TABLES"], "queries": [...]},
      ...
    ]
  }
}
```

### Implementation Phases

#### Phase 1: Plugin Layer + Registry (Foundation)

**Goal:** Create the shared plugin layer and registry. No Lambda changes yet — just the config structure.

**Files to create:**
- `lambda/layers/plugins/python/document_plugins/__init__.py` — Plugin registry module
- `lambda/layers/plugins/python/document_plugins/registry.py` — `get_plugin()`, `get_all_plugins()`, `get_classification_hints()`
- `lambda/layers/plugins/python/document_plugins/types/loan_package.py` — Loan Package plugin config (extracted from router handler lines 385-660 and normalizer lines 321-730)
- `lambda/layers/plugins/python/document_plugins/types/credit_agreement.py` — Credit Agreement plugin config (extracted from router handler lines 56-380 and normalizer lines 50-318)
- `lambda/layers/plugins/python/document_plugins/types/bsa_profile.py` — BSA Profile plugin config (new)
- `lambda/layers/plugins/python/document_plugins/prompts/` — Normalization prompt templates per type

**Tasks:**
- [x] Define the plugin contract interface (Python TypedDict or dataclass) — **PRE-GENERATED (Round 5):** `contract.py` with 10 TypedDicts on disk
- [x] Extract `CREDIT_AGREEMENT_SECTIONS` dict from `lambda/router/handler.py:56-380` into `credit_agreement.py` — **PRE-GENERATED (Round 6):** 7 sections, 153 queries migrated verbatim
- [x] Extract `LOAN_AGREEMENT_SECTIONS` dict from `lambda/router/handler.py:385-660` into `loan_package.py` — **PRE-GENERATED (Round 5):** 3 sections, 97 queries
- [x] Extract `DOCUMENT_TYPES` classification hints from `lambda/router/handler.py:662-840` — **PRE-GENERATED (Rounds 5-6):** Keywords in each plugin's `classification` config
- [x] Extract normalization prompts from `lambda/normalizer/handler.py` into template files — **PRE-GENERATED (Rounds 5-6):** `prompts/` directory with all 5 files
- [x] Write BSA Profile plugin config with classification hints, FORMS extraction strategy, and normalization prompt — **PRE-GENERATED (Round 6):** `types/bsa_profile.py` + `prompts/bsa_profile.txt`
- [x] Write BSA Profile output schema (legal entity, risk assessment, beneficial owners array, trust) — **PRE-GENERATED (Round 6):** Full `output_schema` in `bsa_profile.py`
- [ ] Add plugin layer to CDK stack (`lib/stacks/document-processing-stack.ts`)
- [ ] Unit test: plugin registry loads all 3 plugins, returns correct config by ID
- [ ] Mark `src/financial_docs/schemas/` as deprecated (add comment, do not delete yet)

> **Implementation note:** 7 of 10 Phase 1 tasks are pre-generated (3,090 lines across 10 files). Remaining work: CDK layer construct, unit tests, schema deprecation.

**Success criteria:** `from document_plugins.registry import get_plugin; plugin = get_plugin("bsa_profile")` works in a Lambda. **Pre-verified locally:** Registry discovers all 3 plugins.

##### Phase 1 Research Insights

**Plugin Contract Must Be a TypedDict Hierarchy (Architecture Review):**

The sample BSA Profile config (above) is too flat for multi-section document types. Credit Agreements have 7 sections, each with different Textract features and 30-70 queries per section. The contract must support per-section configuration:

```python
class SectionConfig(TypedDict):
    name: str
    keywords: list[str]
    max_pages: int
    min_keyword_matches: int
    textract_features: list[str]  # ["QUERIES", "TABLES", "FORMS"]
    queries: list[str]            # Textract queries for this section
    extraction_fields: list[str]

class PluginConfig(TypedDict):
    id: str
    name: str
    classification: ClassificationConfig
    sections: dict[str, SectionConfig]  # Keyed by section ID
    normalization: NormalizationConfig
    output_schema: dict  # JSON Schema
    pii_fields: list[PiiFieldSpec]  # JSON path patterns, not just field names
    cost_budget: float
```

**Textract Query Migration from CDK (Architecture Review):**

The CDK stack (`document-processing-stack.ts`, lines 234-693) embeds 300+ Textract query strings in `sfn.TaskInput.fromObject()` payloads. Under the Map state model, these queries must live in the plugin config per section. Add explicit Phase 1 task: migrate CDK-embedded queries into Loan Package and Credit Agreement plugin configs. After Phase 3, CDK should contain zero domain-specific queries.

**PII Fields Need JSON Path Patterns (Security Review):**

BSA Profile has deeply nested PII (beneficial owners array, each with SSN/DOB/ID). Simple field name lists won't work. Use path-based specification:

```python
"pii_fields": [
    {"path": "legalEntity.taxId", "type": "tax_id"},
    {"path": "beneficialOwners[*].ssn", "type": "ssn"},
    {"path": "beneficialOwners[*].dateOfBirth", "type": "dob"},
    {"path": "beneficialOwners[*].idNumber", "type": "government_id"},
]
```

**Carry Forward Validation Metadata (Architecture + Pattern Review):**

The unused `src/financial_docs/schemas/extraction_fields.py` contains valuable metadata: `pii: bool` markers, `cross_reference` fields, `validation_regex` patterns, `min_value`/`max_value` constraints. Use these as reference when building plugin configs — they represent institutional knowledge about financial document validation.

##### Phase 1 Deep Implementation (Round 2 — Plugin Registry TypedDict Designer)

**Complete TypedDict Hierarchy:**

```python
# lambda/layers/plugins/python/document_plugins/contract.py
from typing import TypedDict, NotRequired

class ValidationConstraint(TypedDict, total=False):
    min_value: float
    max_value: float
    regex: str
    allowed_values: list[str]

class FieldDefinition(TypedDict):
    id: str
    name: str
    field_type: str  # "string" | "number" | "currency" | "percentage" | "date" | "boolean"
    required: bool
    method: str  # "query" | "table" | "form" | "text"
    description: NotRequired[str]
    validation: NotRequired[ValidationConstraint]

class PageBonusRule(TypedDict):
    condition: str  # "contains_any" | "contains_all" | "regex_match"
    patterns: list[str]
    bonus: int

class ClassificationHints(TypedDict):
    keywords: list[str]
    min_keyword_matches: int
    typical_pages: NotRequired[str]
    search_schedule_pages: NotRequired[bool]
    page_bonus_rules: NotRequired[list[PageBonusRule]]

class SectionConfig(TypedDict):
    section_id: str
    name: str
    description: str
    max_pages: int
    classification_hints: ClassificationHints
    textract_features: list[str]  # ["QUERIES"] | ["FORMS"] | ["FORMS", "TABLES"]
    queries: NotRequired[list[str]]
    fields: list[FieldDefinition]
    extract_raw_text: bool
    parallel_extraction: bool

class PIIPathMarker(TypedDict):
    json_path: str  # e.g., "beneficialOwners[*].ssn"
    field_type: str  # "ssn" | "dob" | "tax_id" | "government_id" | "email"
    masking_strategy: str  # "partial" | "full" | "hash"

class NormalizationConfig(TypedDict):
    model_id: str
    prompt_template: str  # Filename in prompts/ directory
    max_tokens: int
    temperature: float

class CostBudget(TypedDict):
    max_cost_usd: float
    warn_cost_usd: float
    textract_cost_per_page: float
    section_priority: NotRequired[dict[str, int]]

class DocumentPluginConfig(TypedDict):
    plugin_id: str
    plugin_version: str
    name: str
    description: str
    classification: ClassificationHints
    sections: dict[str, SectionConfig]
    normalization: NormalizationConfig
    output_schema: dict  # JSON Schema
    pii_paths: list[PIIPathMarker]
    cost_budget: CostBudget
    supports_deduplication: bool
    supports_review_workflow: bool
    requires_signatures: bool
```

**Auto-Discovery Registry (`registry.py`):**

```python
import importlib
import pkgutil
from document_plugins import types as _types_pkg

_REGISTRY: dict[str, DocumentPluginConfig] = {}

def _discover_plugins() -> None:
    for importer, modname, ispkg in pkgutil.iter_modules(_types_pkg.__path__):
        module = importlib.import_module(f"document_plugins.types.{modname}")
        config = getattr(module, "PLUGIN_CONFIG", None)
        if config and isinstance(config, dict) and "plugin_id" in config:
            _REGISTRY[config["plugin_id"]] = config

_discover_plugins()

def get_plugin(plugin_id: str) -> DocumentPluginConfig:
    if plugin_id not in _REGISTRY:
        raise KeyError(f"Unknown plugin: {plugin_id}. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[plugin_id]
```

Adding a new document type = creating one file in `types/` with a `PLUGIN_CONFIG` dict. No registration boilerplate.

**Lambda Layer Directory Structure:**

```
lambda/layers/plugins/
├── build.sh
├── requirements.txt      # No external deps (pure Python TypedDicts)
└── python/
    └── document_plugins/
        ├── __init__.py
        ├── contract.py   # TypedDict hierarchy above
        ├── registry.py   # Auto-discovery above
        ├── types/
        │   ├── __init__.py
        │   ├── credit_agreement.py  # Full config with 7 sections + 300 queries
        │   ├── loan_package.py      # Promissory Note, Closing Disclosure, Form 1003
        │   └── bsa_profile.py       # First plugin-native type
        └── prompts/
            ├── common_preamble.txt   # Shared normalization preamble (Round 5)
            ├── credit_agreement.txt
            ├── loan_package.txt
            ├── bsa_profile.txt
            └── common_footer.txt     # Shared "critical instructions" (Round 5)
```

**Design Decisions:**
- **TypedDicts over Pydantic**: Zero-dependency, zero-import-cost, serialize to JSON natively. Pydantic adds 15MB and 200ms cold start.
- **importlib auto-discovery over explicit registry**: Adding a plugin = adding one file. No merge conflicts on a central registry dict. Same pattern as Django management commands.
- **PageBonusRule over hardcoded scoring**: The router's `identify_credit_agreement_sections()` has Credit Agreement-specific scoring baked in. Declarative rules make `identify_sections()` generic.

**Duplicate Code to Consolidate (Pattern Analysis — ~930 lines):**

| Duplication | Current Location | Lines | Target |
|-------------|-----------------|-------|--------|
| Table extraction branching | Extractor lines 803-890 | 4 × 20 = 80 | Single `run_tables_for_section()` helper |
| Section identification algorithm | Router lines 995-1313 | 2 × 150 = 300 | Generic `identify_sections()` with plugin config |
| Prompt "critical instructions" | Normalizer lines 305-317, 702-727 | 2 × 15 = 30 | Shared template fragment |
| Classification keywords | Router 662-840 + Schema module | 2 × 180 = 360 | Plugin registry (single source) |

##### Phase 1 Generated Implementation Files (Round 5)

The following files have been generated and are ready for implementation:

**`contract.py` (170 lines) — 10 TypedDict classes forming the plugin contract:**

| TypedDict | Purpose | Key Fields |
|-----------|---------|------------|
| `ValidationConstraint` | Field validation during normalization | `min_value`, `max_value`, `regex`, `allowed_values` |
| `FieldDefinition` | Single extractable field in a section | `id`, `name`, `field_type`, `required`, `method` |
| `PageBonusRule` | Declarative page scoring for section identification | `condition`, `patterns`, `bonus` |
| `ClassificationConfig` | Router document type identification | `keywords`, `has_sections`, `section_names`, `target_all_pages`, `page_bonus_rules` |
| `SectionClassificationHints` | Per-section keyword scoring | `keywords`, `max_pages`, `search_last_pages` |
| `SectionConfig` | Single extraction section (= 1 Map iteration) | `textract_features`, `queries`, `render_dpi`, `extract_signatures`, `fields` |
| `NormalizationConfig` | Normalizer behavior | `prompt_template`, `llm_model`, `max_tokens`, `field_overrides` |
| `PIIPathMarker` | JSON-path PII field markers | `json_path`, `pii_type`, `masking_strategy` |
| `CostBudget` | Per-doc cost monitoring thresholds | `max_cost_usd`, `warn_cost_usd`, `section_priority` |
| `DocumentPluginConfig` | Top-level plugin (all of the above) | `plugin_id`, `sections`, `normalization`, `pii_paths`, `legacy_section_map` |

**`registry.py` (144 lines) — Auto-discovery with 6 public functions:**

| Function | Purpose |
|----------|---------|
| `get_plugin(plugin_id)` | Get config by ID, raises `KeyError` if not found |
| `get_all_plugins()` | Dict of all registered plugins |
| `get_plugin_ids()` | List of all registered plugin IDs |
| `get_classification_hints()` | Classification configs for router prompt building |
| `get_plugin_for_document_type(doc_type)` | Fuzzy lookup: direct match, then `legacy_section_map` fallback |
| `_discover_plugins()` | Internal: `pkgutil.iter_modules` scan of `types/` subpackage |

Discovery runs once at import time. Duplicate `plugin_id` values are logged and skipped. Failed module imports are caught and logged (non-fatal).

##### Phase 1 Loan Agreement Plugin (Round 8 — Loan Agreement Plugin Config Writer)

**Status: New file required** — Resolves P0 finding that `loan_agreement ≠ loan_package`.

**`types/loan_agreement.py` Summary (~850 lines):**
- **8 sections**: loanTerms, interestDetails, paymentInfo, parties, security, fees, covenants, signatures
- **63 Textract queries** migrated from CDK `extractLoanAgreement` task + extractor handler
- **Section identification**: `keyword_density` strategy (simpler business loans, unlike loan_package which uses LLM)
- **Unique feature**: `_extractedCodes` output schema for downstream banking system compatibility (coded values like `TERM:TERM LOAN`, `PRM:PRIME RATE LOAN`, `C:MONTHLY`)
- **Signatures**: `requires_signatures: True` (unlike credit_agreement). Last 3 pages always checked.
- **Cost budget**: max $0.60, typical ~$0.18 for 15-page loan agreement (hybrid PyPDF + targeted Textract)
- **PII paths**: `[]` (no SSN/DOB in business loan agreements)

**Key differences from credit_agreement:**

| Aspect | Credit Agreement | Loan Agreement |
|--------|-----------------|----------------|
| Typical size | 50-300 pages | 5-30 pages |
| Sections | 7 (institutional finance) | 8 (commercial lending) |
| Queries | 153 | 63 |
| Extraction | Textract OCR (images) | Hybrid PyPDF text + Textract OCR (low-quality pages only) |
| Signatures | Not required | Required (legal enforceability) |
| Output codes | None | `_extractedCodes` for banking systems |
| Cost | ~$0.40-$2.00 | ~$0.18-$0.60 |

**GENERATED (Round 9): `prompts/loan_agreement.txt`** — Complete normalization template (~500 lines):

**Coverage**: 55 extraction fields organized into 10 sections (Document Identification, Loan Terms, Interest Details, Payment Information, Parties, Collateral/Security, Fees, Prepayment, Covenants, Default Provisions) + `_extractedCodes` coded field section + validation rules + audit trail.

**8 Coded Field Enumerations (unique to loan_agreement):**

| Code Field | Valid Values | Default |
|-----------|-------------|---------|
| `instrumentType` | TERM, LINE, ABL, RLOC | TERM:TERM LOAN |
| `interestRateType` | FIX, PRM, SOF, LIB, INT | (inferred from document) |
| `rateIndex` | WALLST, SOFR, WFPRIM, FHLB, FED | WALLST:WALL STREET JOURNAL PRIME |
| `rateCalculationMethod` | 360ACTUAL, 365ACTUAL, 360360 | 360ACTUAL |
| `billingType` | A (interest only), D, F (P&I), G | (context-dependent) |
| `billingFrequency` | A (weekly), C (monthly), E (quarterly), G, I, X | C:MONTHLY |
| `prepaymentIndicator` | Y, N, P (penalty) | (from document) |
| `currency` | USD, CAD, GBP | USD:US DOLLAR |

**Key design decisions:**
- Template follows exact 4-layer composable architecture: slots between `common_preamble.txt` and `common_footer.txt`
- All 27 field definitions from `build_loan_agreement_prompt()` (handler lines 321-728) are covered as numbered extraction instructions 1-55
- Textract query hybrid approach described (OCR + queries with ≥70% confidence preference)
- `currency` field included in `_extractedCodes` (from post-processing at handler line 1664-1668)
- Uses `{{`/`}}` JSON escaping throughout, compatible with `.replace()` injection
- Default value rules from handler lines 711-720: billingType context-dependent (LOC→INTEREST ONLY, TERM→P&I)
- Validation rules: loanAmount × interestRate sanity check, maturity date reasonableness, rate type consistency, coded field completeness, payment structure consistency
- `NEVER use null for coded fields` rule — always use defaults

#### Phase 0: Golden File Capture (Prerequisite)

**Goal:** Capture regression baselines BEFORE any code changes begin.

**Tasks:**
- [ ] Process 1 Loan Package through current pipeline, capture full DynamoDB output as `tests/golden/loan_package.json`
- [ ] Process 1 Credit Agreement through current pipeline, capture full output as `tests/golden/credit_agreement.json`
- [ ] Commit golden files to `tests/golden/` directory
- [ ] Create comparison script that diffs pipeline output against golden files (ignoring timestamps, execution IDs, processing times)
- [ ] Verify comparison script passes against current pipeline (baseline = clean diff)

**Success criteria:** Golden files committed and comparison script validates current pipeline produces matching output.

> **BLOCKING:** Phase 2 cannot begin until Phase 0 is complete. This is the highest-risk mitigation in the entire plan.

##### Phase 0 Deep Implementation (Round 3 — Golden File Testing Architect)

**Directory Structure:**

```
tests/golden/
    __init__.py
    capture.py                  # Upload doc, poll Step Functions, export DynamoDB record
    compare.py                  # Field-level diff with tolerances
    conftest.py                 # Pytest fixtures for golden tests
    test_golden_regression.py   # Pytest wrapper
    files/                      # Committed golden files
        credit-agreement.credit_agreement.golden.json
        loan-package.loan_package.golden.json
```

**1. Capture Script (`tests/golden/capture.py`):**

Automates: upload to S3 → poll Step Functions for completion → scan DynamoDB for result → write golden JSON with metadata wrapper.

```python
def capture_golden_file(pdf_path: str, output_dir: str = "tests/golden/files"):
    """End-to-end capture: upload, process, export."""
    bucket = get_stack_output("DocumentBucketName")        # From CloudFormation exports
    table = get_stack_output("DocumentsTableName")
    sfn_arn = get_stack_output("StateMachineArn")

    # 1. Upload to S3 ingest/ prefix (triggers pipeline)
    s3_key = f"ingest/{Path(pdf_path).name}"
    s3_client.upload_file(pdf_path, bucket, s3_key)

    # 2. Poll Step Functions for completion (timeout 120s)
    execution = wait_for_execution(sfn_arn, s3_key, timeout=120)

    # 3. Scan DynamoDB for the processed record
    record = get_document_by_content_hash(table, compute_sha256(pdf_path))

    # 4. Write golden file with metadata envelope
    golden = {
        "_goldenFileMetadata": {
            "sourceDocument": Path(pdf_path).name,
            "captureDate": datetime.utcnow().isoformat(),
            "pipelineVersion": get_stack_output("StackVersion"),
            "contentHash": record.get("contentHash"),
        },
        "record": record,
    }
    output_path = Path(output_dir) / f"{stem}.{doc_type}.golden.json"
    output_path.write_text(json.dumps(golden, indent=2, default=str))
```

**2. Comparison Script (`tests/golden/compare.py`) — Key Design Decisions:**

| Feature | Design | Rationale |
|---------|--------|-----------|
| Numeric tolerance | `NUMERIC_TOLERANCE = 0.001` (financial amounts), `RATE_TOLERANCE = 0.0001` (rates/spreads) | DynamoDB Decimal conversion can introduce floating-point noise |
| Order-insensitive arrays | Lender commitments, guarantors, lead arrangers, covenants | Banks may be listed in any order across LLM runs |
| Ignore paths | `documentId`, `createdAt`, `updatedAt`, `ttl`, `processingTime.*`, `processingCost.breakdown.lambda.*`, all LLM token counts | These vary every run by design |
| Soft match paths | `validation.validationNotes`, `audit.extractionSources` | LLM phrasing varies ("3 high-confidence signatures" vs "4 high-confidence...") |
| String normalization | Collapse whitespace, strip — do NOT normalize case | Borrower names must preserve case from LLM |

**3. Fields That Must Match Exactly (no tolerance):**

- `extractedData.*` (all extracted financial values)
- `documentType`, `status`, `reviewStatus`, `version`, `contentHash`, `fileSize`
- `validation.isValid`, `validation.confidence`
- `signatureValidation.*`
- `processingCost.breakdown.textract.pages`, `processingCost.breakdown.textract.cost`
- `processingCost.breakdown.stepFunctions.*`

**4. LLM Non-Determinism Mitigation:**

Both Router (Claude 3 Haiku) and Normalizer (Claude 3.5 Haiku) use `temperature=0`, which is nearly but not perfectly deterministic. Establish golden baselines via multi-run stability check:

```bash
# Run same document 3 times, compare runs to identify variable fields
for i in 1 2 3; do
    ./scripts/cleanup.sh --keep-source
    python tests/golden/capture.py test-documents/credit-agreement.pdf --output /tmp/run-$i
done
python tests/golden/compare.py /tmp/run-1/*.golden.json /tmp/run-2/*.golden.json
# Any field differing across runs → add to IGNORE_PATHS or SOFT_MATCH_PATHS
```

**5. CI Integration (GitHub Actions):**

```yaml
golden-file-test:
  runs-on: ubuntu-latest
  needs: [deploy-to-staging]
  steps:
    - name: Run pipeline on test documents
      run: |
        python tests/golden/capture.py test-documents/credit-agreement.pdf --output /tmp/golden-current
        python tests/golden/capture.py test-documents/loan-package.pdf --output /tmp/golden-current
    - name: Compare golden files
      run: |
        python tests/golden/compare.py tests/golden/files/credit-agreement.*.golden.json /tmp/golden-current/credit-agreement.*.golden.json
        python tests/golden/compare.py tests/golden/files/loan-package.*.golden.json /tmp/golden-current/loan-package.*.golden.json
```

**6. Phase 0 Execution Steps:**

1. Create `tests/golden/` directory structure
2. Deploy current stack (no changes)
3. Capture golden files for Credit Agreement + Loan Package
4. Verify compare.py passes against itself (self-test)
5. Manually edit a field to verify diff detection works
6. Run multi-run stability check (3 runs per doc type)
7. Commit golden files: `git commit -m "test: add golden file regression infrastructure"`

##### Phase 0 Implementation Details (Round 7 — Golden File Test Infrastructure Designer)

**Test Documents Available in `docs/`:**

| Document Type | File | Size |
|---------------|------|------|
| Credit Agreement | `CREDIT AGREEMENT.pdf` | 3.7MB |
| Loan Package (mortgage) | `MCS CONTRACTING GROUP LLC_Executed Laser Pro Package_2025-10-07.pdf` | 5.0MB |
| Loan Agreement | `TRINITY DISTRIBUTIONS LLC_Loan Agreement_2025-11-17.pdf` | 756KB |

**Golden File Naming Convention:** `{stem}.{document_type_lowercase}.golden.json` (stem = filename lowercased, hyphens, truncated to 40 chars)

**`tests/golden/compare.py` — 24 IGNORE_PATHS (complete list):**
- Unique IDs: `record.documentId`, `record.originalS3Key`
- Timestamps: `record.createdAt`, `record.updatedAt`, `record.ttl`
- Processing time: `record.processingTime.totalSeconds`, `.startedAt`, `.completedAt`, `.breakdown.router.*`, `.breakdown.textract.*`, `.breakdown.normalizer.*`
- Lambda costs: `record.processingCost.breakdown.lambda.*` (all 5 sub-fields)
- LLM tokens: `record.processingCost.breakdown.router.inputTokens`, `.outputTokens`, `.cost`; same for normalizer
- Total cost: `record.processingCost.totalCost`
- Golden metadata: `_goldenFileMetadata`
- Review state: `record.reviewedBy`, `.reviewedAt`, `.reviewNotes`, `.corrections`

**7 ORDER_INSENSITIVE_ARRAYS:** `parties.leadArrangers`, `parties.guarantors`, `lenderCommitments`, `applicableRates.tiers`, `covenants.otherCovenants`, `paymentTerms.interestPaymentDates`, `paymentTerms.interestPeriodOptions`

**No External Dependencies:** `deepdiff` intentionally avoided — domain-specific tolerance rules (rate vs financial, order-insensitive by business key, soft match for LLM text) are cleaner to implement directly than configure in deepdiff callbacks.

**Deduplication Handling:** `capture.py` computes SHA-256 locally, queries `ContentHashIndex` before upload. If duplicate found, warns user to run `./scripts/cleanup.sh --keep-source` first.

**Expected Capture Time:** 45-90 seconds per document (Step Functions ~35-60s + polling ~10s + DynamoDB read ~5s). `DEFAULT_TIMEOUT_SECONDS = 180` provides headroom.

**10-Step Execution Checklist:**

1. Create `tests/golden/`, `tests/golden/files/` directories
2. Implement `capture.py`, `compare.py`, `conftest.py`, `test_golden_regression.py`
3. Verify stack is deployed: `aws cloudformation list-exports | grep FinancialDoc`
4. Clean existing data: `./scripts/cleanup.sh`
5. Capture golden files (3 runs each for stability check):
   ```bash
   for i in 1 2 3; do
       python -m tests.golden.capture "docs/CREDIT AGREEMENT.pdf" --output /tmp/run-$i
       python -m tests.golden.capture "docs/MCS CONTRACTING GROUP LLC_Executed Laser Pro Package_2025-10-07.pdf" --output /tmp/run-$i
       python -m tests.golden.capture "docs/TRINITY DISTRIBUTIONS LLC_Loan Agreement_2025-11-17.pdf" --output /tmp/run-$i
       ./scripts/cleanup.sh --keep-source
   done
   ```
6. Cross-compare runs to identify variable fields
7. Any field differing across runs → add to `IGNORE_PATHS` or `SOFT_MATCH_PATHS`
8. Commit one run's outputs to `tests/golden/files/`
9. Self-test: compare golden vs itself (must produce 0 mismatches)
10. Tamper test: manually edit a field, verify compare.py catches it

**Files to Create (4 files, ~550 lines total):**

| File | Lines | Purpose |
|------|-------|---------|
| `tests/golden/capture.py` | ~150 | Upload→poll→export with CloudFormation stack output resolution |
| `tests/golden/compare.py` | ~250 | Field-level diff with tolerances, IGNORE/SOFT_MATCH paths |
| `tests/golden/conftest.py` | ~50 | Shared pytest fixtures (PDF paths, stack outputs) |
| `tests/golden/test_golden_regression.py` | ~100 | 3 test classes with `@pytest.mark.integration` |

#### Phase 2: Router Refactor (Classify from Plugin Registry)

**Goal:** Router Lambda reads classification hints from plugin registry instead of hardcoded dicts.

**Files to modify:**
- `lambda/router/handler.py` — Replace `CREDIT_AGREEMENT_SECTIONS`, `LOAN_AGREEMENT_SECTIONS`, `DOCUMENT_TYPES` with plugin registry imports

**Tasks:**
- [ ] Import plugin registry in router handler
- [ ] Replace `DOCUMENT_TYPES` dict (lines 662-840) with `build_classification_prompt()` reading from plugin registry + `FALLBACK_DOCUMENT_TYPES` (~80 lines for non-plugin types: deed_of_trust, bank_statement, etc.)
- [ ] Replace `CREDIT_AGREEMENT_SECTIONS` (lines 56-380) with `get_plugin("credit_agreement").sections` — **Delete immediately in Phase 2**
- [ ] **KEEP `LOAN_AGREEMENT_SECTIONS` (lines 385-660)** — loan_agreement ≠ loan_package. No plugin exists. **Round 7 CRITICAL finding**
- [ ] Modify `classify_pages_with_bedrock()` to build prompt from plugin registry dynamically
- [ ] Add BSA Profile classification to the dynamic prompt
- [ ] Change router output format: produce `extractionPlan.sections[]` array instead of type-specific keys
- [ ] Add `ROUTER_OUTPUT_FORMAT` env var (`"legacy"` / `"dual"` / `"plugin"`)
- [ ] Implement `build_classification_prompt()` (~60 lines) — top-10 keywords per plugin + distinguishing rules
- [ ] Implement `identify_sections()` + `_evaluate_bonus_rule()` (~80 lines) — generic keyword-density section identification
- [ ] Implement `build_extraction_plan()` (~50 lines) — construct `extractionPlan` from plugin config + section pages
- [ ] Implement `add_backward_compatible_keys()` (~50 lines) — dual-format output for credit_agreement and loan_package
- [ ] Implement `_resolve_plugin()` (~25 lines) — match classification result to plugin
- [ ] **NOTE:** BSA Profile only functional AFTER Phase 3 Map state. Do not test BSA during Phase 2 dual-format.
- [ ] **NOTE:** loan_package section pages come from LLM classification (start page), not keyword density. Add `section_identification_strategy` check.
- [ ] Maintain backward-compatible output keys (`creditAgreementSections`, `loanAgreementSections`) during transition
- [ ] **REGRESSION TEST:** Process existing Loan Package test doc → compare output to golden file
- [ ] **REGRESSION TEST:** Process existing Credit Agreement test doc → compare output to golden file

**Success criteria:** Router classifies all 3 document types correctly. Output includes `extractionPlan` with sections array.

##### Phase 2 Deep Implementation (Round 3 — Router Dynamic Classification Specialist)

**1. Dynamic Classification Prompt Builder:**

Replace the hardcoded `DOCUMENT_TYPES` dict (router lines 662-840) with a function that reads all registered plugins and builds the classification prompt dynamically:

```python
def build_classification_prompt(page_snippets: list[str], total_pages: int) -> str:
    """Build classification prompt from all registered plugins."""
    plugins = get_all_plugins()

    # Build document type descriptions from plugin classification hints
    type_descriptions = []
    for plugin in plugins.values():
        cls_cfg = plugin["classification"]
        keywords = ", ".join(cls_cfg["keywords"][:10])  # Top 10 for prompt brevity
        distinguishing = cls_cfg.get("distinguishing_rules", [""])[0]
        type_descriptions.append(
            f"- **{plugin['plugin_id']}**: {plugin['description']}. "
            f"Keywords: {keywords}. {distinguishing}"
        )

    # BSA vs Form 1003 disambiguation is critical
    prompt = f"""Analyze the following document page snippets and classify the document.

Document types to identify:
{chr(10).join(type_descriptions)}

For each document type, return the page number where it starts, or null if not found.
Return JSON with keys: {', '.join(plugins.keys())}
..."""
    return prompt
```

**2. Generic `identify_sections()` — Replaces Two 150-Line Functions:**

The current `identify_credit_agreement_sections()` (lines 995-1122) and `identify_loan_agreement_sections()` (lines 1125-1313) both implement the same algorithm: score pages by keyword density, rank, select top-N. Replace with a single generic function that reads page scoring rules from plugin config:

```python
def identify_sections(
    page_snippets: list[str],
    plugin_config: dict,
    total_pages: int,
) -> dict[str, list[int]]:
    """Generic section identification using plugin classification hints."""
    section_pages = {}
    for section_id, section_cfg in plugin_config["sections"].items():
        hints = section_cfg["classification_hints"]
        max_pages = section_cfg["max_pages"]

        scored_pages = []
        for page_num, snippet in enumerate(page_snippets, 1):
            snippet_lower = snippet.lower()
            score = sum(1 for kw in hints["keywords"] if kw.lower() in snippet_lower)

            # Apply page_bonus_rules from plugin config
            for rule in hints.get("page_bonus_rules", []):
                if rule["condition"] == "page_position_first_n":
                    if page_num <= rule["n"]:
                        score += rule["bonus"]
                elif rule["condition"] == "page_position_last_n":
                    if page_num > total_pages - rule["n"]:
                        score += rule["bonus"]
                elif rule["condition"] == "contains_any":
                    if any(p.lower() in snippet_lower for p in rule["patterns"]):
                        score += rule["bonus"]
                elif rule["condition"] == "contains_all":
                    if all(p.lower() in snippet_lower for p in rule["patterns"]):
                        score += rule["bonus"]

            min_threshold = hints.get("min_keyword_matches", 2)
            if score >= min_threshold:
                scored_pages.append((page_num, score))

        scored_pages.sort(key=lambda x: -x[1])
        section_pages[section_id] = [p for p, _ in scored_pages[:max_pages]]

    return section_pages
```

**3. `extractionPlan.sections[]` Output Format:**

The router produces a unified format consumed by the Map state. Examples for each document type:

**Credit Agreement (7 sections):**
```json
{
  "extractionPlan": {
    "pluginId": "credit_agreement",
    "sections": [
      {
        "sectionType": "credit_agreement_section",
        "creditAgreementSection": "agreementInfo",
        "sectionPages": [1, 2, 3, 4, 5],
        "textractFeatures": ["QUERIES"],
        "queries": ["What type of agreement is this?", ...],
        "extractRawText": true,
        "parallelExtraction": true
      },
      ... // 6 more sections
    ]
  }
}
```

**BSA Profile (1 section, all pages):**
```json
{
  "extractionPlan": {
    "pluginId": "bsa_profile",
    "sections": [
      {
        "sectionType": "bsa_profile_all",
        "textractFeatures": ["FORMS", "TABLES"],
        "sectionPages": [1, 2, 3, 4, 5],
        "queries": [],
        "extractRawText": true,
        "parallelExtraction": true,
        "includeSignatures": true
      }
    ]
  }
}
```

**4. Query Migration (305 queries, CDK → Plugin Configs):**

| Source | Lines | Query Count | Target Plugin |
|--------|-------|-------------|---------------|
| CDK `extractPromissoryNote` | 234-308 | ~35 | `loan_package.sections.promissory_note.queries` |
| CDK `extractClosingDisclosure` | 323-425 | ~50 | `loan_package.sections.closing_disclosure.queries` |
| CDK `extractLoanAgreement` | 571-693 | ~60 | `loan_agreement.sections.*.queries` |
| Extractor `CREDIT_AGREEMENT_QUERIES` | 64-287 | ~160 | `credit_agreement.sections.*.queries` |

After migration, CDK contains zero domain-specific queries. The Map state passes `queries` from `$$.Map.Item.Value.queries`.

**5. BSA Classification Strategy — Distinguishing From Form 1003:**

BSA has highly distinctive markers ("BSA Profile", "Beneficial Ownership", "KYC", "FinCEN", "Customer Due Diligence") that never appear in Form 1003 or any other document type. Risk of false positive is extremely low.

```python
"classification": {
    "keywords": [
        "bsa profile", "beneficial ownership", "kyc", "know your customer",
        "legal entity information", "bank secrecy act", "customer due diligence",
        "cdd", "fincen", "anti-money laundering", "aml", "entity type",
        "naics code", "beneficial owner", "ownership percentage", "control person",
        "politically exposed person", "pep", "cash intensive business",
    ],
    "has_sections": False,
    "target_all_pages": True,
    "expected_page_count": 5,
}
```

**6. Backward Compatibility During Transition:**

Router produces BOTH formats simultaneously during Phase 2:

```python
def add_backward_compatible_keys(result: dict, extraction_plan: dict) -> dict:
    """Add legacy output keys consumed by current Parallel branches.
    Remove after Phase 3 Map state migration is confirmed working."""
    plugin_id = extraction_plan.get("pluginId")

    if plugin_id == "credit_agreement":
        ca_sections = {}
        for section in extraction_plan["sections"]:
            ca_name = section.get("creditAgreementSection")
            if ca_name:
                ca_sections[ca_name] = section.get("sectionPages", [])
        result["creditAgreementSections"] = {"sections": ca_sections, ...}

    elif plugin_id == "loan_package":
        for section in extraction_plan["sections"]:
            sub_type = section.get("documentSubType")
            page = section.get("pageNumber")
            if sub_type and page:
                result["classification"][sub_type] = page
                # Legacy camelCase keys
                camel_map = {"promissory_note": "promissoryNote", ...}
                if sub_type in camel_map:
                    result["classification"][camel_map[sub_type]] = page
    return result
```

Legacy keys are removed in Phase 3 cleanup after confirming the Map state works correctly.

##### Phase 2 Risk Analysis (Round 7 — Router Handler Refactoring Specialist)

**7 risk areas identified — ordered by severity:**

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | **loan_agreement ≠ loan_package** — different document types, no plugin exists | CRITICAL | Keep all `LOAN_AGREEMENT_SECTIONS` (275 lines) and `identify_loan_agreement_sections()` (184 lines). Create `types/loan_agreement.py` before deletion. |
| 2 | Credit Agreement two-pass refinement removal | HIGH | Keep `classify_credit_agreement_with_bedrock()` as optional LLM step. Add `use_llm_section_refinement: true` plugin flag. |
| 3 | Misclassification reclassification logic (lines 1651-1681) | HIGH | Port to generic post-classification validation checking section content |
| 4 | `page_bonus_rules` schema gaps | MEDIUM | Express compound conditions as two rules: `contains_any(["$"])` +1 and `contains_any(["bank",...])` +2 |
| 5 | BSA cannot work in dual mode | MEDIUM | Document: BSA only functional after Phase 3 |
| 6 | Prompt token budget increase | LOW | Keep top-10 keywords per plugin. Monitor token usage. |
| 7 | `loan_package` uses LLM-based section ID, not keyword density | HIGH | Add `section_identification_strategy: "llm_classification"` to ClassificationConfig. loan_package sections derive from LLM output, not `identify_sections()`. |

**Net Phase 2 Code Change:**

| Change | Lines |
|--------|-------|
| Delete `CREDIT_AGREEMENT_SECTIONS` | -325 |
| Delete `DOCUMENT_TYPES` | -178 |
| Add new functions (5 functions) | +265 |
| Add `FALLBACK_DOCUMENT_TYPES` | +80 |
| Add feature flag + imports | +15 |
| Modify `lambda_handler()` | +40 |
| **Net** | **-103 lines** |

After Phase 3 validation + loan_agreement plugin: additional ~725 lines deletable.

##### Phase 2 Complete Function Implementations (Round 9 — Router Handler Implementation Specialist)

**1. `build_classification_prompt(page_snippets, all_plugins)` — Complete Implementation (~60 lines):**

Replaces `classify_pages_with_bedrock()` (lines 1452-1576). Builds dynamic prompt from plugin registry with top-10 keywords per plugin, distinguishing rules, and BSA vs Form 1003 disambiguation block. Single Bedrock call replaces the current two-call pattern (classify + refine).

**2. `identify_sections(page_snippets, plugin, page_count)` — Complete Implementation (~80 lines):**

Generic keyword density scoring with `_evaluate_bonus_rule()` helper. Supports declarative `page_bonus_rules` from plugin config (e.g., `contains_any(["$"])` +1 for lenderCommitments dollar signs). Returns `{section_id: [page_numbers]}` dict. Replaces both `identify_credit_agreement_sections()` (lines 995-1127) and `identify_loan_agreement_sections()` (lines 1130-1313).

**3. `build_extraction_plan(plugin, classification_result, page_snippets)` — Complete Implementation (~50 lines):**

Three extraction strategies mapped to plugin archetypes:
- **target_all_pages** (BSA): All pages go to every section
- **section_names** (loan_package): LLM-returned start pages → computed page ranges
- **keyword_density** (credit/loan agreement): Keyword-identified pages per section

Each extraction section carries its full `sectionConfig` so the extractor Lambda has queries, textract features, etc. without re-loading the plugin.

**4. `add_backward_compatible_keys(result, plugin_id)` — Complete Implementation (~50 lines):**

Per-plugin legacy key generation:
- **credit_agreement**: `creditAgreementSections.sections`, `metadata.creditAgreementTargetedPages`
- **loan_package**: camelCase classification aliases (`promissoryNote`, `closingDisclosure`, `form1003`), per-section page arrays
- **loan_agreement**: `loanAgreementSections.sections`, `metadata.loanAgreementTargetedPages`
- **bsa_profile**: No legacy keys (new-only plugin)

**5. `_resolve_plugin(classification_result, all_plugins)` — Complete Implementation (~25 lines):**

Three-strategy resolution:
1. **Direct match**: `primary_document_type` == plugin_id (e.g., "credit_agreement")
2. **Section name match**: `primary_document_type` is a sub-document within a plugin's `section_names` (e.g., "promissory_note" → loan_package)
3. **Legacy fallback**: Check each plugin's `legacy_section_map`

Raises `ValueError` if no match, returning minimal result with classification only.

**6. Refactored `lambda_handler` — 9-step flow:**

1. Download PDF + extract page snippets (unchanged)
2. Load plugins from registry (`get_all_plugins()`)
3. Build dynamic classification prompt
4. Call Bedrock for classification (single call)
5. Resolve plugin from classification result
6. Identify sections (strategy depends on plugin type)
7. Build extraction plan
8. Add backward-compatible keys for Step Functions transition
9. Update DynamoDB status to CLASSIFIED

**Credit Agreement reclassification logic preserved:** If credit_agreement sections are insufficient (no critical sections or ≤1 section with content), reclassifies to loan_agreement. Falls back to `identify_loan_agreement_sections()` inline function until loan_agreement plugin is created.

**Dead Code Analysis (what can be deleted and when):**

| Symbol | Lines | Action | When |
|--------|-------|--------|------|
| `CREDIT_AGREEMENT_SECTIONS` | 56-380 | DELETE immediately | Phase 2 deploy |
| `DOCUMENT_TYPES` | 663-840 | DELETE immediately | Phase 2 deploy |
| `identify_credit_agreement_sections()` | 995-1127 | DELETE immediately | Phase 2 deploy |
| `classify_credit_agreement_with_bedrock()` | 1316-1449 | DELETE immediately | Phase 2 deploy |
| `classify_pages_with_bedrock()` | 1452-1576 | DELETE immediately | Phase 2 deploy |
| `LOAN_AGREEMENT_SECTIONS` | 385-658 | KEEP temporarily | Delete when loan_agreement plugin exists |
| `identify_loan_agreement_sections()` | 1130-1313 | KEEP temporarily | Delete when loan_agreement plugin exists |

#### Phase 3: CDK Step Functions Refactor (Map State)

**Goal:** Replace 3 hardcoded `Parallel` branches with a single `Map` state.

**IMPORTANT: Phases 2, 3, and 4 must deploy atomically** (single `cdk deploy`). The router's new `extractionPlan` output, the Map state that consumes it, and the extractor that reads the new event format are tightly coupled. The backward-compatible keys from Phase 2 are removed once the pipeline is confirmed working.

**Files to modify:**
- `lib/stacks/document-processing-stack.ts` — Replace Parallel branches (lines 700-783) with Map state

**Tasks:**
- [ ] Remove `parallelMortgageExtraction` (lines 708-714) and its 3 branch task definitions (lines 226-442)
- [ ] Remove `parallelCreditAgreementExtraction` (lines 717-727) and its 7 branch task definitions (lines 448-560)
- [ ] Remove `parallelLoanAgreementExtraction` (lines 700-705) and its branch
- [ ] Remove `documentTypeChoice` Choice state (lines 754-783)
- [ ] Add `sfn.Map` state that iterates over `$.extractionPlan.sections`
- [ ] **Map state input:** Use `itemSelector` to merge document metadata (S3 bucket, key, pluginId) with each section item so the extractor receives both the section config and the PDF location
- [ ] Map state invokes extractor Lambda for each section
- [ ] Set `maxConcurrency: 10` for parallel section extraction
- [ ] **Map state error handling:** Add a `Catch` on the Map state to handle individual section extraction failures — log the failed section and continue with successful ones (partial extraction is better than total failure)
- [ ] **Data flow:** After the Map state, pass `pluginId` from `$.extractionPlan.pluginId` to the normalizer step via `resultSelector` so it can load the correct prompt template
- [ ] Add plugin layer to all Lambda functions in CDK
- [ ] Remove backward-compatible output keys from router (Phase 2 cleanup)
- [ ] **TEST:** Deploy to dev environment, run existing test documents through new pipeline

**Success criteria:** Step Functions workflow uses Map state. Same documents produce same extraction results.

> **Note:** Since Phases 2, 3, and 4 deploy together, develop and test them locally before a single `cdk deploy`. The CDK TypeScript code examples above are illustrative — verify against the current CDK v2 `Map` state API during implementation.

##### Phase 3 Research Insights

**256KB Payload Size Budget (Architecture + Performance Review):**

Step Functions has a 256KB payload limit per state transition. The Map state's `resultPath: '$.extractions'` aggregates ALL section results into a single array passed to the normalizer. With `MAX_RAW_TEXT_CHARS = 80000` per section and up to 10 concurrent sections, the combined payload can exceed 256KB.

**Recommendation:** Have the extractor write full results to S3 (it already has bucket access) and pass only an S3 reference key in the Step Functions payload. The normalizer reads from S3. Add task:

- [ ] Extractor writes extraction results to `s3://bucket/extractions/{executionId}/{sectionName}.json`
- [ ] Step Functions payload contains only `{"s3Key": "...", "sectionName": "...", "status": "EXTRACTED"}` per section
- [ ] Normalizer reads all section results from S3 before building prompt
- [ ] Reduce `MAX_RAW_TEXT_CHARS` or remove it entirely (no longer constrained by payload limit)

**Map State Error Handling — Tolerated Failures (Best Practices):**

Step Functions Map state supports `toleratedFailurePercentage` and `toleratedFailureCount` for partial success handling. For a 7-section Credit Agreement, 1 failed section should not fail the entire document. Configure:

```typescript
const extractSections = new sfn.Map(this, 'ExtractSections', {
  maxConcurrency: 10,
  toleratedFailurePercentage: 30,  // Allow up to ~2/7 sections to fail
});
```

**Textract TPS Monitoring (Performance Review):**

With 10 concurrent Map iterations × 30 parallel workers × concurrent Step Functions executions, the theoretical peak is 2100 Textract TPS — far exceeding the 50 TPS quota. Add CloudWatch alarm for Textract throttling and consider reducing `MAX_PARALLEL_WORKERS` when Map state concurrency is high.

##### Phase 3 Deep Implementation (Round 2 — CDK Map State Researcher)

**CORRECTION: `toleratedFailurePercentage` is DistributedMap-Only**

The Round 1 plan snippet referencing `toleratedFailurePercentage` on `sfn.Map` is incorrect. This property exists ONLY on `sfn.DistributedMap`. For inline `sfn.Map`, use per-iteration `addCatch` instead. DistributedMap is overkill for at most 7 iterations and adds child workflow execution billing.

**Complete CDK Replacement Code:**

```typescript
// Single generic extraction task — invoked once per section by Map
const extractSection = new tasks.LambdaInvoke(this, 'ExtractSection', {
  lambdaFunction: extractorLambda,
  outputPath: '$.Payload',
  retryOnServiceExceptions: true,
});

// Per-iteration retry (retries only the FAILED section independently)
extractSection.addRetry({
  errors: ['Lambda.ServiceException', 'Lambda.AWSLambdaException',
           'Lambda.SdkClientException', 'States.TaskFailed'],
  interval: cdk.Duration.seconds(2),
  maxAttempts: 2,
  backoffRate: 2.0,
});

// Per-iteration catch (failed section → error placeholder, others continue)
const sectionFailedPass = new sfn.Pass(this, 'SectionExtractionFailed', {
  result: sfn.Result.fromObject({
    status: 'FAILED',
    error: 'Section extraction failed after retries',
  }),
});
extractSection.addCatch(sectionFailedPass, {
  errors: ['States.ALL'],
  resultPath: '$.sectionError',
});

// Map state iterating over extractionPlan.sections from router
const mapExtraction = new sfn.Map(this, 'MapExtraction', {
  comment: 'Iterate over extraction plan sections',
  maxConcurrency: 10,
  itemsPath: '$.extractionPlan.sections',
  itemSelector: {
    // Document metadata (from parent state)
    'documentId.$': '$.documentId',
    'bucket.$': '$.bucket',
    'key.$': '$.key',
    'contentHash.$': '$.contentHash',
    'size.$': '$.size',
    'uploadedAt.$': '$.uploadedAt',
    'routerTokenUsage.$': '$.routerTokenUsage',
    'lowQualityPages.$': '$.lowQualityPages',
    // Section config (from current array element via context object)
    'sectionType.$': '$$.Map.Item.Value.sectionType',
    'creditAgreementSection.$': '$$.Map.Item.Value.creditAgreementSection',
    'sectionPages.$': '$$.Map.Item.Value.sectionPages',
    'extractionType.$': '$$.Map.Item.Value.extractionType',
    'pageNumber.$': '$$.Map.Item.Value.pageNumber',
    'queries.$': '$$.Map.Item.Value.queries',
    'isLoanAgreement.$': '$$.Map.Item.Value.isLoanAgreement',
    // Unique S3 path for intermediate storage
    'executionId.$': '$$.Execution.Name',
  },
  resultPath: '$.extractions',
});
mapExtraction.itemProcessor(extractSection);
```

**Data Flow Through Map State:**

`resultPath: '$.extractions'` only writes to that specific path. All router output fields (`documentId`, `bucket`, `key`, `contentHash`, `classification`, `extractionPlan.pluginId`, `routerTokenUsage`) pass through unchanged. The normalizer receives the full object with `$.extractions` added. No `resultSelector` needed.

**256KB S3 Intermediate Storage Pattern:**

Each extractor invocation writes full results to S3 and returns a lightweight reference:

```python
# In extractor lambda_handler return path:
def write_extraction_to_s3(bucket, document_id, section_name, result, execution_id):
    s3_key = f"extractions/{execution_id}/{section_name}.json"
    s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(result, default=str))
    return {
        's3ResultRef': {'bucket': bucket, 'key': s3_key, 'sizeBytes': len(json.dumps(result))},
        'documentId': result.get('documentId'),
        'creditAgreementSection': result.get('creditAgreementSection'),
        'status': result.get('status'),
        'hasQueries': bool(result.get('results', {}).get('queries')),
        'hasTables': bool(result.get('results', {}).get('tables', {}).get('tables')),
    }
```

Normalizer resolves S3 refs before processing:

```python
# In normalizer lambda_handler:
def resolve_s3_extraction_refs(extractions):
    resolved = []
    for ext in extractions:
        s3_ref = ext.get('s3ResultRef')
        if s3_ref:
            full_result = json.loads(s3_client.get_object(Bucket=s3_ref['bucket'], Key=s3_ref['key'])['Body'].read())
            resolved.append(full_result)
        else:
            resolved.append(ext)  # Backward compat or failed section
    return resolved
```

**Map vs Parallel Performance:** With `maxConcurrency: 10` and at most 7 credit agreement sections, all 7 iterations launch simultaneously — identical to current Parallel behavior. Performance is equivalent.

**Router Must Produce `extractionPlan.sections` Array:** The router builds the sections array from plugin config, moving query lists from CDK into the router. After migration, CDK contains zero domain-specific queries.

**Files That Change for Phase 3:**
| File | Change |
|------|--------|
| `lib/stacks/document-processing-stack.ts` | Remove 10 LambdaInvoke tasks, 3 Parallel states, Choice state. Add single `extractSection` + `sfn.Map`. |
| `lambda/router/handler.py` | Add `extractionPlan` output with `sections` array. |
| `lambda/extractor/handler.py` | Add `write_extraction_to_s3()`. Modify return paths. |
| `lambda/normalizer/handler.py` | Add `resolve_s3_extraction_refs()`. Call before processing. |

##### Phase 3 CDK Map State Implementation Details (Round 5 — CDK Map State Code Generator)

**Key CDK Code Patterns (from generated replacement):**

1. **Map State with `itemSelector`** — Merges document metadata with per-section config:
```typescript
const mapExtraction = new sfn.Map(this, 'MapExtraction', {
  maxConcurrency: 10,
  itemsPath: '$.extractionPlan.sections',
  itemSelector: {
    'sectionConfig.$': '$$.Map.Item.Value',
    'documentId.$': '$.documentId',
    'bucket.$': '$.bucket',
    'key.$': '$.key',
    'pluginId.$': '$.extractionPlan.pluginId',
    'executionName.$': '$$.Execution.Name',
  },
  resultPath: '$.extractions',
});
```

2. **Per-Iteration Error Handling** — `addRetry` for throttling, `addCatch` for failures:
```typescript
extractSection.addRetry({
  errors: ['ThrottlingException', 'ProvisionedThroughputExceededException'],
  interval: cdk.Duration.seconds(2),
  maxAttempts: 3,
  backoffRate: 2,
});
extractSection.addCatch(sectionExtractionFailed, {
  resultPath: '$.error',
});
```

3. **Blue/Green Choice State** — Routes between Map (new) and Parallel (legacy) during transition:
```typescript
const extractionRouteChoice = new sfn.Choice(this, 'ExtractionRouteChoice')
  .when(sfn.Condition.isPresent('$.extractionPlan'), mapExtraction)
  .otherwise(legacyParallelExtraction);
```

4. **Environment Variables Added:**
   - `ROUTER_OUTPUT_FORMAT` — `"old"` | `"dual"` | `"new"` (feature flag)
   - `SELECTION_CONFIDENCE_THRESHOLD` — `"0.75"` (checkbox confidence)
   - `S3_EXTRACTION_PREFIX` — `"extractions/"` (intermediate storage path)
   - `MAP_MAX_CONCURRENCY` — `"10"` (adjustable per deployment)

5. **Log Level** — Changed from `ALL` to `ERROR` to prevent PII in CloudWatch.

6. **Data Flow (5 steps):**
   Router output → Choice (blue/green) → Map iterates sections → Extractor writes S3 refs → Normalizer resolves refs.

   `resultPath: '$.extractions'` preserves all router fields. No `resultSelector` needed.

**All legacy Parallel branches preserved with `[LEGACY]` comments** during the transition period. Removed only after blue/green validation passes golden file tests.

##### Phase 3 CDK API Validation (Round 7 — CDK Map State API Validator)

**15 API findings validated against `node_modules/aws-cdk-lib/aws-stepfunctions/`:**

| # | API Element | Verdict | Notes |
|---|-------------|---------|-------|
| 1 | `sfn.Map` (not `DistributedMap`) | **CORRECT** | Inline Map for ≤40 items. 7-10 sections max. |
| 2 | `itemSelector` on `Map` | **CORRECT** | From `MapBaseOptions`. Deprecated `parameters` still works. |
| 3 | `toleratedFailurePercentage` on `Map` | **INCORRECT** | Only on `DistributedMap`. Self-corrected in Round 2. Use per-iteration `addCatch`. |
| 4 | `itemProcessor()` method | **CORRECT** | `iterator()` is deprecated. |
| 5 | `LambdaInvoke` directly to `itemProcessor()` | **CORRECT** | Implements `IChainable`. No `Chain` wrapper needed. |
| 6 | `maxConcurrency: 10` | **CORRECT** | Inline Map max is 40. |
| 7 | `resultPath: '$.extractions'` | **CORRECT** | Preserves all other fields from state input. |
| 8 | `$$.Map.Item.Value` context object | **CORRECT** | `.$` suffix required for dynamic path evaluation. |
| 9 | `$$.Execution.Name` context object | **CORRECT** | Standard Step Functions context. |
| 10 | `new sfn.Chain(this, 'id')` | **INCORRECT** | No such constructor. Chain created via `Chain.start(state)`. Superseded by Round 2 code. |
| 11 | Round 2 vs Round 5 `itemSelector` | **INCONSISTENT** | Use Round 5: `'sectionConfig.$': '$$.Map.Item.Value'` (nested, maintainable). |
| 12 | `addRetry` + `retryOnServiceExceptions` | **COMPOUND** | Creates up to 8 attempts. Set `retryOnServiceExceptions: false`. |
| 13 | Optional fields in `itemSelector` (`lowQualityPages`, `routerTokenUsage`) | **RUNTIME RISK** | If absent in state, `.$` resolution fails. Omit from `itemSelector`. |
| 14 | Inner `LambdaInvoke` `payload` property | **CRITICAL** | Must NOT be set. Receives `itemSelector` output as `$` input. |
| 15 | `parameters` (deprecated) | **VALIDATED** | `itemSelector` is the correct replacement. |

**Corrected CDK Pattern (validated):**
```typescript
const extractSection = new tasks.LambdaInvoke(this, 'ExtractSection', {
  lambdaFunction: extractorLambda,
  // No payload property: receives Map's itemSelector output as $ input
  outputPath: '$.Payload',
  retryOnServiceExceptions: false,  // Manage all retries explicitly
});

extractSection.addRetry({
  errors: [
    'Lambda.ServiceException', 'Lambda.AWSLambdaException',
    'Lambda.SdkClientException', 'Lambda.ClientExecutionTimeoutException',
    'ThrottlingException', 'ProvisionedThroughputExceededException',
  ],
  interval: cdk.Duration.seconds(2),
  maxAttempts: 3,
  backoffRate: 2.0,
});
```

**S3 Lifecycle Rule for `extractions/` Prefix (add to CDK):**
```typescript
{ id: 'CleanupExtractionArtifacts', prefix: 'extractions/', expiration: cdk.Duration.days(1) }
```

**Line-by-Line Change Map for `document-processing-stack.ts`:**

| Lines | Action | Description |
|-------|--------|-------------|
| After 119 | INSERT | `pluginsLayer` LayerVersion definition |
| 130 | MODIFY | Add `pluginsLayer` to routerLambda layers |
| 133-137 | MODIFY | Add `ROUTER_OUTPUT_FORMAT: 'dual'` |
| 159 | MODIFY | Add `pluginsLayer` to extractorLambda layers |
| 163-172 | MODIFY | Add `S3_EXTRACTION_PREFIX`, `SELECTION_CONFIDENCE_THRESHOLD` |
| ~197 | MODIFY | Add `layers: [pluginsLayer]` to normalizerLambda |
| 226-697 | KEEP | Legacy extraction tasks with `[LEGACY]` comments |
| 700-727 | KEEP | Legacy Parallel states with `[LEGACY]` comments |
| After 727 | INSERT | New `extractSection`, `sectionExtractionFailed`, `mapExtraction` |
| 754-783 | REPLACE | `extractionRouteChoice` → Map or `legacyDocumentTypeChoice` |
| 818 | MODIFY | `level: sfn.LogLevel.ERROR` |

##### Phase 3 CDK Stack Annotated Diff (Round 8 — CDK Stack Complete Diff Generator)

**Current file inventory** — 45+ CDK constructs mapped across 1,060 lines. Key construct groups:
- S3 buckets (2): `DocumentBucket` (lines 25-61), `FrontendBucket` (lines 63-71)
- DynamoDB: `DocumentTable` (lines 73-108)
- Lambda layers: `pypdfLayer` (lines 110-119)
- Lambda functions (5): router (127-150), extractor (152-186), normalizer (188-213), trigger (215-247), API (840-877)
- Step Functions states: 14 LambdaInvoke tasks (lines 249-697), 3 Parallel states (lines 700-749), 1 Choice state (lines 751-783)
- API Gateway: 14 routes (lines 881-940)
- CloudFront: distribution + OAI + URL rewrite function (lines 942-1015)
- CfnOutputs: 7 exports (lines 1017-1060)

**Phase 3 complete annotated diff:**
1. **INSERT** `pluginsLayer` (LayerVersion) after line 119
2. **MODIFY** router/extractor/normalizer Lambda `layers` arrays to add `pluginsLayer`
3. **ADD** env vars: `ROUTER_OUTPUT_FORMAT`, `S3_EXTRACTION_PREFIX`, `SELECTION_CONFIDENCE_THRESHOLD`
4. **INSERT** Map state constructs: `ExtractCreditAgreementSection` (inner LambdaInvoke), `SectionExtractionFailed` (Pass), `MapCreditAgreementExtraction` (Map with `maxConcurrency: 7`, `itemsPath: '$.sections'`, `resultPath: '$.extractions'`)
5. **INSERT** blue/green `CreditAgreementExtractionChoice`: routes to Map if `$.sections` present, otherwise legacy Parallel
6. **MODIFY** `documentTypeChoice` wiring: credit agreement branch now goes through `CreditAgreementExtractionChoice`
7. **ADD** `mapCreditAgreementExtraction.addCatch(handleError)` for error handling
8. **RETAIN** all 7 legacy `ExtractCreditAgreement*` tasks + `parallelCreditAgreementExtraction` during blue/green

**Phase 3 deployment safety:**
- All new CDK constructs are CREATES (safe). 5 existing resources modified (3 Lambda layers/envs, state machine definition, Choice wiring). 0 deletions.
- **Highest risk**: State machine definition update. CloudFormation UPDATE (not REPLACE) — verify `stateMachineName` unchanged with `cdk diff`.
- **Recommended order**: Deploy CDK first (safe — legacy Parallel is default), then deploy router code (emits `$.sections` → activates Map path).

**Phase 4 S3 lifecycle rule:** Add `{id: 'CleanupExtractions', prefix: 'extractions/', expiration: Duration.days(1)}` to existing `lifecycleRules` array.

**Phase 6 constructs (8 new):**
- KMS key (`PIIEncryptionKey`) with `enableKeyRotation: true`, `removalPolicy: RETAIN`
- Cognito User Pool (`DocumentProcessingUserPool`) with 3 groups (Admins, Reviewers, Viewers)
- Cognito App Client (`DashboardClient`) with authorization code grant flow
- Audit DynamoDB table (`AuditTable`) with KMS encryption, 7-year TTL, `UserActionIndex` GSI
- API Gateway `CognitoUserPoolsAuthorizer` — **modifies all 14 `addMethod` calls** (HIGH RISK)
- KMS grants: `grantEncryptDecrypt(normalizerLambda)`, `grantDecrypt(apiLambda)`
- 4 new CfnOutputs: `UserPoolId`, `UserPoolClientId`, `AuditTableName`, `PIIKeyArn`

**Construct dependency graph impact:** The Map state depends on `pluginsLayer` and `extractorLambda`. The Cognito authorizer depends on `userPool` which depends on `distribution` (for callback URLs). The audit table depends on `piiEncryptionKey`.

#### Phase 4: Extractor Refactor (Config-Driven Extraction)

**Goal:** Extractor Lambda reads extraction strategy from event payload instead of branching on document type.

**Files to modify:**
- `lambda/extractor/handler.py` — Replace `creditAgreementSection`/`isLoanAgreement` branching with generic section extraction

**Tasks:**
- [ ] Replace the `creditAgreementSection` branch (line 2107) with generic `sectionConfig` from event
- [ ] Replace the `isLoanAgreement` branch (line 2165) with `extractionStrategy` field from event
- [ ] Implement `textract_forms_plus_pypdf` strategy for BSA Profile (Textract FORMS on all pages + PyPDF text)
- [ ] **BUG FIX:** Update `extract_forms()` (line 1565) to handle `SELECTION_ELEMENT` blocks — currently only extracts `WORD` blocks from value children, silently dropping checkbox/radio values. Add `valueType: "selection"` to results. (Best Practices research)
- [ ] Keep existing `textract_queries`, `textract_queries_and_tables`, and `hybrid` strategies working
- [ ] Extractor returns raw Textract output + PyPDF text in consistent format regardless of strategy
- [ ] **REGRESSION TEST:** Verify Credit Agreement section extraction produces identical output
- [ ] **REGRESSION TEST:** Verify Loan Package extraction produces identical output

**Success criteria:** Extractor handles any strategy defined in plugin config. No document-type-specific branching remains.

##### Phase 4 Research Insights

**Implement `process_pages_forms_parallel()` (Performance Review — P0):**

The current `extract_forms()` at extractor line 1565 handles only single-page extraction. BSA Profile needs 5-page FORMS extraction. Without a parallel implementation, 5 pages process sequentially (10-15 seconds) instead of concurrently (3-4 seconds). Add task:

- [ ] Implement `process_pages_forms_parallel()` following the same pattern as `process_pages_queries_parallel()` at line 516

**BSA Pipeline Time Estimate:** ~16-23 seconds total (Router ~5-8s, Extractor ~4-6s parallel, Normalizer ~3-5s, overhead ~2s). Well under 60-second target.

**Extraction Strategy at Section Level, Not Document Level (Architecture Review):**

The plan's strategy names (`textract_forms_plus_pypdf`, `textract_queries`) are too coarse. A single document type can have sections with different strategies. Define extraction at the section level using boolean flags:

```python
# Per-section config in plugin
"sections": {
    "agreementInfo": {
        "textract_features": ["QUERIES"],
        "include_pypdf_text": True,
        "low_quality_fallback": False,
        "render_as_images": True,
        "queries": [...]
    },
    "applicableRates": {
        "textract_features": ["QUERIES", "TABLES"],
        "include_pypdf_text": False,
        "render_as_images": True,
        "queries": [...]
    }
}
```

**Consolidate Duplicated Extraction Logic (Pattern Analysis):**

Four identical table extraction branches (extractor lines 803-890) should become a single `run_tables_for_section()` function. The plugin config's `textract_features` list per section drives which Textract calls to make — no more `if section_name == "..."` branches.

Similarly, create a generic `run_textract_feature(feature_type, page_images, bucket, temp_key)` helper that encapsulates the 3-way branch (multi-page parallel / single page / S3 fallback) that currently appears ~10 times in the extractor.

**CRITICAL BUG: `extract_forms()` Drops Checkbox/Radio Values (Best Practices Research):**

The current `extract_forms()` at extractor line 1565 only processes `WORD` blocks from value children. Textract represents checkboxes and radio buttons as `SELECTION_ELEMENT` blocks with `SelectionStatus: "SELECTED" | "NOT_SELECTED"`. These are silently dropped by the current code. The fix:

1. Check for `SELECTION_ELEMENT` blocks alongside `WORD` blocks in value children
2. Add `valueType: "selection"` to distinguish text from checkbox/radio results
3. Use the `SelectionStatus` field as the value
4. Consider a lower confidence threshold (75%) for selection elements since they are binary

Accuracy expectations for BSA Profile checkboxes:

| Content Type | Expected Confidence |
|-------------|-------------------|
| Digitally filled checkboxes | 90-99% |
| Hand-checked (clear marks) | 80-95% |
| Lightly marked checkboxes | 60-80% (below 85% threshold) |
| Digital text in forms | 95-99% |
| Clean handwritten text | 80-95% |

**Additional Textract FORMS Best Practice:** Consider requesting `FORMS` + `TABLES` together for BSA pages that may contain selection elements inside table cells. Selection elements nested in tables are only returned when `TABLES` feature is included.

**Credit Agreement `ensure_all_table_data` Post-Processing (Pattern Analysis):**

The normalizer's `ensure_all_table_data` function (lines 1392-1598) contains Credit Agreement-specific knowledge about `applicableRates.tiers` and `lenderCommitments`. Consider adding a `table_post_processing` hook in the plugin config, or document that Credit Agreements require this custom step.

##### Phase 4 Deep Implementation (Round 2 — Textract FORMS/Checkbox Specialist)

**Fixed `extract_forms()` — Key Changes:**

The core bug fix adds `SELECTION_ELEMENT` handling alongside existing `WORD` handling in the value child loop. Key additions:

1. **New `SELECTION_CONFIDENCE_THRESHOLD` (75%)** — Separate from 85% text threshold. Checkboxes are binary detection; handwritten marks score 70-85% and must not be dropped.
2. **`valueType` field** — Every result carries `"text"`, `"selection"`, or `"selection_with_text"` so normalizer knows how to interpret.
3. **`include_tables` parameter** — Controls whether `['FORMS']` or `['FORMS', 'TABLES']` is sent to Textract.
4. **Three-way value handling** — Pure selection, pure text, and mixed (`[X] Other: explain here`).

```python
# In the value child loop (replacing current WORD-only check):
if child_block['BlockType'] == 'WORD':
    value_text += child_block.get('Text', '') + ' '
    has_words = True
elif child_block['BlockType'] == 'SELECTION_ELEMENT':
    has_selection = True
    selection_status = child_block.get('SelectionStatus', 'NOT_SELECTED')
    selection_confidence = child_block.get('Confidence', 0)
    value_type = 'selection'
```

**SECOND BUG: `extract_tables()` Has Same Issue (lines 1421-1426)**

Table cells can also contain `SELECTION_ELEMENT` children. Fix the same way:

```python
# In extract_tables() cell content loop:
if child_block['BlockType'] == 'WORD':
    cell_text += child_block.get('Text', '') + ' '
elif child_block['BlockType'] == 'SELECTION_ELEMENT':
    sel_status = child_block.get('SelectionStatus', 'NOT_SELECTED')
    cell_text += f'[{sel_status}] '
```

**BSA Requires FORMS + TABLES Combined ($0.065/page):**

| FeatureTypes Requested | Selection elements in FORMS | Selection elements in TABLE CELL |
|------------------------|----------------------------|---------------------------------|
| `['FORMS']` | YES | NO — dropped |
| `['TABLES']` | NO | YES |
| `['FORMS', 'TABLES']` | YES | YES |

BSA page 2 (risk assessment) has checkboxes inside grid/table structures. Must use `['FORMS', 'TABLES']`. Cost difference: $0.075/doc (5 pages × $0.015). Negligible vs. missing compliance-critical checkboxes.

**`process_pages_forms_parallel()` Implementation:**

Follows exact pattern of existing `process_pages_queries_parallel()` (line 516) and `process_pages_tables_parallel()` (line 579):

```python
def process_pages_forms_parallel(page_images, bucket, include_tables=False):
    """Parallel FORMS extraction across multiple pages.
    Merges key-value pairs: highest confidence wins for duplicate keys.
    For BSA 5-page forms: ~10-15s sequential → ~3-4s parallel.
    """
    # ThreadPoolExecutor with MAX_PARALLEL_WORKERS
    # Each page → _process_single_page_forms(page_idx, image_bytes, bucket, include_tables)
    # Merge: keep highest-confidence result for duplicate field keys across pages
    # Track sourcePage for audit trail
    # Return: {keyValues, fieldCount, selectionFieldCount, pageResults, _extractionMetadata}
```

**Complete BSA Profile Extraction Strategy:**

```python
def extract_bsa_profile_multi_page(bucket, key, document_id, page_numbers, pdf_stream, ...):
    # 1. Render all pages to images (PyMuPDF at 150 DPI)
    # 2. process_pages_forms_parallel(page_images, bucket, include_tables=True)
    # 3. extract_signatures() on last page (certification)
    # 4. PyPDF raw text for normalizer cross-referencing
    # Returns: {forms, signatures, rawText, processingTimeSeconds}
```

**Updated BSA Cost Estimate:**

| Stage | Service | Details | Cost |
|-------|---------|---------|------|
| Router | Claude 3 Haiku | ~5-page text classification | ~$0.003 |
| Textract | FORMS + TABLES | 5 pages × $0.065/page | ~$0.325 |
| Textract | SIGNATURES | 1 page × $0.015/page | ~$0.015 |
| Normalizer | Claude 3.5 Haiku | Forms data + raw text | ~$0.015 |
| Lambda + SF | Compute + orchestration | | ~$0.001 |
| **Total** | | | **~$0.36** |

Processing time estimate: ~4-6 seconds (parallel) vs. ~12-15s (sequential). Well under 60s target.

**CDK Environment Variable for Selection Threshold:**

```typescript
environment: {
    SELECTION_CONFIDENCE_THRESHOLD: '75.0',  // Lower for checkbox binary detection
},
```

**Updated Phase 4 Tasks:**

- [ ] **BUG FIX:** Update `extract_forms()` (line 1565) — handle `SELECTION_ELEMENT` blocks, add `valueType`, `selectionStatus` fields
- [ ] **BUG FIX:** Update `extract_tables()` (lines 1421-1426) — same `SELECTION_ELEMENT` fix
- [ ] Add `SELECTION_CONFIDENCE_THRESHOLD` env var (75.0) to extractor Lambda in CDK
- [ ] Implement `_process_single_page_forms()` helper (insert after line 513)
- [ ] Implement `process_pages_forms_parallel()` (insert after line 702)
- [ ] Implement `extract_bsa_profile_multi_page()` orchestrator
- [ ] BSA pages use `include_tables=True` for checkboxes in table cells

##### Phase 4 BSA Extraction Accuracy Details (Round 4 — BSA Extraction Accuracy Specialist)

**Page-by-Page Extraction Strategy:**

| Page | Content | Textract Features | Expected Fields | Key Challenges |
|------|---------|-------------------|----------------|----------------|
| 1 | Legal Entity Info (company name, Tax ID, entity type, NAICS, addresses) | FORMS + TABLES | ~20-25 key-value pairs | Entity Type may be checkbox group; Tax ID often handwritten |
| 2 | Risk Assessment (AML, PEP, fraud, cash intensive, sector flags) | FORMS + TABLES (**critical**) | ~15-20 boolean/selection + 2-3 text | **Highest-risk page** — checkboxes in table cells require TABLES |
| 3 | Beneficial Ownership / Controlling Party (name, DOB, SSN, ID, citizenship) | FORMS + TABLES | ~30-35 fields (2 person records) | SSN/DOB handwritten PII; distinguish Controlling Party vs. Owner 1 |
| 4-5 | Beneficial Owners 2-4, Trust Info | FORMS + TABLES | ~60-75 fields (most empty) | Repeating labels ("Full Name" 4x); detect empty vs. partially filled |

**Checkbox Confidence Tiers (normalizer handling):**

| Confidence Range | Normalizer Behavior |
|-----------------|---------------------|
| >= 90% | **High confidence** — use value directly, no flag |
| 75-89% | **Medium confidence** — use value, add note in `validation.validationNotes` |
| < 75% | **Low confidence** — use value but flag for **mandatory human review** |

**Normalizer Checkbox Interpretation Rules (for BSA prompt template):**

1. `SELECTED` = `true`, `NOT_SELECTED` = `false` (explicit mapping)
2. If confidence < 75%, still return value but add: `"Low confidence NOT_SELECTED (XX%) for field Y — manual verification recommended"`
3. **Mutual exclusivity** for radio groups (Entity Type, Risk Rating): only one should be `true`. If multiple `SELECTED`, use highest confidence
4. **Neither checked** (both `NOT_SELECTED`): return `null` with validation note
5. **Both checked** (both `SELECTED`): return `true` (conservative for compliance) with validation note
6. **Conflict with text**: prefer `SELECTION_ELEMENT` status (visual evidence); add validation note about potential conflict

**DPI Configuration Per Plugin:**

Current pipeline uses `IMAGE_DPI = 150`. AWS recommends 300 DPI for handwritten text. Compromise: 200 DPI for BSA forms balances accuracy and payload size.

```python
# BSA plugin config addition:
"extraction": {
    "render_dpi": 200,  # Higher DPI for handwritten forms (default: 150)
    "textract_features": ["FORMS", "TABLES"],
    "target_all_pages": True,
}
```

The extractor reads this via `plugin_config.get("extraction", {}).get("render_dpi", int(os.environ.get("IMAGE_DPI", 150)))`.

**SIGNATURES Optimization — Page 5 Only:**

BSA certification/signature section is exclusively on page 5. Processing SIGNATURES on all 5 pages: $0.075. On page 5 only: $0.015. **Savings: $0.060/doc.**

```python
# In extract_bsa_profile_multi_page():
# FORMS+TABLES on all 5 pages
forms_results = process_pages_forms_parallel(all_page_images, bucket, include_tables=True)
# SIGNATURES on page 5 only
signature_result = extract_signatures(page_images[4], bucket)  # 0-indexed
```

**QUERIES Decision: Not Needed Initially**

BSA is a standardized form with well-defined labels. FORMS handles standard key-value pairs effectively. QUERIES add $0.030-0.075/doc (8-21% cost increase) with marginal accuracy gain for standardized fields. **Add QUERIES as a targeted enhancement later only if accuracy testing reveals gaps.**

**Sync Parallel Processing (Confirmed Correct):**

For BSA's 5 pages, sync `AnalyzeDocument` (1 page/call, 5 concurrent) completes in 3-5s. Async `StartDocumentAnalysis` adds 10-30s overhead for job submission + polling. The existing `ThreadPoolExecutor` with `MAX_PARALLEL_WORKERS=30` pattern is correct.

**Validated BSA Cost Breakdown:**

| Stage | Service | Details | Cost |
|-------|---------|---------|------|
| Router | Claude 3 Haiku | ~5-page text classification | ~$0.003 |
| Textract | FORMS + TABLES | 5 pages × $0.065/page | $0.325 |
| Textract | SIGNATURES | 1 page (page 5 only) × $0.015 | $0.015 |
| Normalizer | Claude 3.5 Haiku | ~8K input + 2K output tokens | ~$0.018 |
| Lambda + SF | 4 invocations + orchestration | | ~$0.001 |
| KMS | 2 API calls (envelope encrypt) | | ~$0.000006 |
| **Total** | | | **~$0.36** |

##### Phase 4 Extractor Refactoring Details (Round 7 — Extractor Handler Refactoring Specialist)

**Dead Code Analysis — 981 lines (41%) removable after validation:**

| Line Range | Content | Lines | Reason for Deletion |
|-----------|---------|-------|---------------------|
| 60-287 | `CREDIT_AGREEMENT_QUERIES` dict | 228 | Migrated to `credit_agreement.py` plugin (sections.*.queries) |
| 705-993 | `extract_credit_agreement_section()` | 289 | Replaced by generic `extract_section()` |
| 1680-2076 | `extract_loan_agreement_multi_page()` | 397 | Replaced by generic `extract_section()` with `includePypdfText` and `lowQualityPages` |
| 2107-2159 | Credit Agreement branch in `lambda_handler` | 53 | Replaced by `sectionConfig` path |
| 2162-2228 | Loan Agreement branch in `lambda_handler` | 67 | Replaced by `sectionConfig` path |

> **IMPORTANT:** These lines are NOT deleted in Phase 4 — they are retained with `[LEGACY]` comments during blue/green transition. The `lambda_handler` first checks for `sectionConfig` (new path), then falls through to legacy paths. Deletion happens in Phase 5 cleanup after golden file regression tests pass.

**New Generic `extract_section()` Function (~130 lines):**

Replaces all 3 hardcoded extraction functions with a single config-driven entry point:

```python
def extract_section(
    bucket: str, key: str, document_id: str,
    section_config: dict, execution_name: str,
) -> dict:
    """Generic section extraction driven by plugin sectionConfig.

    Steps:
    1. Download PDF once (not per-branch like current code)
    2. Read pages list from section_config["pages"]
    3. Render pages to images at section_config render_dpi (default 150)
    4. For each feature in section_config["textractFeatures"]:
       call run_textract_feature_parallel(feature, page_images, ...)
    5. If section_config["includePypdfText"]: extract raw text via PyPDF
    6. If section_config["extractSignatures"]: run SIGNATURES on designated pages
    7. Return combined results dict with section metadata
    """
```

**New `run_textract_feature_parallel()` Function (~50 lines):**

Consolidates 4 identical table extraction branches (lines 803-890) and the 3-way image/single/S3 branch pattern (~120 lines total, repeated ~10 times) into one dispatcher:

```python
def run_textract_feature_parallel(
    feature: str, page_images: list[bytes] | None, bucket: str,
    temp_key: str = "", queries: list | None = None,
    include_tables: bool = False,
) -> dict:
    """Dispatch to the correct parallel processor by Textract feature type.

    Handles: QUERIES, TABLES, FORMS, SIGNATURES
    Automatically routes: multi-page → parallel, single-page → direct, no images → S3
    """
```

**New `process_pages_forms_parallel()` Function (~95 lines):**

Required for BSA 5-page form extraction. Mirrors existing `process_pages_tables_parallel()` and `process_pages_queries_parallel()` patterns:

- Uses `ThreadPoolExecutor` with `MAX_PARALLEL_WORKERS`
- Merges key-value pairs across pages (highest confidence wins for duplicate keys)
- Tracks `selectionFieldCount` and `perPageResults` for audit trail
- BSA performance: ~10-15s sequential → ~3-4s parallel

**SELECTION_ELEMENT Bug Fix (2 locations):**

*Bug Location 1: `extract_forms()` (lines 1617-1640)* — Value child loop only processes `WORD` blocks, silently dropping checkbox/radio `SELECTION_ELEMENT` blocks.

Fix adds:
- New constant `SELECTION_CONFIDENCE_THRESHOLD = 75.0` (lower than text threshold — handwritten checkmarks score 70-85%)
- New `include_tables` parameter (FORMS+TABLES combined for BSA page 2 checkboxes in table cells)
- Three value types: `"text"`, `"selection"`, `"selection_with_text"` (mixed checkbox + label)
- Selection-specific fields: `selectionStatus`, `selectionConfidence`, `textValue` (for mixed)

*Bug Location 2: `extract_tables()` (lines 1421-1426)* — Cell content loop also only processes `WORD` blocks.

Fix: Add `SELECTION_ELEMENT` handling → `cell_text += f'[{sel_status}] '` and `hasSelection` flag on cell_data.

**S3 Intermediate Storage — `write_extraction_to_s3()` (~55 lines):**

Prevents Step Functions 256KB payload limit by writing full extraction results to S3:

```python
def write_extraction_to_s3(
    bucket: str, document_id: str, section_name: str,
    result: dict, execution_name: str,
) -> dict:
    """Write to s3://bucket/extractions/{executionName}/{sectionName}.json
    Return lightweight reference with summary flags (hasQueries, hasTables,
    hasForms, hasSignatures) for normalizer to decide what to process."""
```

**Refactored `lambda_handler` Entry Point (~30 lines added):**

```python
def lambda_handler(event, context):
    # ---- New path: Map state with sectionConfig ----
    section_config = event.get("sectionConfig")
    if section_config:
        result = extract_section(bucket, key, document_id, section_config, execution_name)
        s3_ref = write_extraction_to_s3(bucket, document_id, result["sectionName"], result, execution_name)
        return s3_ref

    # ---- [LEGACY] paths preserved during blue/green transition ----
    # ... existing credit_agreement and loan_agreement branches unchanged ...
```

**5-Step Incremental Diff Strategy:**

| Step | Action | Risk | Test Gate |
|------|--------|------|-----------|
| 1 | Add new constants + helper functions (non-breaking) | None | Unit tests pass |
| 2 | Apply SELECTION_ELEMENT bug fixes to `extract_forms()` + `extract_tables()` (improves existing path) | Low — existing tests still pass | Forms extraction returns selection fields |
| 3 | Add `sectionConfig` entry point to `lambda_handler` (non-breaking — falls through to legacy) | Low — new path only activates with `sectionConfig` key | Manual test with sample sectionConfig event |
| 4 | Deploy with both paths active. Run golden file regression | Medium — first real dual-path execution | Golden files match for Credit Agreement + Loan Package |
| 5 | Remove legacy code (Phase 5 cleanup after validation) | High — point of no return | All 3 document types pass golden regression |

**Net Code Changes (Phase 4):**

| Category | Lines Added | Lines Modified | Lines Deleted (Phase 5) |
|----------|------------|---------------|------------------------|
| Constants | 3 | 0 | 0 |
| `_process_single_page_forms()` | 18 | 0 | 0 |
| `process_pages_forms_parallel()` | 95 | 0 | 0 |
| `run_textract_feature_parallel()` | 50 | 0 | 0 |
| `write_extraction_to_s3()` | 55 | 0 | 0 |
| `extract_section()` | 130 | 0 | 0 |
| `extract_forms()` bug fix | 0 | 113 (full rewrite) | 0 |
| `extract_tables()` bug fix | 0 | 6 | 0 |
| `lambda_handler` new path | 30 | 0 | 0 |
| **Totals (Phase 4)** | **~381** | **~119** | **0** |
| **Cleanup (after validation)** | 0 | 0 | **~981** |
| **Net after cleanup** | — | — | File shrinks from ~2379 to ~1779 lines (25% reduction) |

**Consolidation Opportunities Resolved:**

| Pattern | Occurrences | Lines Saved | Consolidated Into |
|---------|-------------|-------------|-------------------|
| 4 identical table extraction branches (lines 803-890) | 4 | ~88 | `run_textract_feature_parallel("TABLES", ...)` |
| 3-way image/single/S3 branch | ~10 | ~120 | `run_textract_feature_parallel()` dispatcher |
| 2 signature detection blocks (lines 893-918 + 1953-2016) | 2 | ~90 | `extract_section()` checks `extractSignatures` from config |
| 2 independent PDF downloads (lines 2130 + 1735) | 2 | ~20 | `extract_section()` downloads once at top |

#### Phase 5: Normalizer Refactor (Template-Driven Prompts)

**Goal:** Normalizer Lambda loads prompt templates from plugin config instead of hardcoded prompt builders.

**Files to modify:**
- `lambda/normalizer/handler.py` — Replace 3 prompt builders with generic template-based normalization

**Tasks:**
- [ ] Create generic `build_normalization_prompt(plugin_config, raw_extraction_data)` function — **Use `.replace("{extraction_data}", data)` not `.format()`** to avoid `{{`/`}}` escaping issues. See 4-layer architecture in Phase 5 Generated Prompt Templates section below.
- [x] Move `build_credit_agreement_prompt()` (lines 50-318) content to plugin prompt template — **PRE-GENERATED (Round 6):** `prompts/credit_agreement.txt` (302 lines)
- [x] Move `build_loan_agreement_prompt()` (lines 321-730) content to plugin prompt template — **PRE-GENERATED (Round 6):** `prompts/loan_package.txt` (382 lines)
- [x] Move general normalization prompt (lines 910-1050) to plugin prompt template — **PRE-GENERATED (Round 5):** `prompts/common_preamble.txt` + `prompts/common_footer.txt`
- [x] Write BSA Profile normalization prompt template (checkbox interpretation, beneficial owner array, PII fields) — **PRE-GENERATED (Round 6):** `prompts/bsa_profile.txt` (247 lines)
- [ ] Generic function loads template, injects extraction data, calls Bedrock
- [ ] Remove document-type detection logic (lines 829-893) — plugin ID comes from event
- [ ] **REGRESSION TEST:** Normalize existing Credit Agreement extraction → compare to golden file
- [ ] **REGRESSION TEST:** Normalize existing Loan Package extraction → compare to golden file

> **Implementation note:** 4 of 9 Phase 5 tasks are pre-generated (all prompt template files). Remaining work: write `build_normalization_prompt()` function, wire it into the handler, remove old detection logic, run regression tests.

**Success criteria:** Normalizer uses prompt templates from plugin config. Same inputs produce same outputs for existing types. BSA Profile normalization works.

##### Phase 5 Research Insights

**Composable Prompt Builder, Not Monolithic Templates (Architecture Review):**

The current prompt builders are 270-400 lines each with 15+ dynamic sections, field-specific extraction rules, format constraints, and cross-reference validation. Converting these to flat text templates with `str.format()` is error-prone. Use a composable approach instead:

```python
def build_normalization_prompt(plugin_config, raw_extraction_data):
    """Assemble prompt from multiple template fragments."""
    parts = []
    parts.append(load_template("common_preamble.txt"))  # Shared across all plugins

    # Per-field extraction instructions generated from output schema
    for field_name, field_spec in plugin_config["output_schema"]["properties"].items():
        parts.append(format_field_instruction(field_name, field_spec))

    # Plugin-specific normalization rules
    parts.append(load_template(plugin_config["normalization"]["prompt_template"]))

    # Shared critical instructions footer (no hallucination, decimal conversion, etc.)
    parts.append(load_template("common_footer.txt"))

    return "\n\n".join(parts)
```

This is more maintainable than 300-line text files per document type. The "critical instructions" footer (normalizer lines 305-317 and 702-727) is nearly identical between builders — extract it as `common_footer.txt`.

**Normalizer Document-Type Detection Elimination (Pattern Analysis):**

The 64-line heuristic detection block (normalizer lines 829-893) that inspects payload structure to infer document type is the fragile part. With `pluginId` passed explicitly in the event from the router, this entire block is eliminated. The normalizer simply does: `plugin = get_plugin(event["pluginId"])`.

##### Phase 5 Deep Implementation (Round 3 — Normalizer Prompt Architect)

**1. Composable Prompt Architecture — 4 Layers:**

The existing 3 prompt builders (lines 50-318, 321-730, 910-1050) share substantial structure. Replace with a composable 4-layer system:

```python
def build_normalization_prompt(plugin_config: dict, raw_extractions: list[dict]) -> str:
    """Assemble normalization prompt from 4 composable layers."""
    parts = []

    # Layer 1: Common preamble (shared across ALL plugins)
    # - Role definition, extraction context, JSON output format
    parts.append(load_template("common_preamble.txt"))

    # Layer 2: Schema-driven field instructions (auto-generated from output_schema)
    normalization_cfg = plugin_config["normalization"]
    for field_name, field_spec in plugin_config["output_schema"]["properties"].items():
        instruction = format_field_instruction(field_name, field_spec, normalization_cfg)
        parts.append(instruction)

    # Layer 3: Plugin-specific normalization rules
    # - BSA: checkbox interpretation, beneficial owner array, PII masking notes
    # - Credit Agreement: pricing tier formatting, lender commitment tables
    # - Loan Package: sub-document cross-referencing
    parts.append(load_template(normalization_cfg["prompt_template"]))

    # Layer 4: Common footer — critical instructions (shared across ALL plugins)
    # - "Do not hallucinate values not present in the source"
    # - "Convert all percentages to decimal format"
    # - "Use null for missing fields, not empty strings"
    # - "Return valid JSON only"
    parts.append(load_template("common_footer.txt"))

    return "\n\n".join(parts)
```

**2. `format_field_instruction()` — Schema-Driven:**

Generates per-field instructions from the plugin's output schema, eliminating the manual field-by-field prompt writing:

```python
def format_field_instruction(field_name: str, field_spec: dict, normalization_cfg: dict) -> str:
    """Generate extraction instruction for a single field from its JSON schema definition."""
    field_type = field_spec.get("type", "string")
    description = field_spec.get("description", "")
    enum_values = field_spec.get("enum", [])

    instruction = f"- **{field_name}**"
    if description:
        instruction += f": {description}"

    # Type-specific instructions
    if field_type == "boolean":
        instruction += " → Return true/false. For checkbox/radio fields, interpret marks as true."
    elif field_type == "number":
        instruction += " → Return as number (not string). Convert percentages to decimal (e.g., 8.5% → 0.085)."
    elif field_type == "array":
        items_type = field_spec.get("items", {}).get("type", "object")
        instruction += f" → Return as JSON array of {items_type}s. Exclude empty/unfilled entries."
    elif enum_values:
        instruction += f" → Must be one of: {', '.join(enum_values)}"

    # Plugin-specific overrides (e.g., BSA checkbox confidence threshold)
    overrides = normalization_cfg.get("field_overrides", {})
    if field_name in overrides:
        instruction += f" {overrides[field_name]}"

    return instruction
```

**3. BSA Profile Normalization Prompt Template (`bsa_profile.txt`):**

```text
## BSA Profile Specific Instructions

### Checkbox/Radio Interpretation
- SELECTION_ELEMENT blocks with SelectionStatus "SELECTED" → true
- SelectionStatus "NOT_SELECTED" → false
- If confidence < 75%: still return the value but flag in validation notes
- For mutually exclusive radio groups (e.g., Entity Type), only one should be true
- Cross-reference checkbox results with surrounding text labels for confirmation

### Beneficial Owners Array
- Extract up to 4 beneficial owners from pages 3-5
- Each owner is a separate object in the beneficialOwners array
- SKIP completely empty owner sections (all fields blank)
- Include an owner if ANY field is filled (even just a name)
- ownershipPercentage: return as number (e.g., 25, not "25%")

### Risk Assessment Booleans
- Page 2 contains a risk assessment matrix with Yes/No checkboxes
- Map each checkbox to the corresponding boolean field
- If BOTH Yes and No are checked (ambiguous): return true and add validation note
- If NEITHER is checked: return null and add validation note

### PII Fields (for downstream encryption marking)
- SSN/TIN fields: extract as-is (e.g., "123-45-6789"), encryption handled post-normalization
- Government ID numbers: extract as-is
- Date of Birth: extract in YYYY-MM-DD format
```

**4. Common Footer Template (`common_footer.txt`):**

Extracted from the nearly identical blocks at normalizer lines 305-317 and 702-727:

```text
## Critical Instructions (All Document Types)

1. Do NOT hallucinate or infer values not explicitly present in the extracted text.
2. Use null for any field where the value cannot be determined from the source data.
3. Do NOT use empty strings "" — use null instead.
4. Convert all percentage values to decimal format (e.g., 8.5% → 0.085).
5. Convert all currency amounts to plain numbers without symbols (e.g., $1,500,000 → 1500000).
6. Preserve exact names, addresses, and identifiers as they appear in the source.
7. Return ONLY valid JSON. No explanatory text before or after the JSON object.
8. If a field appears multiple times with different values, use the most recent/authoritative instance.
```

**5. S3 Extraction Data Resolution:**

Since Phase 3 stores extraction results in S3 (not in the Step Functions payload), the normalizer must resolve S3 references before building the prompt:

```python
def resolve_extractions(event: dict) -> list[dict]:
    """Load extraction results from S3 references in Map state output."""
    extractions = event.get("extractions", [])
    resolved = []
    for ext in extractions:
        s3_ref = ext.get("s3ResultRef")
        if s3_ref:
            obj = s3_client.get_object(Bucket=s3_ref["bucket"], Key=s3_ref["key"])
            resolved.append(json.loads(obj["Body"].read()))
        else:
            resolved.append(ext)  # Inline data (backward compat during transition)
    return resolved
```

**6. Post-Processing Preserved Per-Plugin:**

The existing post-processing functions (`_post_process_credit_agreement`, `_post_process_loan_data`) contain type-specific cleanup logic (Decimal conversion, rate formatting, lender table parsing). These move to plugin-specific post-processors:

```python
# In plugin config:
"normalization": {
    "prompt_template": "credit_agreement.txt",
    "post_processor": "post_process_credit_agreement",  # Function name in plugin module
    "llm_model": "claude-3-5-haiku",
}

# In normalizer:
plugin = get_plugin(plugin_id)
post_proc_name = plugin["normalization"].get("post_processor")
if post_proc_name:
    post_proc_fn = getattr(plugin_module, post_proc_name)
    normalized_data = post_proc_fn(normalized_data)
```

##### Phase 5 Generated Prompt Templates (Round 5 — BSA Normalization Prompt Generator)

**Generated files in `lambda/layers/plugins/python/document_plugins/prompts/`:**

**`common_preamble.txt` (47 lines)** — Shared normalization preamble for all document types:
- Role definition ("financial document data normalizer")
- `{extraction_data}` placeholder for raw Textract/PyPDF insertion
- 7 normalization rule categories: interest rates/percentages → decimal, currency → numeric, names → preserve exact/Title Case, dates → ISO 8601, addresses → structured with state codes, missing data → null (never hallucinate), booleans → JSON true/false
- Ends with "FIELD-BY-FIELD EXTRACTION INSTRUCTIONS:" to lead into Layer 2 (schema-driven fields)

**`common_footer.txt` (18 lines)** — Shared critical instructions:
- JSON-only output (no preamble/markdown blocks)
- Start with `{{` end with `}}` (escaped braces for Python template safety)
- 14 rules including: null over empty strings, preserve exact identifiers, include ALL array entries, validation notes for uncertain extractions, page/section audit trail, conservative extraction
- **Implementation note:** Use `.replace("{extraction_data}", data)` not `.format()` to avoid `{{`/`}}` escaping issues

**Prompt Assembly in Normalizer (4-layer composable architecture):**

```python
def build_normalization_prompt(plugin_id: str, extraction_data: str) -> str:
    """Assemble prompt from 4 layers: preamble + fields + plugin-specific + footer."""
    plugin = get_plugin(plugin_id)
    prompts_dir = Path(__file__).parent.parent / "layers/plugins/python/document_plugins/prompts"

    # Layer 1: Common preamble with extraction data
    preamble = (prompts_dir / "common_preamble.txt").read_text()
    preamble = preamble.replace("{extraction_data}", extraction_data)

    # Layer 2: Schema-driven field instructions (auto-generated from plugin config)
    field_instructions = []
    for section_name, section in plugin.get("sections", {}).items():
        for field in section.get("fields", []):
            field_instructions.append(format_field_instruction(field, plugin["normalization"]))

    # Layer 3: Plugin-specific instructions (BSA checkbox rules, etc.)
    plugin_template = (prompts_dir / plugin["normalization"]["prompt_template"]).read_text()

    # Layer 4: Common footer
    footer = (prompts_dir / "common_footer.txt").read_text()

    return preamble + "\n".join(field_instructions) + "\n\n" + plugin_template + "\n\n" + footer
```

##### Phase 5 Normalizer Refactoring Details (Round 8 — Normalizer Handler Refactoring Specialist)

**Dead Code Analysis — 1,342 lines (52%) removable after validation:**

| Line Range | Content | Lines | Reason for Deletion |
|-----------|---------|-------|---------------------|
| 321-728 | `build_loan_agreement_prompt()` | 408 | Replaced by `build_normalization_prompt()` with `loan_agreement.txt` template |
| 729-1050 | `build_credit_agreement_prompt()` | 322 | Replaced by `build_normalization_prompt()` with `credit_agreement.txt` template |
| 1051-1263 | `build_loan_package_prompt()` | 213 | Replaced by `build_normalization_prompt()` with `loan_package.txt` template |
| 1264-1350 | `detect_document_type()` | 87 | Replaced by `pluginId` from event (router already classified) |
| 2175-2240 | Document type dispatch in `lambda_handler` | 66 | Replaced by generic plugin-driven path |
| 2241-2487 | `apply_loan_agreement_defaults()` + `apply_credit_agreement_defaults()` | 246 | Replaced by plugin `field_overrides` config |

**`resolve_s3_extraction_refs()` function (~40 lines):**

```python
def resolve_s3_extraction_refs(extraction_results: list[dict], bucket: str) -> dict:
    """Download section extraction JSONs from S3 and merge into one dict.
    Uses ThreadPoolExecutor for parallel S3 downloads (~0.5-1s total).
    Returns: {"sections": {"sectionName": {extraction_data}, ...}}
    """
```

**Refactored `lambda_handler` Entry Point:**

```python
def lambda_handler(event, context):
    # ---- New path: plugin-driven normalization ----
    plugin_id = event.get("pluginId")
    if plugin_id:
        plugin = get_plugin(plugin_id)
        extraction_refs = event.get("extractions", [])
        raw_data = resolve_s3_extraction_refs(extraction_refs, bucket)
        prompt = build_normalization_prompt(plugin, raw_data)
        # ... invoke Bedrock, parse response, write to DynamoDB ...
        return result

    # ---- [LEGACY] paths preserved during blue/green transition ----
    # ... existing document type detection and prompt building unchanged ...
```

**5-Step Diff Strategy:**

| Step | Action | Risk |
|------|--------|------|
| 1 | Add `resolve_s3_extraction_refs()` + `build_normalization_prompt()` (non-breaking) | None |
| 2 | Add `pluginId` entry point to `lambda_handler` (falls through to legacy) | Low |
| 3 | Deploy with both paths active. Run golden file regression | Medium |
| 4 | Remove legacy prompt builders + document type detection | High |
| 5 | Remove `apply_*_defaults()` functions | High |

**Net Code Changes:**

| Category | Lines Added | Lines Modified | Lines Deleted (cleanup) |
|----------|------------|---------------|------------------------|
| `resolve_s3_extraction_refs()` | 40 | 0 | 0 |
| `build_normalization_prompt()` | 80 | 0 | 0 |
| `lambda_handler` new path | 45 | 0 | 0 |
| **Totals (Phase 5)** | **~165** | **~0** | **0** |
| **Cleanup (after validation)** | 0 | 0 | **~1,342** |
| **Net after cleanup** | — | — | File shrinks from ~2,577 to ~1,400 lines (46% reduction) |

##### Phase 5 Complete Function Implementations (Round 9 — Normalizer Handler Implementation Specialist)

**1. `resolve_s3_extraction_refs(extraction_results, bucket)` — Complete Implementation (~70 lines):**

Downloads extraction results from S3 `extractions/` prefix using `ThreadPoolExecutor(max_workers=7)` for parallel downloads. Handles 3 cases: `s3ResultRef` (new Map state output), inline `results` (testing/small payloads), and missing/failed sections. Returns `(raw_extraction_data, failed_sections)` tuple. Failed sections logged as validation notes, not errors.

**2. `build_normalization_prompt(plugin, raw_extraction_data)` — Complete Implementation (~80 lines):**

Implements 4-layer composable architecture:
1. `common_preamble.txt` (role definition + `{extraction_data}` placeholder)
2. Plugin-specific template from `normalization.prompt_template` (e.g., `loan_agreement.txt`)
3. `common_footer.txt` (critical JSON-only instructions)
4. Extraction data injected via `.replace("{extraction_data}", json.dumps(data))`

Template loading uses `importlib.resources` or falls back to `os.path.join(os.path.dirname(__file__))` for Lambda layer compatibility. Caches loaded templates in module-level dict.

**3. `invoke_bedrock_normalize(prompt, plugin)` — Complete Implementation (~80 lines):**

Reads `llm_model`, `max_tokens`, `temperature` from plugin's `normalization` config. Uses assistant prefill trick (`{"role": "assistant", "content": "{"}`) to force JSON output (preserved from existing line 1275).

**CRITICAL behavioral change**: On JSON parse failure, returns minimal valid structure with `confidence: "low"` + validation note instead of raising `ValueError`. This keeps the document in PENDING_REVIEW state for human inspection rather than killing the Step Functions execution. Existing code at line 1336 raises, losing all extraction work.

**4. `apply_field_overrides(result, plugin)` — Complete Implementation (~50 lines):**

Reads `normalization.field_overrides` from plugin config. Each override is a dot-path → default-value mapping (e.g., `"loanData.loanAgreement._extractedCodes.billingFrequency": "C:MONTHLY"`). Only applies when current value is `None` or `""`. Records all applied overrides in `validation.validationNotes`.

**Limitation**: Cannot express conditional defaults (e.g., "if LINE OF CREDIT then billingType=INTEREST ONLY"). Complex contextual defaults in existing `apply_loan_agreement_defaults()` (lines 1651-1661) remain in the legacy function during transition.

**5. Refactored `lambda_handler` — Plugin path branching:**

The key architectural decision: if event contains `pluginId`, take new `_handle_plugin_path()`. Otherwise, fall through to existing legacy code verbatim. This preserves 100% backward compatibility.

`_handle_plugin_path()` 9-step flow:
1. Load plugin from registry
2. Resolve S3 extraction references (parallel download)
3. Build normalization prompt from templates
4. Invoke Bedrock with plugin LLM config
5. Apply field overrides
6. Post-processing: signature validation, pricing tier preservation (credit_agreement), failed section notes
7. Calculate costs (Textract pages, token usage)
8. Store to DynamoDB + S3 audit trail
9. Return summary

**DynamoDB Write Integration:**

The existing `store_to_dynamodb()` (line 2026) is called unchanged. Critical mapping: `extractedData` receives `normalized_data['loanData']` (not the full dict). The plugin's `output_schema` drives what goes inside `loanData`:
- **credit_agreement**: `{"creditAgreement": {agreementInfo, parties, facilities, ...}}`
- **loan_package**: `{"promissoryNote": {...}, "closingDisclosure": {...}, "form1003": {...}}`
- **bsa_profile**: `{"bsaProfile": {legalEntity, riskAssessment, beneficialOwners, ...}}`
- **loan_agreement**: `{"loanAgreement": {documentInfo, loanTerms, interestDetails, ...}}`

Frontend already reads `extractedData` by checking which top-level key is present — no frontend changes needed for existing types.

**Event Flow (new plugin path expects):**
```json
{
  "pluginId": "credit_agreement",
  "extractionResults": [
    {"sectionName": "agreementInfo", "pageCount": 5, "s3ResultRef": {"bucket": "...", "key": "extractions/doc-abc/agreementInfo.json"}}
  ]
}
```

**Helper functions:**
- `_count_textract_pages(event, plugin_id)` — Counts pages from extraction results, handles hybrid extraction, Map state output, and legacy formats
- `_build_plugin_summary(plugin_id, normalized_data, signature_validation)` — Per-type summary with key fields (borrower, amount, rate, maturity)

#### Phase 6: PII Field-Level Encryption

**Goal:** Encrypt PII fields declared in plugin config before DynamoDB write.

**Files to modify:**
- `lambda/normalizer/handler.py` — Add encryption step after normalization
- `lambda/api/handler.py` — Add decryption step when reading PII fields
- `lib/stacks/document-processing-stack.ts` — Add KMS key, grant Lambda access

**Tasks:**
- [ ] Create KMS key in CDK stack for PII encryption
- [ ] Write `encrypt_pii_fields(data, plugin_config)` utility — reads `pii_fields` from plugin, encrypts matching values with KMS
- [ ] Write `decrypt_pii_fields(data, plugin_config)` utility — decrypts for authorized API reads
- [ ] Call `encrypt_pii_fields()` in normalizer before DynamoDB write
- [ ] Call `decrypt_pii_fields()` in API handler for document detail and review endpoints
- [ ] Add IAM policy: only API Lambda and normalizer Lambda can use the KMS key
- [ ] Test: BSA Profile SSN field is encrypted in DynamoDB, decrypted in API response
- [ ] Test: Loan Package data (no PII markers) passes through unencrypted (no regression)

**Success criteria:** PII fields in DynamoDB are KMS-encrypted ciphertext. API returns decrypted values to authorized callers.

##### Phase 6 Research Insights

**CRITICAL PREREQUISITE: API Authentication Required (Security Review):**

Every API endpoint is publicly accessible with zero authentication (CDK stack lines 881-940). No Cognito, no API key, no Lambda authorizer. Once Phase 6 adds PII decryption, unprotected endpoints become the single gateway to all decrypted PII (SSN, DOB, government IDs). Add mandatory prerequisite tasks:

- [ ] **BLOCKING:** Add Cognito User Pool authorizer or IAM-based auth to all API Gateway methods
- [ ] Implement role-based access (read-only users cannot call approve/reject/fields endpoints)
- [ ] Restrict CORS to CloudFront distribution domain only (currently `allowOrigins: ['*']` at 3 locations)

**CRITICAL PREREQUISITE: PII Log Sanitization (Security Review):**

All Lambda handlers log full event payloads to CloudWatch in plaintext. BSA Profile classification snippets, normalization prompts, and Bedrock responses will contain SSN, DOB, and beneficial ownership data. Specific locations:

- `lambda/api/handler.py:689` — logs entire API request
- `lambda/router/handler.py:1589` — logs full event
- `lambda/router/handler.py:1627` — logs classification result (may contain PII text snippets)
- `lambda/normalizer/handler.py:1294,1337` — logs Bedrock response content on error

Add prerequisite tasks:

- [ ] **BLOCKING:** Audit and sanitize ALL `print()` statements across all Lambda handlers
- [ ] Create `safe_log(event, scrub_fields)` utility that strips PII field values
- [ ] Set CloudWatch Logs retention to minimum necessary (7 days debug, 90 days max)
- [ ] Reduce Step Functions log level from `ALL` to `ERROR` (line 818 in CDK stack)

**Use KMS Envelope Encryption (Performance Review):**

Per-field KMS `Encrypt` calls add 5-15ms each. For BSA Profile with 4 owners × 3 PII fields = 12 calls = 60-180ms. Use envelope encryption instead:

1. Call `kms:GenerateDataKey` once per document (~10ms) — get plaintext data key
2. Encrypt all PII fields locally with AES-256 using the data key
3. Store encrypted data key alongside the DynamoDB item
4. On decryption: call `kms:Decrypt` once to unwrap data key, decrypt all fields locally

Total latency: **10-20ms** instead of 60-180ms. Consider using the AWS Encryption SDK for Python (v4.x with KMS keyring) which handles envelope encryption, commitment policy, and encryption context automatically.

**Encryption Fail-Closed (Security Review):**

If `encrypt_pii_fields()` raises an exception, the normalizer must NOT proceed with the DynamoDB write. A try/except that falls through would write plaintext PII. Make this explicit:

```python
try:
    encrypted_data = encrypt_pii_fields(normalized_data, plugin_config)
except Exception as e:
    # FAIL CLOSED — do not write unencrypted PII
    raise RuntimeError(f"PII encryption failed, aborting write: {e}")
```

**KMS Key Policy Scope Is Incomplete (Security Review):**

The plan grants KMS access to API Lambda and normalizer Lambda only, but misses:

- **DynamoDB Stream** (currently `NEW_AND_OLD_IMAGES`) — stream consumers receive encrypted ciphertext without context
- **S3 audit trail** — the normalizer writes to `audit/{documentId}/`. If encryption happens before the DynamoDB write but after the S3 audit write, the audit copy contains plaintext PII
- **Step Functions execution history** (`LogLevel.ALL`) — captures full state transition payloads including normalized data

Add tasks to address:

- [ ] Document exact encryption timing relative to S3 audit write
- [ ] Either encrypt PII in S3 audit copy or ensure audit bucket has access controls + KMS encryption
- [ ] Evaluate DynamoDB Stream configuration (filter PII fields from events or grant decrypt to stream consumers)

**Existing Form 1003 PII Already Unencrypted (Security Review):**

The normalizer already processes SSN, DOB, email, and phone for Form 1003 (Loan Package) — stored unencrypted in DynamoDB since v1.0.0. Add to Loan Package plugin config:

```python
"pii_fields": [
    {"path": "form1003.borrowerInfo.ssn", "type": "ssn"},
    {"path": "form1003.borrowerInfo.dateOfBirth", "type": "dob"},
    {"path": "form1003.borrowerInfo.email", "type": "email"},
]
```

And add a one-time migration script to re-encrypt existing data.

**PII on List Endpoints (Performance Review):**

List endpoints (`GET /documents`, `GET /review`) should NOT decrypt PII fields — return masked values or omit PII entirely. Only decrypt on detail endpoints (`GET /documents/{id}`, `GET /review/{id}`). This avoids N KMS calls on list pages. Add task:

- [ ] List endpoints return PII fields as masked (e.g., `***-**-1234`) or omitted
- [ ] Decrypt only on detail/review-by-id endpoints with audit logging

**Decryption Audit Trail (Security Review):**

BSA/KYC compliance under FinCEN regulations requires auditable PII access. Log every decryption event with: requestor identity, documentId, timestamp, fields decrypted. Do NOT log decrypted values. Add CloudTrail monitoring for KMS key usage.

##### Phase 6 Deep Implementation (Round 2 — KMS PII Encryption Architect)

**1. KMS Envelope Encryption Pattern (`lambda/common/pii_crypto.py`):**

Uses AWS Encryption SDK v4.x with KMS keyring:

```python
from aws_cryptographic_material_providers.mpl.models import CreateAwsKmsKeyringInput
from aws_encryption_sdk import CommitmentPolicy

# One-time setup per Lambda cold start
kms_keyring = mat_prov.create_aws_kms_keyring(
    CreateAwsKmsKeyringInput(kms_key_id=KMS_KEY_ARN)
)

def encrypt_pii_fields(data, pii_paths, document_id):
    """Envelope encryption: 1 GenerateDataKey + local AES for all fields."""
    for path_spec in pii_paths:
        value = resolve_json_path(data, path_spec['json_path'])  # Handles [*] wildcards
        if value:
            ciphertext, _ = client.encrypt(
                source=json.dumps(value).encode(),
                keyring=kms_keyring,
                encryption_context={'documentId': document_id, 'fieldPath': path_spec['json_path']},
            )
            set_json_path(data, path_spec['json_path'], {
                '__encrypted': True,
                '__ciphertext': base64.b64encode(ciphertext).decode(),
            })
    return data
```

Encryption context ties each ciphertext to its document and field — cannot be copied to a different document.

**2. Cognito User Pool Auth (CDK):**

```typescript
const userPool = new cognito.UserPool(this, 'FinancialDocsUserPool', {
  selfSignUpEnabled: false,  // Admin-created accounts only
  signInAliases: { email: true },
  mfa: cognito.Mfa.REQUIRED,
  mfaSecondFactor: { sms: false, otp: true },
  passwordPolicy: { minLength: 12, requireUppercase: true, requireDigits: true, requireSymbols: true },
});

// RBAC groups
new cognito.CfnUserPoolGroup(this, 'AdminsGroup', { groupName: 'Admins', userPoolId: userPool.userPoolId });
new cognito.CfnUserPoolGroup(this, 'ReviewersGroup', { groupName: 'Reviewers', userPoolId: userPool.userPoolId });
new cognito.CfnUserPoolGroup(this, 'ViewersGroup', { groupName: 'Viewers', userPoolId: userPool.userPoolId });

const authorizer = new apigateway.CognitoUserPoolsAuthorizer(this, 'ApiAuthorizer', {
  cognitoUserPools: [userPool],
});
// Apply to all methods: { authorizer, authorizationType: apigateway.AuthorizationType.COGNITO }
```

API Lambda extracts caller identity from `event.requestContext.authorizer.claims`. Only `Admins` group can access decrypted PII.

**3. CloudWatch Log Sanitization (`lambda/common/safe_log.py`):**

Drop-in `safe_log()` replacement for `print()`:

```python
# Migration per Lambda (2-line change per file):
from common.safe_log import safe_log, safe_json_dumps

# BEFORE: print(f"API Lambda received event: {json.dumps(event)}")
# AFTER:  safe_log(f"API Lambda received event: {safe_json_dumps(event)}")
```

Scrubs SSN patterns (`123-45-6789` → `***-**-6789`), EIN patterns, email addresses, phone numbers. For JSON objects, identifies PII by field name (`ssn`, `dateOfBirth`, `taxId`, etc.) and redacts values. Safe name fields (`functionName`, `bucketName`) are preserved.

**Specific `print()` statements to replace:**
- `lambda/api/handler.py:689` — full API request event
- `lambda/normalizer/handler.py:2175` — full Step Functions payload with extracted SSN/DOB
- `lambda/router/handler.py:1589` — full event
- `lambda/api/handler.py:770-772` — error responses leak `str(e)` internals

**4. PII Access Audit Table (`lambda/common/audit_logger.py`):**

Every PII decryption logs to DynamoDB audit table (queryable) + CloudWatch (real-time alerting):

```python
def log_pii_access(document_id, fields_decrypted, requestor, access_reason, api_endpoint, source_ip):
    """Log who accessed what PII, when, and why. NEVER logs actual PII values."""
    # DynamoDB: PK=documentId, SK=timestamp#auditEventId
    # GSI: RequestorIndex (query all access by a user)
    # GSI: EventTypeIndex (query all ACCESS_DENIED events)
    # TTL: 6 years (exceeds 5-year BSA minimum)
```

CDK for audit table:
```typescript
const auditTable = new dynamodb.Table(this, 'PiiAuditTable', {
  tableName: 'financial-docs-pii-audit',
  partitionKey: { name: 'documentId', type: dynamodb.AttributeType.STRING },
  sortKey: { name: 'sortKey', type: dynamodb.AttributeType.STRING },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  pointInTimeRecovery: true,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
  timeToLiveAttribute: 'expiresAt',  // 6-year TTL
});
// GSIs for RequestorIndex and EventTypeIndex
```

**5. FinCEN BSA/KYC Compliance Requirements:**

| Requirement | Source | Implementation |
|-------------|--------|---------------|
| AES-256 encryption at rest for NPI | FFIEC, OCC Bulletin 2001-47 | KMS envelope encryption (above) |
| Encryption in transit | GLBA Safeguards Rule | API Gateway HTTPS + CloudFront redirect (already in place) |
| Annual key rotation | NIST SP 800-57 | KMS `enableKeyRotation: true` |
| PII access audit trail | BSA/AML Manual Section 8.1 | DynamoDB audit table + CloudWatch (above) |
| 5-year data retention for BSA/KYC records | 31 CFR 1010.430(a) | S3 lifecycle: retain 6 years, Glacier after 90 days |
| Segregation of duties | FinCEN Guidance FIN-2016-G003 | Cognito groups: Admin / Reviewer / Viewer |
| Unusual activity monitoring | BSA/AML Manual | CloudWatch alarm: >5 denied PII access in 5 minutes |

Add S3 Object Lock for compliance mode on audit bucket prefix:
```typescript
{ id: 'BSARetentionPolicy', prefix: 'audit/', expiration: cdk.Duration.days(2190) } // 6 years
```

**6. CloudWatch Alarm for Suspicious PII Access:**

```typescript
// Metric filter: count PII_ACCESS_DENIED events
const piiDeniedFilter = new logs.MetricFilter(this, 'PiiAccessDeniedFilter', {
  logGroup: apiLambda.logGroup,
  filterPattern: logs.FilterPattern.stringValue('$.eventType', '=', 'PII_ACCESS_DENIED'),
  metricNamespace: 'FinancialDocs/Security',
  metricName: 'PiiAccessDenied',
});
// Alarm: >5 denied attempts in 5 minutes
```

**Updated Phase 6 Tasks:**

- [ ] **BLOCKING:** Add Cognito User Pool with MFA + Admin/Reviewer/Viewer groups to CDK
- [ ] **BLOCKING:** Add CognitoUserPoolsAuthorizer to all API Gateway methods
- [ ] **BLOCKING:** Audit and replace ALL `print()` with `safe_log()` across 4 Lambda handlers
- [ ] **BLOCKING:** Reduce Step Functions log level from `ALL` to `ERROR`
- [ ] Create `lambda/common/pii_crypto.py` with envelope encrypt/decrypt
- [ ] Create `lambda/common/safe_log.py` with PII scrubbing
- [ ] Create `lambda/common/audit_logger.py` with DynamoDB + CloudWatch logging
- [ ] Add PII audit DynamoDB table to CDK stack
- [ ] Add CloudWatch alarm for suspicious PII access
- [ ] Add `lambda/layers/encryption/requirements.txt` with `aws-encryption-sdk>=4.0.0`
- [ ] Add S3 retention policy (6 years) on `audit/` prefix
- [ ] Restrict CORS to CloudFront domain at 3 locations in CDK
- [ ] Update `frontend/src/types/index.ts` with `piiMasked?: boolean`
- [ ] One-time migration script for existing Form 1003 SSN/DOB encryption

**New Files for Phase 6:**
| File | Purpose |
|------|---------|
| `lambda/common/pii_crypto.py` | Envelope encrypt/decrypt using AWS Encryption SDK |
| `lambda/common/safe_log.py` | PII-scrubbing `print()` replacement |
| `lambda/common/audit_logger.py` | PII access audit logging to DynamoDB + CloudWatch |
| `lambda/layers/encryption/requirements.txt` | `aws-encryption-sdk>=4.0.0` |

##### Phase 6 Implementation Details (Round 8 — PII Encryption Implementation Specialist)

**`safe_log.py` module — PII-aware logging with redaction:**
- Drop-in replacement for `print()` across all 266 call sites (6 CRITICAL)
- Reads `pii_fields` from plugin registry to know which JSON paths to redact
- Masking strategies: SSN → `***-**-6789` (last 4), DOB → `1985-**-**` (year only), names → initials, addresses → city/state only
- Handles nested paths and array wildcards (`beneficialOwners[*].ssn`)
- Log levels: DEBUG, INFO, WARN, ERROR (respects `LOG_LEVEL` env var)

**`pii_crypto.py` module — Envelope encryption implementation:**
- `encrypt_pii_fields(record, plugin_id) -> dict` — Encrypts all fields at plugin's `pii_fields` paths
- `decrypt_pii_fields(record, plugin_id) -> dict` — Decrypts for API responses
- `is_encrypted(record) -> bool` — Checks for `_pii_envelope` key (idempotency)
- Uses KMS `GenerateDataKey` (1 API call per record, ~10-20ms) + AES-256-GCM for field encryption
- Stores encrypted data key + per-field ciphertexts in `_pii_envelope` dict alongside the record
- Plaintext field values replaced with `"[ENCRYPTED]"` marker

**Migration scripts:**
- `scripts/encrypt-existing-pii.py` — Scan + encrypt unencrypted Form 1003 SSN/DOB + BSA PII. Dry-run mode (default). Idempotent (skips records with `_pii_envelope`). Rate-limited to avoid KMS/DynamoDB throttling.
- `scripts/decrypt-for-rollback.py` — Decrypt all encrypted records back to plaintext. Safety checks: verifies KMS key is active, CDK stack exists. Requires `--execute --confirm` flags.

**Prerequisite: Update `loan_package.py` pii_paths:**
```python
"pii_paths": [
    {"json_path": "form1003.borrowerInfo.ssn", "pii_type": "ssn", "masking_strategy": "partial"},
    {"json_path": "form1003.borrowerInfo.dateOfBirth", "pii_type": "dob", "masking_strategy": "full"},
],
```

**28-step deployment checklist (4 phases):**
1. **Pre-deployment** (Day -1): DynamoDB backup, verify no in-flight executions, update loan_package pii_paths, add `cryptography` dependency, code review
2. **Infrastructure** (Day 0 AM): Deploy KMS key + audit table + Cognito (no Lambda code changes yet)
3. **Data migration** (Day 0 PM): Dry-run → review → execute migration script → spot-check 3 records
4. **Lambda code** (Day 0 Eve): Deploy safe_log + pii_crypto integration, smoke test new + existing records
5. **Frontend + Auth** (Day 1): Deploy Cognito-integrated frontend, enable API Gateway authorizer, verify 401 for unauthenticated

**Rollback procedure:**
- Option A (code-only): Revert Lambda code → run decrypt-for-rollback → cdk deploy pre-Phase-6
- Option B (full): Run decrypt-for-rollback → git checkout pre-phase-6 tag → cdk deploy → schedule KMS key deletion (30-day pending)

#### Phase 7: BSA Profile Frontend Components

**Goal:** Display BSA Profile extracted data in the frontend.

**Files to modify:**
- `frontend/src/types/index.ts` — Add BSA Profile types
- `frontend/src/components/ExtractedValuesPanel.tsx` — Add BSA fields rendering
- `frontend/src/pages/ReviewDocument.tsx` — Add BSA review rendering

**Tasks:**
- [ ] Add `BSAProfileData` interface to `frontend/src/types/index.ts`:
  - `legalEntity`: Company Name, Tax ID, Entity Type, NAICS, addresses, etc.
  - `riskAssessment`: PEP status, cash intensive, energy/real estate/MSB flags (all booleans/enums)
  - `beneficialOwners`: Array of owner objects (name, DOB, SSN, address, ID, citizenship)
  - `trustInfo`: Optional trust details
- [ ] Add `documentType: string` (replace union literal) in Document interface
- [ ] Add `BSAProfileFields` component in `ExtractedValuesPanel.tsx`
  - Legal Entity section with FieldRow for each field
  - Risk Assessment section with boolean/enum display
  - Beneficial Owners section with array rendering (1-4 owners)
  - Trust Information section (conditional)
- [ ] Add BSA rendering to `ReviewDocument.tsx`
- [ ] Add "BSA_PROFILE" to status badge and document list displays
- [ ] Test: Upload BSA Profile → view extracted data → review workflow

**Success criteria:** BSA Profile data displays correctly in dashboard, detail view, and review workflow.

##### Phase 7 Deep Implementation (Round 3 — Frontend BSA Component Designer)

**1. TypeScript Interface Hierarchy (`frontend/src/types/index.ts`):**

```typescript
export interface BSAAddress {
  street?: string;
  city?: string;
  state?: string;
  zipCode?: string;
  country?: string;
}

export interface BSALegalEntity {
  companyName?: string;
  dbaName?: string;
  taxId?: string;              // PII — encrypted at rest
  taxIdType?: string;
  entityType?: string;
  stateOfOrganization?: string;
  countryOfOrganization?: string;
  dateOfOrganization?: string;
  naicsCode?: string;
  naicsDescription?: string;
  businessDescription?: string;
  principalAddress?: BSAAddress;
  phoneNumber?: string;
  emailAddress?: string;
  isPubliclyTraded?: boolean;
  stockExchange?: string;
  tickerSymbol?: string;
  isExemptEntity?: boolean;
  exemptionType?: string;
}

export interface BSARiskAssessment {
  overallRiskRating?: 'LOW' | 'MEDIUM' | 'HIGH' | 'PROHIBITED';
  hasAmlHistory?: boolean;
  hasPepAssociation?: boolean;
  hasFraudHistory?: boolean;
  hasSarHistory?: boolean;
  isOnOfacList?: boolean;
  isCashIntensive?: boolean;
  isMoneyServiceBusiness?: boolean;
  isThirdPartyPaymentProcessor?: boolean;
  industryRiskFlags?: string[];
  requiresEdd?: boolean;
  eddReason?: string;
  riskNotes?: string;
}

export interface BSABeneficialOwner {
  fullName?: string;
  dateOfBirth?: string;        // PII
  ssn?: string;                // PII
  address?: BSAAddress;
  citizenship?: string;
  identificationDocType?: string;
  identificationDocNumber?: string;  // PII
  identificationDocState?: string;
  identificationDocExpiration?: string;
  ownershipPercentage?: number;
  isPep?: boolean;
  controlPerson?: boolean;
}

export interface BSATrustInfo {
  trustName?: string;
  trustType?: string;
  trusteeName?: string;
  dateEstablished?: string;
  stateOfFormation?: string;
  trustTaxId?: string;         // PII
}

export interface BSACertificationInfo {
  signatoryName?: string;
  signatoryTitle?: string;
  certificationDate?: string;
  signatureStatus?: 'SIGNED' | 'ELECTRONIC' | 'UNSIGNED';
}

export interface BSAProfileData {
  legalEntity?: BSALegalEntity;
  riskAssessment?: BSARiskAssessment;
  beneficialOwners?: BSABeneficialOwner[];
  trustInfo?: BSATrustInfo;
  certificationInfo?: BSACertificationInfo;
  pageNumber?: number;
}
```

**2. Document Type Extensibility:**

Change `documentType` from union literal to `string` in `Document` interface (line 3). Add display name utility:

```typescript
const DOCUMENT_TYPE_DISPLAY_NAMES: Record<string, string> = {
  'LOAN_PACKAGE': 'Loan Package',
  'CREDIT_AGREEMENT': 'Credit Agreement',
  'LOAN_AGREEMENT': 'Loan Agreement',
  'BSA_PROFILE': 'BSA/CDD Profile',
};

export function getDocumentTypeDisplayName(docType?: string): string {
  if (!docType) return 'Unknown';
  return DOCUMENT_TYPE_DISPLAY_NAMES[docType] || docType.replace(/_/g, ' ');
}
```

Use this in `Documents.tsx` (line 134) and `ReviewDocument.tsx` (lines 1126-1131) instead of hardcoded if/else chains.

**3. Key Components for `ExtractedValuesPanel.tsx`:**

**PII Masking Utility:**
```typescript
function maskPiiValue(value?: string, type?: string): string | undefined {
  if (!value) return value;
  if (type === 'ssn') return `***-**-${value.slice(-4)}`;
  if (type === 'taxId') return `**-***${value.slice(-4)}`;
  if (type === 'dob') return `****-**-${value.slice(-2)}`;
  if (type === 'idNumber') return `${'*'.repeat(Math.max(0, value.length - 4))}${value.slice(-4)}`;
  return value;
}
```

**BooleanFlag Component** — renders boolean fields as colored Yes/No badges:
```typescript
function BooleanFlag({ label, value, invertColor = false }: {
  label: string; value?: boolean; invertColor?: boolean;
}) {
  if (value === undefined || value === null) return null;
  const isTrue = value === true;
  const colorClass = invertColor
    ? (isTrue ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700')
    : (isTrue ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500');
  return (
    <div className="flex justify-between items-center py-1.5 px-2">
      <span className="text-sm text-gray-500">{label}</span>
      <span className={`text-xs font-medium px-2 py-0.5 rounded ${colorClass}`}>
        {isTrue ? 'Yes' : 'No'}
      </span>
    </div>
  );
}
```

**BeneficialOwnerCard** — collapsible card per owner with PII masking:
- Expand/collapse toggle (first owner expanded by default)
- PEP and Control Person badges on the header
- Ownership percentage badge
- All PII fields (SSN, DOB, ID number) masked when `piiMasked=true`

**BSAProfileFields** — main component with 5 sections:
1. **Legal Entity Information** — FieldRow for each field, teal-100 left border
2. **Risk Assessment** — Overall risk rating colored badge, boolean flags with `invertColor=true` for red-when-true, industry risk flags as orange chips
3. **Beneficial Owners** — Array of BeneficialOwnerCard, "N of 4" counter, empty slot indicators
4. **Trust Information** — Conditional section (only if trustInfo present)
5. **Certification** — Signature status colored badge

**GenericDataFields Fallback** — for future plugin types before custom components exist:
```typescript
function GenericDataFields({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-1">
      {Object.entries(data).map(([key, value]) => {
        if (key.startsWith('_') || key === 'pageNumber' || value == null) return null;
        if (typeof value === 'object' && !Array.isArray(value)) {
          return (<div key={key}><h4>...</h4><GenericDataFields data={value} /></div>);
        }
        return <FieldRow key={key} label={humanize(key)} value={String(value)} />;
      })}
    </div>
  );
}
```

**4. Review Workflow (`ReviewDocument.tsx`):**

Add `renderBSAProfileData()` following the existing `renderCreditAgreementData()` pattern, and update `renderExtractedData()` to detect `bsaProfile` key.

Editable fields during review: Legal Entity (all), Risk Assessment (all), Beneficial Owners (all non-PII). PII fields (SSN, DOB, Tax ID, ID numbers) are NOT directly editable — corrections go through rejection workflow.

Array field corrections use dot-notation paths:
```json
{ "corrections": { "bsaProfile.beneficialOwners.0.fullName": "John A. Smith" } }
```

**5. Visual Design:**

| Element | Color | Rationale |
|---------|-------|-----------|
| BSA section accent | teal (`border-teal-100`, `text-teal-600`) | Not used by any existing doc type |
| Risk rating HIGH | `bg-red-100 text-red-700` | Consistent with existing severity colors |
| Risk rating MEDIUM | `bg-yellow-100 text-yellow-700` | Standard warning color |
| Risk flags (true) | `bg-red-100 text-red-700` | `invertColor=true` — red means risk |
| PEP badge | `bg-red-100 text-red-700` | High-risk indicator |
| Control Person badge | `bg-blue-100 text-blue-700` | Neutral indicator |
| Lucide icons | Shield (section), Briefcase (entity), AlertCircle (risk), User (owners), FileText (trust), PenTool (cert) | All already available in lucide-react |

**6. Files Changed Summary:**

| File | Changes |
|------|---------|
| `frontend/src/types/index.ts` | Add 7 BSA interfaces, change documentType to string, add `piiMasked`, add display name utility |
| `frontend/src/components/ExtractedValuesPanel.tsx` | Add `piiMasked` prop, maskPiiValue, BooleanFlag, BeneficialOwnerCard, BSAProfileFields, GenericDataFields fallback |
| `frontend/src/components/DocumentViewer.tsx` | Pass `piiMasked` to ExtractedValuesPanel |
| `frontend/src/pages/ReviewDocument.tsx` | Add renderBSAProfileData, update renderExtractedData, use getDocumentTypeDisplayName |
| `frontend/src/pages/Documents.tsx` | Replace hardcoded type display with getDocumentTypeDisplayName |

##### Phase 7 Cognito Authentication Integration (Round 9 — Frontend Cognito Integration Designer)

**1. `frontend/src/services/auth.ts` — Cognito Authentication Service (~120 lines):**

Uses AWS Amplify v6 tree-shakeable imports (`@aws-amplify/auth`, `@aws-amplify/core`). Key functions:
- `configureAuth(userPoolId, clientId)` — One-time Amplify configuration from Vite env vars
- `signIn(email, password)` → `AuthResult` with `success`, `user`, `challengeName`, `error`
- `signOut()` — Swallows errors (clearing local state is sufficient)
- `getCurrentUser()` → `AuthUser | null` (userId, email, groups, displayName)
- `getIdToken()` → string (auto-refreshes within 5 min of expiry via Amplify v6)
- `getUserGroups()` → `UserRole[]` from `cognito:groups` JWT claim

Types: `AuthUser` (userId, email, groups, displayName), `UserRole` = 'Admin' | 'Reviewer' | 'Viewer', `AuthResult` (success, user?, challengeName?, error?)

**2. `frontend/src/contexts/AuthContext.tsx` — React Context Provider (~100 lines):**

- `configureAuth()` called in `useEffect` on mount from `VITE_COGNITO_USER_POOL_ID` + `VITE_COGNITO_CLIENT_ID`
- `checkAuthState()` on mount detects existing sessions (Amplify persists to localStorage)
- `isLoading` starts `true` → prevents flash of login page on refresh
- `hasRole(role)` and `hasAnyRole(...roles)` convenience methods
- Exports `useAuth()` hook

**3. `frontend/src/pages/Login.tsx` — Login Page Component (~130 lines):**

Full-screen centered form (no Layout sidebar). Features:
- `from` state captures attempted route for post-login redirect
- Cognito challenge handling: `NEW_PASSWORD_REQUIRED` (guidance text), MFA (contact admin)
- Error mapping: `NotAuthorizedException` → "Incorrect email or password", `UserNotFoundException` → "No account found", etc.
- `autoComplete` attributes for password manager integration
- Spinner during submission, disabled state

**4. Modified `frontend/src/services/api.ts` — Authorization Header Injection:**

Minimal changes to existing `fetchApi`:
- Import `getIdToken` from `./auth`
- Before every `fetch`: call `getIdToken()`, inject `Authorization: Bearer ${idToken}`
- On token failure: redirect to `/login`
- On `response.status === 401`: redirect to `/login`
- `uploadFile` (presigned POST to S3) does NOT need auth header

**5. Modified `frontend/src/App.tsx` — Route Protection:**

Three new components:
- `ProtectedRoute` — Checks `isAuthenticated` + `isLoading`, redirects to `/login` preserving attempted path
- `RoleGuard` — Checks `hasAnyRole(allowedRoles)`, shows "Access Denied" for insufficient permissions
- Login route is public (outside ProtectedRoute)

**Route Access Matrix:**

| Route | Viewer | Reviewer | Admin |
|-------|--------|----------|-------|
| `/` (Dashboard) | Yes | Yes | Yes |
| `/documents` | Yes | Yes | Yes |
| `/documents/:id` | Yes | Yes | Yes |
| `/upload` | No | Yes | Yes |
| `/review` | No | Yes | Yes |
| `/review/:id` | No | Yes | Yes |
| `/login` | Public | Public | Public |

**6. Modified `frontend/src/components/Layout.tsx` — Sidebar User Info:**

- Filter navigation items by role (hide Review/Upload for Viewer)
- Replace footer with: user avatar initial, display name, role badge, sign-out button

**7. PII Visibility Rules (Server-Side Masking):**

The frontend does NOT mask PII. Server-side approach (defense in depth):
- **Viewer role**: API returns pre-masked values (`***-**-6789`). Full SSN never reaches browser.
- **Reviewer/Admin**: API returns decrypted values from KMS
- `piiMasked: boolean` response field indicates which version was returned
- `FieldRow` shows lock icon when value matches `\*{2,}` pattern

**8. Modified `frontend/src/pages/ReviewDocument.tsx` — Authenticated Identity:**

Replace manual `reviewerName` text input with `const { user } = useAuth(); const reviewerName = user?.email`. Eliminates self-reported name; `reviewedBy` is now verifiable Cognito identity.

**Environment Variables (from CDK stack outputs):**
```
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
VITE_COGNITO_CLIENT_ID=1234567890abcdef
VITE_API_URL=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod
```

## Cross-Cutting Concerns (Round 4)

### Error Handling Strategy

**Per-Iteration Error Handling in Map State:**

The Map state uses per-iteration `addCatch` (since `toleratedFailurePercentage` is DistributedMap-only). When a section extraction fails, the catch inserts an error placeholder; other sections continue.

| Error Code | Source | Step Functions Behavior |
|------------|--------|------------------------|
| `PLUGIN_CONFIG_ERROR` | Router | `classifyDocument.addCatch` — fail entire execution |
| `CLASSIFICATION_FAILED` | Router | `classifyDocument.addCatch` — fail entire execution |
| `SECTION_EXTRACTION_FAILED` | Extractor (per Map iteration) | `extractSection.addCatch` — insert error placeholder, continue |
| `TEXTRACT_THROTTLED` | Extractor | `extractSection.addRetry` (max 3, backoff 2x) — retry |
| `NORMALIZATION_FAILED` | Normalizer | `normalizeData.addCatch` — fail entire execution |
| `PII_ENCRYPTION_FAILED` | Normalizer | `normalizeData.addCatch` — fail entire execution (fail-closed) |
| `S3_WRITE_FAILED` | Extractor | Handled inline — fallback to inline payload |

**Normalizer Handling of Partial Failures:**

When the normalizer receives Map state output containing failed sections:

1. Filter out sections with `status: "FAILED"` before building LLM prompt
2. Log which sections failed with error codes
3. Set `validation.isValid = false` if any critical section failed (e.g., `agreementInfo`)
4. Set `validation.confidence = "low"` if more than 30% of sections failed
5. Populate `validation.requiredFields` with missing data from failed sections

**PII Encryption Failure — Fail-Closed:**

```python
# In normalizer, AFTER normalization, BEFORE DynamoDB write:
try:
    encrypted_data = encrypt_pii_fields(normalized_data, plugin_config["pii_paths"])
except Exception as e:
    # FAIL CLOSED: Do NOT write unencrypted PII
    table.update_item(
        Key={"documentId": document_id, "documentType": doc_type},
        UpdateExpression="SET #status = :status, updatedAt = :ts, encryptionError = :err",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "ENCRYPTION_FAILED",
            ":ts": datetime.utcnow().isoformat() + "Z",
            ":err": str(e)[:200],
        },
    )
    raise RuntimeError(f"PII encryption failed, aborting write: {e}")
```

**DLQ Recommendation:** Add SQS Dead Letter Queue for trigger Lambda async invocation failures. For Step Functions, add CloudWatch Events rule on `FAILED`/`TIMED_OUT` executions → SQS for investigation.

### Structured Logging

**Current State:** 266 `print()` statements across Lambda handlers. 6 are **CRITICAL PII risks** that log extracted financial data:

| Lambda | Line(s) | Risk | Content Logged |
|--------|---------|------|----------------|
| Normalizer | 1294 | **CRITICAL** | First 500 chars of Bedrock response (contains SSN, names, amounts) |
| Normalizer | 1305 | **CRITICAL** | Bedrock response body with extracted PII |
| Normalizer | 1337 | **CRITICAL** | Full LLM normalization response containing PII |
| Router | 1438 | **CRITICAL** | Credit Agreement section response (may contain document text) |
| Router | 1575 | **CRITICAL** | Classification response parse error (contains page snippets) |
| Router | 1589 | **CRITICAL** | Full event dump with document content |

**`safe_log()` Implementation** (`lambda/common/safe_log.py`):

```python
import re, json

PII_PATTERNS = [
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '***-**-XXXX'),     # SSN
    (re.compile(r'\b\d{2}-\d{7}\b'), '**-***XXXX'),              # EIN
    (re.compile(r'\b\d{2}/\d{2}/\d{4}\b'), 'DOB_REDACTED'),     # DOB
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), 'EMAIL_REDACTED'),
    (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), 'PHONE_REDACTED'),
]

PII_FIELD_NAMES = {"ssn", "socialSecurityNumber", "taxId", "ein", "dateOfBirth",
                   "dob", "email", "phone", "idNumber", "trustTaxId"}

def scrub_string(text: str) -> str:
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text

def scrub_dict(obj: dict) -> dict:
    scrubbed = {}
    for key, value in obj.items():
        if key.lower() in {n.lower() for n in PII_FIELD_NAMES}:
            scrubbed[key] = "***REDACTED***"
        elif isinstance(value, str):
            scrubbed[key] = scrub_string(value)
        elif isinstance(value, dict):
            scrubbed[key] = scrub_dict(value)
        elif isinstance(value, list):
            scrubbed[key] = [scrub_dict(v) if isinstance(v, dict) else v for v in value]
        else:
            scrubbed[key] = value
    return scrubbed

def safe_log(message: str, **kwargs):
    print(json.dumps({"message": scrub_string(message), **kwargs}))
```

**Step Functions Logging Level:** Change from `ALL` to `ERROR`. `ALL` logs full state I/O including extracted data with PII.

**Correlation ID Strategy:** The existing `executionId` (format `doc-{docId[:8]}-{timestamp}`) is already unique per processing run and passed through the entire Step Functions execution via `$$.Execution.Name`. No new correlation mechanism needed.

### Deployment Order and Atomicity

**Deployment Sequence:**

```
Phase 0 (Golden Files)     → No CDK changes. Test infrastructure only.
Phase 1 (Plugin Layer)     → CDK: create LayerVersion (no Lambda references it yet)
Phase 2 (Router)           → Lambda code only. Set ROUTER_OUTPUT_FORMAT=dual
                             ✓ Can deploy independently — backward-compatible keys preserved
Phase 3+4 (CDK + Extractor) → MUST deploy together in single `cdk deploy`
                             Map state expects extractionPlan; extractor reads new event format
Phase 5 (Normalizer)       → Deploy after 3+4 validated. Reads S3 refs from new extractor.
Phase 6 Prerequisites      → CDK: Cognito, KMS key, audit table (independent of Lambdas)
Phase 6 (PII Encryption)   → Lambda code changes only
Phase 7 (Frontend)         → S3 + CloudFront. Independent of backend.
```

**Feature Flag for Router:**

```python
ROUTER_OUTPUT_FORMAT = os.environ.get("ROUTER_OUTPUT_FORMAT", "legacy")
# "legacy" → current output only (safe default)
# "dual"   → both old keys + new extractionPlan (Phase 2 deploy)
# "plugin" → new format only (after Map state validated)
```

**Blue/Green via Choice State (Recommended):** During transition, the Step Functions definition contains BOTH Map state and legacy Parallel branches. A Choice state checks `$.extractionPlan` — if present, uses Map; if absent, uses Parallel. This acts as a canary: `ROUTER_OUTPUT_FORMAT=dual` produces both formats, and the Choice state routes accordingly.

### Rollback Procedures

| Phase | Rollback Time | Data Risk | Dependencies | Procedure |
|-------|--------------|-----------|--------------|-----------|
| Phase 0 | Instant | None | None | Delete `tests/golden/` |
| Phase 1 | 3-5 min | None | None | Remove LayerVersion from CDK, deploy |
| Phase 2 | 3-5 min | None | None | Revert handler.py, deploy. In-flight executions still work (backward-compat keys) |
| Phase 3 | 5-10 min | Low (in-flight) | Wait for running executions | Revert CDK. In-flight executions on Map may fail |
| Phase 4 | 3-5 min | None | **Rollback with Phase 3** | Revert handler.py. Cannot exist without Phase 3 |
| Phase 5 | 3-5 min | None | **Rollback with Phase 4** | Revert handler.py. Old normalizer cannot resolve S3 refs |
| Phase 6 | 5 min + migration | **HIGH** | Keep KMS key alive | **Already-encrypted records show ciphertext.** Need decryption migration script |
| Phase 7 | 3-5 min | None | None | Revert frontend, `s3 sync`, CloudFront invalidation |

**Phase 6 Rollback Mitigation (HIGH risk):**

Documents processed after Phase 6 deployment have encrypted PII fields (`{ "__encrypted": true, "__ciphertext": "..." }`). Rollback options:

1. **Keep API decryption but remove normalizer encryption** — new documents write plaintext, old encrypted documents still decrypt
2. **Full rollback with migration script** — decrypt all Phase 6 records back to plaintext (requires KMS key to remain active)

Prepare the decryption migration script **before** deploying Phase 6.

### Configuration Management

**Environment Variables Per Lambda:**

| Variable | Lambda | Status | Purpose |
|----------|--------|--------|---------|
| `ROUTER_OUTPUT_FORMAT` | Router | **New** | `"legacy"` / `"dual"` / `"plugin"` |
| `SELECTION_CONFIDENCE_THRESHOLD` | Extractor | **New** | `75.0` for checkbox detection |
| `S3_EXTRACTION_PREFIX` | Extractor | **New** | `"extractions/"` for S3 intermediate results |
| `KMS_KEY_ARN` | Normalizer, API | **New (Phase 6)** | KMS key for PII encrypt/decrypt |
| `PII_ENCRYPTION_ENABLED` | Normalizer | **New (Phase 6)** | `"true"` / `"false"` feature flag |
| `COGNITO_USER_POOL_ID` | API | **New (Phase 6)** | Cognito pool for auth validation |
| `PII_AUDIT_TABLE` | API | **New (Phase 6)** | DynamoDB table for PII access audit |

**SSM vs. Environment Variables:** Use environment variables for all static per-deployment config (KMS ARN, feature flags, thresholds). Reserve SSM Parameter Store only for values that need runtime adjustment without redeployment (e.g., Textract TPS settings during load testing). SSM adds ~50-200ms cold start overhead per `GetParameter` call.

## Acceptance Criteria

### Functional Requirements

- [ ] Plugin registry loads 3 plugins: Loan Package, Credit Agreement, BSA Profile
- [ ] Router classifies BSA Profile documents correctly (test with provided sample PDF)
- [ ] Router still classifies Loan Packages and Credit Agreements correctly (golden file regression)
- [ ] Extractor runs Textract FORMS + PyPDF on BSA Profile, Textract QUERIES on Loan Package
- [ ] Normalizer extracts all BSA Profile fields: legal entity info, risk assessment, beneficial owners (1-4), trust
- [ ] Normalizer handles checkboxes: Yes/No → boolean, multi-select → arrays
- [ ] Normalizer handles variable beneficial owner count (1 to 4 filled, rest excluded)
- [ ] PII fields (SSN, DOB, ID numbers) are KMS-encrypted in DynamoDB
- [ ] API returns decrypted PII to authorized callers
- [ ] Frontend displays BSA Profile data with all sections
- [ ] Review workflow works for BSA Profile documents
- [ ] Existing Loan Package processing unchanged (end-to-end regression test)
- [ ] Existing Credit Agreement processing unchanged (end-to-end regression test)

### Non-Functional Requirements

- [ ] BSA Profile processing cost < $1.00 per document (estimated ~$0.36 with FORMS+TABLES at $0.065/page — Round 2 Textract Research)
- [ ] BSA Profile processing time < 1 minute (estimated 16-23 seconds — Performance review)
- [ ] Adding a new document type requires only: plugin config file + frontend component (no router/extractor/normalizer/CDK changes)
- [ ] Lambda cold start with plugin layer < 1 second additional (estimated 10-30ms — Performance review downgraded from 3s target)
- [ ] KMS envelope encryption/decryption adds < 50ms to pipeline (estimated 10-20ms with GenerateDataKey approach — Performance review)
- [ ] **NEW:** API Gateway requires authentication on all endpoints (Security review)
- [ ] **NEW:** No PII appears in CloudWatch Logs (Security review)
- [ ] **NEW:** CORS restricted to CloudFront distribution domain (Security review)
- [ ] **NEW:** Step Functions payload stays under 256KB per state transition (Architecture review)

### Quality Gates

- [ ] Phase 0 golden files committed to `tests/golden/` before any refactoring begins
- [ ] Golden file tests pass for all 3 document types after each phase
- [ ] CDK synth succeeds with new Map state architecture
- [ ] No hardcoded document-type branching remains in router, extractor, or normalizer
- [ ] PII is never logged — audit all `print()` statements (Security review: currently FAILING, must be fixed)
- [ ] **NEW:** PII encryption is fail-closed — if encrypt fails, DynamoDB write aborts (Security review)
- [ ] **NEW:** Plugin contract validates `pii_fields` covers all PII-indicative field names (Security review)
- [ ] **NEW:** Error responses return generic messages, never `str(e)` content (Security review)

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| BSA extraction accuracy | >90% field accuracy on test docs | Manual review of 5 sample BSA profiles |
| Cost per BSA document | < $0.50 | CloudWatch Bedrock + Textract billing metrics |
| Processing time | < 60 seconds | Step Functions execution duration |
| Regression: Loan Package | 100% output match | Golden file diff |
| Regression: Credit Agreement | 100% output match | Golden file diff |
| Plugin add effort | < 2 files changed (excluding plugin config) | Code review |

## Dependencies & Prerequisites

- AWS account with Bedrock access (Claude 3 Haiku, Claude 3.5 Haiku) — already in place
- AWS Textract FORMS feature enabled — already in place
- KMS key creation permissions — verify IAM
- BSA Profile sample PDF for testing — `docs/BSA Profile NEW 2 1 3.pdf` (available)
- Existing golden file outputs for Loan Package and Credit Agreement — need to capture before refactor

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Regression in existing document types | Medium | High | Phase 0: Capture golden files BEFORE any changes. Run diff after every phase. Comparison script committed to `tests/golden/`. |
| Step Functions Map state behavioral differences | Low | High | Test Map state in dev with existing doc types before removing Parallel branches |
| 256KB Step Functions payload limit exceeded | Medium | High | **NEW:** Extractor writes results to S3, passes only S3 reference keys in payload. Normalizer reads from S3. (Architecture + Performance review) |
| Lambda cold start increase from plugin layer | Low | Low | Plugin layer estimated 15-30KB compressed. Adds ~10-30ms to cold start. (Performance review: risk was overestimated — downgraded from Medium to Low impact) |
| Textract FORMS unreliable on handwritten BSA checkboxes | Medium | Medium | LLM normalizer cross-references PyPDF text. Flag low-confidence fields for human review. Current `extract_forms()` already tracks confidence per field. |
| KMS encryption adds latency | Low | Low | Use envelope encryption (1 GenerateDataKey call) instead of per-field Encrypt calls. Latency: ~10-20ms total. (Performance review) |
| Normalizer prompt templates too rigid | Medium | Medium | Use composable prompt builder with fragments (preamble + per-field instructions + footer), not monolithic templates. (Architecture review) |
| **NEW:** API has no authentication — PII exposed publicly | Certain | Critical | **BLOCKING:** Add Cognito/IAM auth before Phase 6. (Security review) |
| **NEW:** PII logged to CloudWatch in plaintext | Certain | Critical | **BLOCKING:** Sanitize all print() statements, create safe_log utility. (Security review) |
| **NEW:** Wildcard CORS allows cross-origin PII access | Certain | High | Restrict CORS to CloudFront domain at 3 locations. (Security review) |
| **NEW:** Textract TPS throttling with concurrent executions | Medium | Medium | Monitor with CloudWatch alarm. Consider reducing MAX_PARALLEL_WORKERS when Map concurrency is high. (Performance review) |

## Testing Strategy (Enhanced Round 4)

### Golden File Regression Tests

**Before Phase 2 starts:**
1. Process 1 Loan Package through current pipeline, capture full DynamoDB output as `golden/loan_package.json`
2. Process 1 Credit Agreement through current pipeline, capture full output as `golden/credit_agreement.json`
3. Store golden files in `tests/golden/` directory

**After each phase:**
1. Process the same test documents through modified pipeline
2. Diff output against golden files (ignore timestamps, execution IDs)
3. Phase does NOT pass until diff is clean

### Unit Tests

**Plugin Registry (`tests/unit/test_plugin_registry.py`):**
- `test_get_plugin_returns_config` — verify `get_plugin("credit_agreement")` returns valid config
- `test_get_plugin_raises_keyerror` — unknown plugin ID raises `KeyError` with available list
- `test_get_all_plugins_returns_3` — registry auto-discovers loan_package, credit_agreement, bsa_profile
- `test_plugin_config_matches_contract` — each plugin satisfies TypedDict contract fields

**Router Dynamic Classification (`tests/unit/test_router_classification.py`):**
- `test_build_classification_prompt_includes_all_plugins` — all 3 plugin keyword sets in prompt
- `test_identify_sections_credit_agreement` — 7 sections identified with correct page ranges
- `test_identify_sections_bsa_profile` — single section, all 5 pages
- `test_backward_compatible_keys_credit_agreement` — `creditAgreementSections` key generated from extractionPlan
- `test_backward_compatible_keys_loan_package` — `promissoryNote`, `closingDisclosure`, `form1003` keys generated

**Normalizer Composable Prompt (`tests/unit/test_normalizer_prompt.py`):**
- `test_prompt_contains_common_preamble` — Layer 1 text appears in assembled prompt
- `test_prompt_contains_all_output_schema_fields` — Layer 2 auto-generates instructions for every field
- `test_format_field_instruction_boolean` — Boolean fields produce "Return true/false" instruction
- `test_format_field_instruction_array` — Array fields produce "Return as JSON array. Exclude empty entries"
- `test_format_field_instruction_enum` — Enum fields list allowed values
- `test_resolve_extractions_s3_refs` — S3 references resolved to full extraction data
- `test_resolve_extractions_inline_passthrough` — Inline data (backward compat) passes through unchanged

**BSA Checkbox Rules (`tests/unit/test_bsa_checkbox_rules.py`):**
- `test_bsa_template_has_selection_element_rules` — Template includes SELECTED/NOT_SELECTED mapping
- `test_bsa_template_has_beneficial_owner_array_rules` — Template handles variable 1-4 owners

### CDK Integration Tests (`tests/integration/test_cdk_synth.py`)

Run `cdk synth --json` and parse CloudFormation template:

- `test_state_machine_has_map_state` — Map type exists after Phase 3
- `test_no_parallel_extraction_states` — Old Parallel branches removed
- `test_map_state_has_item_selector` — `$$.Map.Item.Value` references present
- `test_map_state_max_concurrency` — MaxConcurrency set to 10
- `test_map_state_has_error_handling` — Catch blocks present on iterations
- `test_s3_reference_payload_under_1kb` — Each S3 ref payload well under 256KB
- `test_7_section_combined_payload_under_256kb` — 7 Credit Agreement section refs combined fit

### E2E Test Matrix

| Document Type | Test Scenario | Expected Result | Test Type |
|---|---|---|---|
| Credit Agreement | Golden file regression | 100% output match | E2E |
| Credit Agreement | 7 sections identified | All sections have page numbers | Unit |
| Credit Agreement | Lender table extraction | Lenders with percentages summing to 100% | Integration |
| Credit Agreement | Processing time | < 60s | E2E perf |
| Credit Agreement | Textract pages | < 50 pages targeted | E2E cost |
| Loan Package | Golden file regression | 100% output match | E2E |
| Loan Package | 3 sub-documents detected | promissory_note, closing_disclosure, form_1003 | Unit |
| Loan Package | Legacy key generation | promissoryNote, closingDisclosure, form1003 | Unit |
| BSA Profile | Classification accuracy | Classified as bsa_profile with high confidence | E2E |
| BSA Profile | All 5 pages extracted | extractionPlan.sections[0].sectionPages = [1,2,3,4,5] | Integration |
| BSA Profile | Checkbox interpretation | Boolean fields correctly parsed from SELECTION_ELEMENT | Integration |
| BSA Profile | Beneficial owners (1-4) | Variable count extracted, empty slots excluded | Integration |
| BSA Profile | PII fields present | SSN, DOB, Tax ID extracted (pre-encryption) | Integration |
| BSA Profile | Processing time | < 60s (target: 16-23s) | E2E perf |
| BSA Profile | Cost | < $0.50 (target: $0.36) | E2E cost |
| BSA (scanned) | OCR quality detection | Low-quality pages flagged, Textract fallback | Integration |
| BSA (handwritten) | Checkbox confidence | Low-confidence flags in validationNotes | Integration |
| Any | Plugin not found | KeyError with available plugins listed | Unit |
| Any | Map state partial failure | Failed section logged, others succeed | Integration |
| Any | 10 concurrent uploads | All 10 complete successfully | E2E stress |
| Any | 256KB payload compliance | S3 references used, no overflow | Unit |
| Any | Duplicate document | Deduplication returns cached result | E2E |
| Frontend (BSA) | BSA data display | All sections render in ExtractedValuesPanel | Playwright E2E |
| Frontend (BSA) | PII masking | SSN shows as `***-**-1234` | Playwright E2E |

### Test Data Strategy

**Available test documents (in `docs/`, not `test-documents/`):**

| File | Type | Pages | Usage |
|------|------|-------|-------|
| `docs/CREDIT AGREEMENT.pdf` | Credit Agreement | ~100 | Golden file candidate |
| `docs/AVIA_Amended_Credit_Agreement.pdf` | Amended Credit Agreement | ~100 | Second CA test |
| `docs/TRINITY DISTRIBUTIONS LLC_Loan Agreement_2025-11-17.pdf` | Loan Agreement | ~20 | Golden file candidate |
| `docs/MCS CONTRACTING GROUP LLC_Executed Laser Pro Package_2025-10-07.pdf` | Loan Package | ~30 | Golden file candidate |
| `docs/BSA Profile NEW 2 1 3.pdf` | BSA Profile | 5 | Primary BSA test |

**Synthetic BSA PDF generation:** Use `reportlab` to create deterministic test PDFs with known field values for unit tests. These can be committed since they contain no real PII.

**Missing test asset:** A scanned/handwritten BSA Profile PDF does not exist. Must be created by printing the digital BSA form, filling by hand, and scanning it. Required for OCR quality detection path testing.

**Test dependencies to add to `pyproject.toml`:**
```toml
[project.optional-dependencies]
test = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "pytest-timeout>=2.2.0",
    "moto[all]>=5.0.0",
    "reportlab>=4.0.0",       # Synthetic PDF generation
    "deepdiff>=7.0",          # Structured golden file comparison
]
```

## File Change Summary

### New Files
| File | Purpose |
|------|---------|
| `tests/golden/capture.py` | Phase 0: End-to-end capture (upload → poll → export DynamoDB record) |
| `tests/golden/compare.py` | Phase 0: Field-level diff with numeric tolerance, order-insensitive arrays, soft match |
| `tests/golden/test_golden_regression.py` | Phase 0: Pytest wrapper for golden file tests |
| `tests/golden/files/credit-agreement.credit_agreement.golden.json` | Phase 0: Credit Agreement regression baseline |
| `tests/golden/files/loan-package.loan_package.golden.json` | Phase 0: Loan Package regression baseline |
| `lambda/layers/plugins/python/document_plugins/__init__.py` | Plugin package init |
| `lambda/layers/plugins/python/document_plugins/registry.py` | Plugin registry (get_plugin, get_all_plugins) |
| `lambda/layers/plugins/python/document_plugins/types/loan_package.py` | Loan Package plugin config |
| `lambda/layers/plugins/python/document_plugins/types/credit_agreement.py` | Credit Agreement plugin config |
| `lambda/layers/plugins/python/document_plugins/types/bsa_profile.py` | BSA Profile plugin config |
| `lambda/layers/plugins/python/document_plugins/prompts/loan_package.txt` | Loan normalization prompt template |
| `lambda/layers/plugins/python/document_plugins/prompts/credit_agreement.txt` | Credit Agreement normalization prompt template |
| `lambda/layers/plugins/python/document_plugins/prompts/bsa_profile.txt` | BSA Profile normalization prompt template |
| `lambda/layers/plugins/python/document_plugins/prompts/common_preamble.txt` | Shared normalization preamble (Phase 5 Round 3) |
| `lambda/layers/plugins/python/document_plugins/contract.py` | TypedDict hierarchy (Phase 1 Round 2) |
| `lambda/layers/plugins/python/document_plugins/prompts/common_footer.txt` | Shared "critical instructions" prompt fragment |
| `lambda/common/pii_crypto.py` | Phase 6: KMS envelope encrypt/decrypt |
| `lambda/common/safe_log.py` | Phase 6: PII-scrubbing log utility |
| `lambda/common/audit_logger.py` | Phase 6: PII access audit to DynamoDB |
| `lambda/layers/encryption/requirements.txt` | Phase 6: AWS Encryption SDK dependency |
| `tests/unit/test_plugin_registry.py` | Round 4: Plugin registry unit tests |
| `tests/unit/test_router_classification.py` | Round 4: Router dynamic classification tests |
| `tests/unit/test_normalizer_prompt.py` | Round 4: Normalizer composable prompt tests |
| `tests/unit/test_bsa_checkbox_rules.py` | Round 4: BSA checkbox interpretation tests |
| `tests/integration/test_cdk_synth.py` | Round 4: CDK synth Map state integration tests |
| `tests/fixtures/generate_bsa_synthetic.py` | Round 4: Synthetic BSA PDF generator (reportlab) |
| `lambda/layers/plugins/python/document_plugins/types/loan_agreement.py` | Round 8: Loan Agreement plugin config (~850 lines, 8 sections, 63 queries) |
| `lambda/layers/plugins/python/document_plugins/prompts/loan_agreement.txt` | Round 8: Loan Agreement normalization prompt template with coded field rules |
| `scripts/encrypt-existing-pii.py` | Round 8: Migration script for encrypting existing unencrypted PII in DynamoDB |
| `scripts/decrypt-for-rollback.py` | Round 8: Rollback script to decrypt PII before reverting Phase 6 |
| `tests/golden/conftest.py` | Round 8: Shared pytest fixtures for golden file tests |
| `tests/golden/files/loan-agreement.loan_agreement.golden.json` | Round 8: Loan Agreement regression baseline |
| `frontend/src/services/auth.ts` | Round 9: Cognito authentication service (Amplify v6, ~120 lines) |
| `frontend/src/contexts/AuthContext.tsx` | Round 9: React auth context provider + useAuth hook (~100 lines) |
| `frontend/src/pages/Login.tsx` | Round 9: Login page with Cognito challenge handling (~130 lines) |

### Modified Files
| File | Changes |
|------|---------|
| `lambda/router/handler.py` | Remove 780 lines of hardcoded config, import plugin registry, produce `extractionPlan` output |
| `lambda/extractor/handler.py` | Remove type-specific branching, read extraction strategy from event |
| `lambda/normalizer/handler.py` | Remove 3 prompt builders (~700 lines), load prompt templates from plugin, add PII encryption |
| `lambda/api/handler.py` | Add PII decryption for sensitive fields, remove hardcoded "LOAN_PACKAGE" default |
| `lib/stacks/document-processing-stack.ts` | Replace Parallel+Choice with Map state, add plugin layer, add KMS key |
| `frontend/src/types/index.ts` | Add BSAProfileData interface, change documentType to string |
| `frontend/src/components/ExtractedValuesPanel.tsx` | Add BSAProfileFields component |
| `frontend/src/pages/ReviewDocument.tsx` | Add BSA Profile review rendering; replace manual reviewer name with Cognito identity (Round 9) |
| `frontend/src/services/api.ts` | Round 9: Add `getIdToken()` import, inject Authorization header in fetchApi, handle 401 |
| `frontend/src/App.tsx` | Round 9: Wrap in AuthProvider, add ProtectedRoute + RoleGuard, add /login route |
| `frontend/src/components/Layout.tsx` | Round 9: Add useAuth() for user info, filter nav by role, add sign-out button |
| `frontend/package.json` | Round 9: Add @aws-amplify/auth and @aws-amplify/core dependencies |

## Cost Projections

| Type | Router | Textract | Normalizer | KMS | Total |
|------|--------|----------|------------|-----|-------|
| Loan Package | ~$0.006 | ~$0.30 | ~$0.03 | - | **~$0.34** |
| Credit Agreement | ~$0.006 | ~$0.38 | ~$0.013 | - | **~$0.40** |
| BSA Profile | ~$0.003 | ~$0.34 | ~$0.015 | ~$0.00 | **~$0.36** |

> **Cost Note (Round 2 Textract Research):** BSA Profile requires FORMS + TABLES combined ($0.065/page) because checkboxes in table-cell structures (page 2 risk matrix) are only returned when TABLES feature is included. Plus SIGNATURES on last page ($0.015). Total Textract: 5 × $0.065 + 1 × $0.015 = $0.34. KMS envelope encryption adds ~$0.000006/doc (2 API calls × $0.03/10K calls). The $0.075 extra for TABLES vs FORMS-only is negligible compared to the risk of missing compliance-critical checkboxes.

## References & Research

### Internal References
- Plugin schemas foundation: `src/financial_docs/schemas/document_types.py:30-42` (DocumentType dataclass)
- Extraction field definitions: `src/financial_docs/schemas/extraction_fields.py:40-57` (ExtractionField dataclass)
- Router hardcoded config: `lambda/router/handler.py:56-840`
- Normalizer prompt builders: `lambda/normalizer/handler.py:50-730`
- CDK Step Functions branches: `lib/stacks/document-processing-stack.ts:700-783`
- Frontend type definitions: `frontend/src/types/index.ts:158-423`
- BSA Profile sample: `docs/BSA Profile NEW 2 1 3.pdf`

### Brainstorm Document
- `docs/brainstorms/2026-02-17-financial-document-processing-plugin-architecture-brainstorm.md`

### Research References (from Deepen-Plan, Rounds 1-5)
- **AWS Encryption SDK for Python v4.x** — KMS keyring + envelope encryption pattern for field-level PII encryption. Use `aws-cryptographic-material-providers` with `CommitmentPolicy.REQUIRE_ENCRYPT_REQUIRE_DECRYPT`.
- **AWS Database Encryption SDK for DynamoDB** — Alternative to raw KMS calls; handles item-level encryption with attribute actions (sign-only, encrypt-and-sign, do-nothing). Recommended by AWS for DynamoDB field-level encryption.
- **CDK v2 Map state API** — `itemSelector` uses `$$.Map.Item.Value` (context object) to pass current array element fields to each iteration. `toleratedFailurePercentage` is **DistributedMap-only** (not available on inline Map).
- **Step Functions 256KB payload limit** — Standard Workflows limit per state transition. Current `MAX_RAW_TEXT_CHARS = 80000` was added specifically for this; Map state aggregation multiplies the risk. Mitigated by S3 intermediate storage.
- **Textract SELECTION_ELEMENT blocks** — Checkboxes/radio buttons are returned as `SELECTION_ELEMENT` block types with `SelectionStatus: "SELECTED" | "NOT_SELECTED"`. Only returned for the FeatureTypes requested: FORMS returns form-context selections, TABLES returns table-cell selections. Both features needed for BSA.
- **FinCEN BSA/KYC compliance** — 31 CFR 1010.430: 5-year retention for BSA/KYC records. BSA/AML Manual Section 8.1: auditable PII access trail. GLBA Safeguards Rule: encryption at rest and in transit.
- **Cognito RBAC pattern** — CognitoUserPoolsAuthorizer on API Gateway passes decoded JWT claims to `event.requestContext.authorizer.claims`. Group membership via `cognito:groups` claim.
- **Golden file testing pattern** — Capture full DynamoDB record as JSON, compare with configurable ignore paths, numeric tolerance, and order-insensitive array support. Multi-run stability checks identify LLM-variable fields.
- **Step Functions Map itemSelector** — `$$.Map.Item.Value.fieldName` passes array element fields to each iteration. Document-level metadata merged via `$.fieldName` references.
- **Textract query migration** — 305 queries across CDK (145) and extractor (160) move to plugin configs. Router includes queries in `extractionPlan.sections[].queries`, extractor reads from event.
- **React PII masking** — Client-side masking utility for SSN (`***-**-1234`), DOB (`****-**-01`), Tax ID (`**-***5678`). Server controls `piiMasked` flag per document.
- **Structured logging with PII scrubbing** — `safe_log()` utility with regex-based PII pattern detection (SSN, EIN, DOB, email, phone) and field-name-based scrubbing. Drop-in replacement for `print()`.
- **Step Functions log level** — `ALL` level logs full state I/O including extracted data. Must switch to `ERROR` before PII flows through the system.
- **Textract AnalyzeDocument (sync)** — 1 page maximum per call. BSA 5-page forms use parallel sync calls (3-5s) not async StartDocumentAnalysis (10-30s overhead).
- **Textract SIGNATURES** — $0.015/page. BSA only needs signature detection on page 5 (certification). Limiting to 1 page saves $0.060/doc.
- **Textract DPI for handwritten content** — AWS recommends 300 DPI for handwritten text, minimum 150 DPI (15px minimum text height at 150 DPI). 200 DPI is a practical compromise for BSA forms.
- **SELECTION_ELEMENT binary classification** — Textract returns strictly `SELECTED` or `NOT_SELECTED`. No `PARTIALLY_SELECTED` state. Ambiguity expressed only through Confidence score (0-100).
- **deepdiff library** — Provides built-in numeric tolerance, order-insensitive arrays, and path-based exclusions for golden file comparison.
- **CDK Step Functions blue/green** — Step Functions has no native blue/green support. Use Choice state with `isPresent('$.extractionPlan')` to route between Map (new) and Parallel (legacy) paths during transition.
- **TypedDict `total=False`** — All plugin TypedDicts use `total=False` to make all fields optional. This allows incremental plugin development — new plugins can start minimal and add fields over time without breaking the registry. Runtime validation (if needed) is separate from type definition.
- **`pkgutil.iter_modules` discovery pattern** — Same as Django management commands. Module-level `_discover_plugins()` runs once on import with `_DISCOVERED` boolean guard. Failed modules logged but don't block other plugins. Discovery is ~5ms for 3 plugins.
- **CDK Map `itemSelector` context object** — `$$.Map.Item.Value` references the current array element. `$$.Execution.Name` provides execution ID for S3 intermediate storage paths. Document-level fields from router output merged via `$.fieldName`.
- **Map `maxConcurrency` vs Textract TPS** — Default 50 TPS Textract quota shared across all concurrent Step Functions executions. With `maxConcurrency: 10`, a single execution uses up to 10 TPS. Multiple concurrent executions need quota headroom.
- **Prompt template `.replace()` vs `.format()`** — Python's `.format()` requires escaping all literal braces as `{{`/`}}`. Since the common_footer.txt uses literal `{{` for JSON output instruction, `.replace("{extraction_data}", data)` is safer and avoids double-brace confusion.

### Deepen-Plan Agent Reports

**Round 1:**
| Agent | Key Finding | Priority |
|-------|-------------|----------|
| Architecture Strategist | Plugin contract underspecified; needs per-section TypedDict hierarchy | P1 |
| Security Sentinel | 2 CRITICAL: No API auth + PII in CloudWatch logs. 13 findings total. | P0 |
| Performance Oracle | Parallel FORMS extraction needed; envelope encryption; 256KB budget | P0-P1 |
| Pattern Recognition | ~930 lines duplicated code mapped; 5 anti-patterns identified | P2 |
| Best Practices Researcher | AWS Encryption SDK patterns; Step Functions error handling | P2 |

**Round 2 (Deep Implementation):**
| Agent | Key Deliverable | Scope |
|-------|----------------|-------|
| Plugin Registry TypedDict Designer | Complete TypedDict hierarchy, auto-discovery registry, full Credit Agreement plugin config, layer structure | Phase 1 |
| CDK Map State Researcher | CDK replacement code with itemSelector, per-iteration retry/catch, S3 intermediate storage pattern, data flow diagram | Phase 3 |
| Textract FORMS/Checkbox Specialist | Fixed extract_forms() + extract_tables() SELECTION_ELEMENT bug, process_pages_forms_parallel(), BSA extraction strategy, FORMS+TABLES analysis | Phase 4 |
| KMS PII Encryption Architect | Envelope encryption with AWS Encryption SDK, Cognito auth CDK, safe_log.py, audit_logger.py, FinCEN compliance requirements, CloudWatch alarms | Phase 6 |

**Round 3 (Deep Implementation):**
| Agent | Key Deliverable | Scope |
|-------|----------------|-------|
| Golden File Testing Architect | Complete capture.py + compare.py scripts, field-level diff with numeric tolerance (0.001/0.0001), order-insensitive arrays, IGNORE/SOFT_MATCH path lists, LLM non-determinism mitigation, CI integration, pytest wrapper | Phase 0 |
| Router Dynamic Classification Specialist | Dynamic prompt builder from plugin registry, generic identify_sections() with page_bonus_rules, extractionPlan.sections[] format for all 3 doc types, query migration plan (305 queries CDK→plugins), BSA classification keywords, backward-compatible dual-format output | Phase 2 |
| Normalizer Prompt Architect | 4-layer composable prompt architecture (preamble + schema-driven fields + plugin-specific + footer), format_field_instruction() auto-generation, BSA normalization template with checkbox interpretation, S3 extraction resolution, post-processor plugin hooks | Phase 5 |
| Frontend BSA Component Designer | Complete BSAProfileData TypeScript hierarchy (7 interfaces), PII masking utility, BooleanFlag + BeneficialOwnerCard + BSAProfileFields components, GenericDataFields fallback, review workflow integration, document type extensibility (string type + display name utility), teal color scheme | Phase 7 |

**Round 4 (Cross-Cutting + Testing + BSA Accuracy):**
| Agent | Key Deliverable | Scope |
|-------|----------------|-------|
| Cross-Cutting Concerns Analyst | Mapped 266 print() statements (6 CRITICAL PII), error codes + Step Functions catch config, DLQ recommendation, safe_log() implementation, two-step atomic deployment order, feature flag strategy, phase-by-phase rollback procedures (Phase 6 HIGH risk), env var per Lambda, SSM vs env var guidance | Cross-cutting |
| Testing Strategy Architect | Unit test designs for plugin registry/router/normalizer/checkbox rules, CDK synth integration tests for Map state, complete E2E test matrix (28 scenarios), test data inventory (`docs/` not `test-documents/`), synthetic PDF generation with reportlab, test dependency list (deepdiff, pytest-timeout) | Testing |
| BSA Extraction Accuracy Specialist | Page-by-page extraction strategy (5 pages), checkbox confidence tiers (>=90% high, 75-89% medium, <75% mandatory review), FORMS+TABLES confirmed required, sync parallel correct for 5 pages, SIGNATURES page 5 only ($0.060 savings), DPI 200 recommendation, QUERIES not needed initially, normalizer checkbox interpretation rules, validated cost ~$0.36 | Phase 4 BSA |

**Round 5 (Implementation File Generation):**
| Agent | Key Deliverable | Files Generated |
|-------|----------------|-----------------|
| Plugin Config File Generator | Complete `contract.py` (10 TypedDicts, 170 lines), `registry.py` (auto-discovery with 6 public functions, 144 lines), `__init__.py` (public API exports), `types/__init__.py` (subpackage). Read all 4 Lambda handlers + CDK stack to extract exact field mappings. | `contract.py`, `registry.py`, `__init__.py`, `types/__init__.py` |
| CDK Map State Code Generator | Complete CDK TypeScript replacement for `document-processing-stack.ts`: Map state with `itemSelector`, blue/green Choice state, per-iteration retry/catch, S3 intermediate storage, plugin layer definition, env vars (ROUTER_OUTPUT_FORMAT, SELECTION_CONFIDENCE_THRESHOLD, S3_EXTRACTION_PREFIX), log level ERROR, complete data flow documentation (5 steps). All legacy Parallel branches preserved with [LEGACY] comments. | Plan-level CDK code specs (not written to `.ts` file) |
| BSA Normalization Prompt Generator | `common_preamble.txt` (47 lines: role definition, {extraction_data} placeholder, 7 normalization rule categories), `common_footer.txt` (18 lines: 14 critical instructions including JSON-only output, null over empty strings, preserve arrays). Analyzed existing 3 prompt builders (~700 lines) to extract shared patterns. | `common_preamble.txt`, `common_footer.txt` |

**Round 6 (Complete Plugin Layer — All Files Written to Disk):**
| Agent | Key Deliverable | Files Generated |
|-------|----------------|-----------------|
| Credit Agreement Plugin Writer | 7 sections with 153 queries migrated from `extractor/handler.py` CREDIT_AGREEMENT_QUERIES. `applicableRates` uses `["QUERIES", "TABLES"]` for pricing grid. `lenderCommitments` has `page_bonus_rules` for schedule page detection. 19 classification keywords from router DOCUMENT_TYPES. Output schema matching normalizer creditAgreement JSON structure. Cost budget: max $2.00, $0.02/page. | `types/credit_agreement.py` (914 lines) |
| BSA Profile Plugin Writer | First plugin-native type (no hardcoded counterpart). Single `bsa_profile_all` section with `["FORMS", "TABLES"]`. 22 classification keywords unique to BSA. 5 PII path markers with array wildcards (`beneficialOwners[*].ssn`, etc.). `render_dpi: 200` for handwritten forms. `extract_signatures: False` (add page-5-only in Phase 4). Cost budget: max $0.50, $0.065/page. | `types/bsa_profile.py` (390 lines) |
| Normalization Prompt Writer | 3 plugin-specific templates. `credit_agreement.txt` (302 lines): interest rate decimal conversion, facility tiers, amendment number rules, joint borrower rules. `bsa_profile.txt` (247 lines): checkbox confidence tiers (≥90%/75-89%/<75%), SELECTION_ELEMENT interpretation, beneficial owner array rules, entity type mapping, PII handling. `loan_package.txt` (382 lines): promissory note, closing disclosure, Form 1003 sub-document rules. All use `{{`/`}}` JSON escaping compatible with `.replace()` injection. | `prompts/credit_agreement.txt`, `prompts/bsa_profile.txt`, `prompts/loan_package.txt` |

**Complete Plugin Layer Directory (3,090 lines total — all files verified on disk):**
```
lambda/layers/plugins/python/document_plugins/
  __init__.py                          # Public API: get_plugin, get_all_plugins, etc.
  contract.py                          # 10 TypedDicts defining plugin config shape (169 lines)
  registry.py                          # Auto-discovery via pkgutil.iter_modules (144 lines)
  types/
    __init__.py                        # Subpackage marker
    loan_package.py                    # 3 sections, ~97 queries, 0 PII paths (478 lines)
    credit_agreement.py                # 7 sections, 153 queries, 0 PII paths (914 lines)
    bsa_profile.py                     # 1 section (FORMS+TABLES), 0 queries, 5 PII paths (390 lines)
  prompts/
    common_preamble.txt                # Shared normalization preamble (47 lines)
    common_footer.txt                  # Shared critical instructions (17 lines)
    loan_package.txt                   # Loan package normalization rules (382 lines)
    credit_agreement.txt               # Credit agreement normalization rules (302 lines)
    bsa_profile.txt                    # BSA profile normalization rules (247 lines)
```

**Round 7 (Implementation-Ready Code Validation & Handler Refactoring Designs):**
| Agent | Key Deliverable | Scope |
|-------|----------------|-------|
| CDK Map State API Validator | Verified all CDK code against real `aws-cdk-lib` v2 source (`node_modules`). 15 findings: 10 validated correct, 5 corrections needed. `sfn.Chain(this,id)` doesn't exist, `addRetry` overlaps `retryOnServiceExceptions`, Round 5 `itemSelector` (nested `sectionConfig.$`) correct over Round 2. Complete corrected CDK TypeScript code with line-by-line change map. S3 `extractions/` lifecycle rule needed. Generated ASL JSON equivalent for validation. | Phase 3 |
| Router Handler Refactoring Specialist | Read full 1803-line router handler. Complete implementations: `build_classification_prompt()` (60 lines), `identify_sections()` + `_evaluate_bonus_rule()` (80 lines), `build_extraction_plan()` (50 lines), `add_backward_compatible_keys()` (50 lines), `_resolve_plugin()` (25 lines). **7 CRITICAL risk areas**: loan_agreement≠loan_package gap, two-pass LLM refinement, BSA dual-mode limitation, loan_package LLM-based section ID, misclassification reclassification. Net Phase 2: -103 lines. | Phase 2 |
| Extractor Handler Refactoring Specialist | Read full 2379-line extractor handler. Complete implementations: `extract_section()` (130 lines), `run_textract_feature_parallel()` (50 lines), `process_pages_forms_parallel()` (95 lines), `write_extraction_to_s3()` (55 lines). Complete SELECTION_ELEMENT bug fix code for `extract_forms()` (full rewrite) and `extract_tables()` (6-line fix). 981 lines (41%) dead code identified. 5-step incremental diff strategy. | Phase 4 |
| Golden File Test Infrastructure Designer | Complete Phase 0 design: `capture.py` (upload→poll→export with 180s timeout, deduplication check, metadata envelope), `compare.py` (24 IGNORE_PATHS, 8 SOFT_MATCH_PATHS, dual tolerance 0.001/0.0001, 7 ORDER_INSENSITIVE_ARRAYS, stdlib-only), `test_golden_regression.py` (3 test classes, `@pytest.mark.integration`), `conftest.py` (3 PDF fixtures from `docs/`). GitHub Actions CI integration. 10-step execution checklist with cross-run stability verification. | Phase 0 |

**Round 7 Key Corrections to Prior Rounds:**

| Correction | Affects | Details |
|-----------|---------|---------|
| `loan_agreement` is NOT `loan_package` | Phase 2, Round 3 Router Research | `LOAN_AGREEMENT_SECTIONS` (275 lines) handles simple business loans with 7 sections. `loan_package` handles mortgages with 3 sub-documents. Must create `types/loan_agreement.py` plugin before deleting handler code. |
| `loan_package` uses LLM classification, not keyword density | Phase 2, Plugin contract | Mortgage sub-document pages come from LLM classification response (`promissoryNote: 5, closingDisclosure: 42`), not keyword scoring. Add `section_identification_strategy` field to ClassificationConfig. |
| BSA requires Phase 3 to be functional | Phase 2 transition plan | BSA has no legacy CDK Choice state path. During dual-format, BSA documents routed to mortgage path (incorrect). BSA testing must wait until Map state is deployed. |
| `sfn.Chain(this, id)` doesn't exist | Phase 3, Round 1 architecture | Early CDK snippet (lines 174-180) uses invalid constructor. Superseded by Round 2 code. Delete from plan. |
| `addRetry` + `retryOnServiceExceptions` = compound retries | Phase 3, Round 2 CDK code | Set `retryOnServiceExceptions: false` on inner LambdaInvoke. Manage all retries via explicit `addRetry` with Textract throttling errors included. |
| Credit Agreement two-pass refinement at risk | Phase 2 | Generic `identify_sections()` is keyword-only (pass 1). Current pipeline also runs `classify_credit_agreement_with_bedrock()` (pass 2) for LLM verification. Need plugin-level flag `use_llm_section_refinement`. |

**Round 8 (Complete Implementation Coverage — All Gaps Filled):**
| Agent | Key Deliverable | Scope |
|-------|----------------|-------|
| Loan Agreement Plugin Config Writer | Complete `types/loan_agreement.py` (~850 lines): 8 sections, 63 queries migrated from router+extractor+CDK, `_extractedCodes` for banking systems, $0.18-$0.60 cost budget. Unique: keyword_density section ID, `requires_signatures: True`, hybrid PyPDF+Textract. Also: `prompts/loan_agreement.txt` outline with coded field rules and default values. | Phase 1 |
| Normalizer Handler Refactoring Specialist | Read full 2,577-line normalizer handler. Dead code analysis: 1,342 lines (52%) removable. Complete `build_normalization_prompt()` (80 lines), `resolve_s3_extraction_refs()` (40 lines, parallel S3 downloads). Refactored `lambda_handler` with pluginId entry point. 5-step diff strategy. File shrinks from ~2,577 to ~1,400 lines (46% reduction). | Phase 5 |
| PII Encryption Implementation Specialist | Read all Lambda handlers + CDK stack. Complete `safe_log.py` (PII-aware logging, array wildcard support), `pii_crypto.py` (AES-256-GCM envelope encryption via KMS GenerateDataKey), `encrypt-existing-pii.py` (idempotent migration, dry-run default), `decrypt-for-rollback.py` (safety checks, --confirm required). CDK constructs for KMS+Cognito+audit table. 28-step deployment checklist across 4 phases. Identified `loan_package.py` missing 2 PII paths. | Phase 6 |
| CDK Stack Complete Diff Generator | Read full 1,060-line CDK stack. Mapped all 45+ constructs with line ranges. Phase 3 annotated diff: plugins layer, Map state, blue/green Choice, explicit retry/catch. Phase 4: S3 lifecycle rule. Phase 6: 8 new constructs (KMS key, Cognito pool+3 groups+client, audit table, authorizer). Complete construct dependency graph. Per-phase deployment safety analysis with risk levels and recommended deployment order. | Phases 3, 4, 6 |

**Round 9 (Complete Function Implementations — All Handler Code Bodies):**
| Agent | Key Deliverable | Scope |
|-------|----------------|-------|
| Loan Agreement Prompt Template Writer | Complete `prompts/loan_agreement.txt` (~500 lines): 55 extraction fields in 10 sections, 8 coded field enumerations with complete valid value lists, default value rules, cross-reference validation (rate × amount sanity), `{{`/`}}` JSON escaping. Covers all 27 field definitions from `build_loan_agreement_prompt()` handler lines 321-728. Follows 4-layer composable architecture. | Phase 1 |
| Frontend Cognito Integration Designer | Complete authentication layer: `auth.ts` (Amplify v6 tree-shakeable, 6 functions), `AuthContext.tsx` (React context + `useAuth` hook), `Login.tsx` (Cognito challenge handling), modified `api.ts` (Authorization header + 401 redirect), modified `App.tsx` (ProtectedRoute + RoleGuard). Role-based access matrix (Viewer/Reviewer/Admin). PII masking is server-side only. ReviewDocument reviewer name from Cognito identity. | Phase 7 |
| Router Handler Implementation Specialist | Complete function bodies for all 6 new functions. `build_classification_prompt()` builds dynamic prompt from plugin registry. `identify_sections()` with keyword density + `_evaluate_bonus_rule()`. `build_extraction_plan()` with 3 strategies. `_resolve_plugin()` with 3-strategy resolution. `add_backward_compatible_keys()` per-plugin legacy keys. Refactored `lambda_handler` with 9-step flow. Dead code analysis: 5 functions delete immediately, 2 keep temporarily. Credit Agreement reclassification preserved. | Phase 2 |
| Normalizer Handler Implementation Specialist | Complete function bodies for all 5 new functions. `resolve_s3_extraction_refs()` with ThreadPoolExecutor parallel S3 downloads. `invoke_bedrock_normalize()` returns partial result on JSON parse failure (CRITICAL fix). `apply_field_overrides()` with dot-path navigation. `_handle_plugin_path()` 9-step flow. Full DynamoDB write integration (`extractedData = normalized_data['loanData']`). `_build_plugin_summary()` per-type. Event flow documented. | Phase 5 |

**Round 10 (Operational Readiness — Deployment, Testing, Schema, Scripts):**
| Agent | Key Deliverable | Scope |
|-------|----------------|-------|
| Trigger Lambda Plugin Analyst | Read full 241-line trigger handler + CDK integration. **ZERO changes needed.** Trigger is fully decoupled from plugin architecture — its input/output contract (documentId, bucket, key, contentHash, size, uploadedAt) passes through Step Functions unchanged. Router enriches data downstream. Dedup logic, DynamoDB record creation, and SFN execution start are all plugin-agnostic. | All Phases |
| Frontend BSA Component Designer | 8 new components designed: `BSAProfileFields` (main section renderer), `BeneficialOwnerCard` (collapsible array items with PII locks), `RiskAssessmentPanel` (checkbox/radio display with risk-level color coding), `BooleanFlag` (reusable yes/no indicator), `PIIIndicator` (lock icon for masked fields with tooltip), `GenericDataFields` (fallback renderer for unknown plugin types using output_schema). Complete TypeScript interfaces: `BSAProfile`, `BeneficialOwner`, `PluginOutputSchema`, `FieldDefinition`, `PluginRegistry`. Integration into existing `ExtractedValuesPanel` via document-type conditional rendering. PII masking is server-side only — frontend shows visual indicators. | Phase 7 |
| DynamoDB Schema Evolution Analyst | Complete schema map: 20+ attributes tracked across 5 Lambda writers/readers. **4 new attributes needed:** `pluginId` (string), `pluginVersion` (string), `_pii_envelope` (map), `retentionPolicy` (string). Multi-tier TTL strategy: 365d (mortgage), 3yr (commercial), 7yr (BSA/KYC). **2 new GSIs:** `PluginIdIndex` (pluginId + createdAt), `RetentionPolicyIndex` (retentionPolicy + retentionExpiry). One-time backfill script for existing records. No breaking changes if new attributes have defaults. Sort key (`documentType`) works fine for BSA_PROFILE and LOAN_AGREEMENT. | Phases 1-7 |
| Deployment Runbook Designer | Complete 8-phase runbook with exact CLI commands per phase. Phase grouping: Group A (Phase 0 independent), Group B (Phases 1-2 low risk), Group C (Phases 3-4 MUST deploy together), Group D (Phases 5-6 sequential), Group E (Phase 7 depends on Phase 3). Per-phase: pre-deployment checks, deployment commands, post-deployment smoke tests, rollback procedures, go/no-go criteria. CloudWatch Logs Insights queries per phase. Cost monitoring (Bedrock tokens, Textract pages, KMS calls). **Phase 6 rollback requires DynamoDB backup restore** (encrypted data is irreversible). Communication plan templates. Master checklist. | All Phases |
| E2E Test Matrix Specialist | 10-step Phase 0 golden file capture checklist. Directory structure: `tests/golden/{documents,audit,executions}/`. **24 IGNORE_PATHS** for non-deterministic fields. **Dual numeric tolerance:** 0.001 financial, 0.0001 rates. **7 ORDER_INSENSITIVE_ARRAYS.** 6 phase-transition test matrices with 30+ test cases total. **7 missing test documents** identified (BSA digital, BSA scanned, loan agreement simple/complex, empty doc, single page, 300+ pages). CI/CD via GitHub Actions. Rollback criteria: >5% numeric tolerance = immediate rollback. | Phase 0 |
| Script Environment Standardization | Complete `scripts/common.sh` design: sources `~/.zshrc`, validates AWS identity (`aws sts get-caller-identity`), prints environment banner (account, region, IAM identity, bucket, table, Python/Node versions). **11 helper functions:** `get_bucket_name()`, `get_table_name()`, `get_stack_output()`, `run_python()`, `confirm_action()`, `print_banner()`, `fail()`, `success()`, `info()`, `warning()`. Per-script modifications for all 6 existing scripts (replace hardcoded values, use `uv run python`, add banners). **8 new scripts:** `deploy-phase.sh`, `validate-deployment.sh`, `capture-golden-files.sh`, `compare-golden-files.sh`, `backfill-dynamodb.sh`, `encrypt-existing-pii.sh`, `decrypt-for-rollback.sh`, `delete-dynamodb-items.py`. Safety guards: `--dry-run`, `--force`, double confirmation, account validation. | All Phases |

**Round 10 Key Findings:**

| Priority | Finding | Source | Plan Impact |
|----------|---------|--------|-------------|
| INFO | Trigger Lambda requires ZERO changes — fully decoupled from plugin architecture | Trigger Lambda Analyst | No trigger tasks needed in any phase |
| P1 | DynamoDB needs `pluginId`, `pluginVersion`, `_pii_envelope`, `retentionPolicy` attributes with defaults | DynamoDB Schema Analyst | Add backfill subtask to Phase 2; add new GSIs to Phase 3 CDK |
| P1 | BSA/KYC records need 7-year TTL (current: 365 days) — multi-tier retention required | DynamoDB Schema Analyst | Add `retentionPolicy` attribute + `RETENTION_POLICIES` dict to normalizer; update CDK TTL config |
| P1 | 7 test documents missing for Phase 0 golden file capture (BSA digital, BSA scanned, loan agreement variants, edge cases) | E2E Test Matrix | Create test documents as Phase 0 prerequisite |
| P1 | All scripts lack AWS environment validation — risk of deploying to wrong account | Script Standardization | Create `scripts/common.sh` as Phase 0 prerequisite |
| P1 | `cleanup.sh` hardcodes bucket name and region — will break if account/region changes | Script Standardization | Replace with `get_bucket_name()` from common.sh |
| P1 | `test-local.sh` uses bare `python` — may invoke wrong interpreter on systems with multiple Python versions | Script Standardization | Replace all `python`/`python3` with `uv run python` via `run_python()` |
| P2 | Phases 3+4 must deploy together (Map state format coupled with extractor input contract) — confirmed by deployment runbook | Deployment Runbook | Deploy as single atomic operation with combined rollback |
| P2 | Phase 6 rollback requires DynamoDB backup restore — encrypted data cannot be decrypted without KMS key after stack destruction | Deployment Runbook | Mandatory DynamoDB backup before Phase 6; 30-day KMS pending window; decryption migration script |
| P2 | Frontend needs `GenericDataFields` fallback component for unknown plugin types — enables future document types without frontend changes | Frontend BSA Designer | Add to Phase 7 alongside BSA-specific components |
| P2 | Frontend PII masking is server-side only — backend returns masked values for non-Admin users; frontend shows lock icons as visual indicators | Frontend BSA Designer | No frontend PII logic needed; just visual indicators |
| P2 | `PluginIdIndex` GSI enables plugin-based filtering and reporting in dashboard | DynamoDB Schema Analyst | Add to Phase 3 CDK deployment (after backfill) |
| P2 | Golden file comparison needs order-insensitive arrays for lenderCommitments, facilities, beneficialOwners | E2E Test Matrix | Implement in `compare.py` with key-based matching |
| P3 | 8 new deployment scripts needed alongside `common.sh` — standardizes all phase deployments | Script Standardization | Create as Phase 0 infrastructure |
