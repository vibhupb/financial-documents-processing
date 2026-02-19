# Financial Document Processing - Plugin Architecture

**Date:** 2026-02-17
**Status:** Brainstorm Complete
**Author:** Vibhu + Claude
**Next Step:** `/workflows:plan`

---

## What We're Building

Transform the Financial Documents Processing system from a hardcoded multi-document-type pipeline into a **plugin-based document processing platform**. Every document type - current (Loan Packages, Credit Agreements) and future (BSA Profiles, W2s, Driver's Licenses, Mortgages, and any prevailing financial document) - becomes a self-contained plugin that plugs into a shared processing engine.

**BSA Profile** is the first new document type built on this architecture, serving as the proof case for the plugin system.

### Architecture Principles (Non-Negotiable)

These are the fundamentals that have made the system successful at ~$0.34/doc and under 1 minute. The plugin architecture must preserve all of them:

1. **Cheapest viable LLMs** - Use Claude 3 Haiku for classification (~$0.006), Claude 3.5 Haiku for normalization (~$0.03). Never use expensive models for tasks a cheap model can handle.
2. **Targeted page extraction** - Router identifies which pages matter, Textract only processes those pages. For large docs (300 pages), extract only relevant pages. For short docs (BSA's 5 pages), all pages may be relevant - "targeted" means the plugin decides.
3. **Smart routing over brute force** - Classify first ($0.006), then extract selectively ($0.02-0.05/page). This is the Router Pattern's core advantage over BDA or Opus-style approaches.
4. **Under $1/doc, under 1 minute** - Hard constraints for any document type plugin.
5. **Engineering-first, nimble** - Prefer simple Python config over complex frameworks. A plugin is a dict, not an enterprise service.

### Document Types

**Currently Implemented (to be refactored into plugins):**

| Type | Pages Extracted | Cost | Status |
|------|----------------|------|--------|
| Loan Package (Promissory Note, Closing Disclosure, Form 1003) | Targeted pages from 20-300 page docs | ~$0.34 | Production |
| Credit Agreement | Targeted sections from 50-200 page docs | ~$0.40 | Production |

**New - BSA Profile (first plugin-native type):**

A 5-page KYC/AML compliance form (Texas Capital) received via email/fax/mail in both digitally-filled and handwritten/scanned formats.

- **Page 1** - Legal Entity Information: Company Name, Tax ID, Entity Type, NAICS, Business Description, Addresses, Trading Details, Regulatory Status
- **Page 2** - Risk Assessment: AML/PEP/Fraud history, Cash Intensive, Energy/Real Estate/MSB/Securities flags
- **Page 3** - Beneficial Ownership: Controlling Party (name, DOB, SSN, ID, citizenship), Ownership Declarations, Beneficial Owner 1
- **Pages 4-5** - Beneficial Owners 2-4, Trust Information

**Future Types (plugin additions, out of scope for now):**
W2 forms, Driver's Licenses, Mortgage documents, SBA Loan documents, Boarding Sheets, and other prevailing financial documents.

## Why Plugin Architecture

### The Problem

Adding Credit Agreements required changes to 6+ files: router prompt, extractor config, normalizer prompt, Step Functions branches, CDK stack, frontend types, frontend components. Each new document type repeats this. At the rate we're adding types, this doesn't scale.

### The Solution

A plugin is a Python configuration that declares everything the processing engine needs. Adding a new document type means:
1. Write a plugin config (classification hints, extraction strategy, normalization prompt, output schema)
2. Add frontend field display (schema-driven or custom component)
3. Deploy

No changes to router, extractor, normalizer, or Step Functions core logic.

### Why Now (Not Later)

- BSA Profile has unique needs (checkbox extraction, PII encryption, repeating structures) that will stress-test plugin boundaries
- Existing Loan + Credit Agreement types are stable and well-understood - low-risk to refactor
- Every future type added without the plugin system increases technical debt

### Alternatives Considered

| Approach | Verdict | Reason |
|----------|---------|--------|
| Hybrid Registry + BSA First | Rejected | Creates temporary dual patterns, migration overhead |
| Hardcoded BSA Path | Rejected | Doesn't scale; repeats the 6-file change problem |

## Key Decisions

### 1. Plugin Contract

Each document type plugin is a Python module that exports a configuration dict:

- **Classification hints** - Keywords/patterns for the router to identify this document type from PyPDF text snippets
- **Extraction strategy** - Which Textract features per page (Forms, Tables, Queries), page targeting rules, whether full-doc or targeted extraction
- **Normalization prompt** - LLM prompt template for structuring raw extraction output into the schema
- **Output schema** - JSON schema defining the extracted/normalized data structure
- **PII field markers** - Which output fields require field-level encryption at rest
- **Cost budget** - Expected per-document cost (enforced as a monitoring alarm, not a hard limit)

The exact module structure (Lambda layer, shared package, or inline config) is a planning decision.

### 2. Processing Engine (Shared)

The router, extractor, normalizer, and Step Functions workflow become generic:

- **Router** reads classification hints from all registered plugins, picks the best match
- **Extractor** reads the matched plugin's extraction strategy, runs Textract accordingly
- **Normalizer** reads the matched plugin's prompt template + schema, produces structured output
- **Step Functions** orchestrates the same classify → extract → normalize flow for any plugin

This preserves the Router Pattern's cost optimization: cheap classification first, targeted extraction second.

### 3. BSA-Specific: Textract FORMS (always) + PyPDF (supplementary) + LLM Interpretation

BSA Profile is a form-heavy document with checkboxes and handwritten fields. Its extraction strategy:

- Always run Textract FORMS on all 5 pages for key-value pairs and checkbox/radio detection
- Also extract PyPDF text to give the LLM normalizer richer context (field labels, narrative descriptions)
- Claude 3.5 Haiku normalizer receives both Textract FORMS output and PyPDF text, interprets ambiguous checkboxes, normalizes values
- Checkbox/radio normalization: LLM resolves ambiguous states (partially filled, unclear marks), maps multi-select fields to arrays, normalizes Yes/No to boolean
- Consistent pipeline regardless of form quality - no conditional branching needed

This differs from Loan Packages (PyPDF + Textract Queries/Tables on targeted pages) and demonstrates the plugin system's flexibility.

### 4. PII Handling: Full Storage with Field-Level Encryption

- Plugin's PII field markers declare which fields are sensitive (SSN, DOB, ID numbers)
- Processing engine encrypts marked fields with AWS KMS before DynamoDB write
- Decryption only available to authorized IAM roles
- Applies to any plugin that declares PII fields - not BSA-specific logic

### 5. Beneficial Owner Repeating Structure (BSA-specific)

- Schema supports array of up to 4 beneficial owners + 1 trust
- Each owner has identical field structure (name, DOB, SSN, address, ID, citizenship)
- Normalizer handles variable count of filled owners (1 to 4)
- Empty/unfilled owner sections excluded from output

## Scope

### In Scope

**Plugin Architecture:**
- Design and implement plugin registry/contract system
- Refactor existing Loan Package into plugin module
- Refactor existing Credit Agreement into plugin module
- Genericize router, extractor, normalizer to read plugin configs
- Update Step Functions workflow for plugin-based routing

**BSA Profile Plugin:**
- BSA Profile plugin config (classification, extraction, normalization, schema)
- Extract ALL fields across all 5 pages (entity info, risk assessment, beneficial owners, trust)
- Handle digital and scanned/handwritten forms
- Field-level PII encryption for sensitive fields

**Frontend:**
- BSA Profile data display and review components
- Maintain existing Loan/Credit Agreement display (regression safety)

**Constraints:**
- Every plugin must stay under $1/doc and under 1 minute processing
- No changes to existing document processing behavior (Loan, Credit Agreement)

### Out of Scope
- Downstream Loan AI UI Booking Automation integration (separate system, consumes our output)
- Adding W2 / Driver's License / Mortgage / SBA types (future plugins using this architecture)
- OCR confidence scoring UI
- Automated PEP screening against watchlists
- Multi-language form support

## Open Questions

1. **Plugin storage structure** - Should plugins live as subdirectories under `lambda/plugins/` or as a shared Lambda layer? Affects cold start, deployment, and how the processing engine loads configs.
2. **Schema versioning** - When a plugin's output schema changes, how do we handle documents extracted with older schema versions?
3. **Textract QUERIES as validation layer** - For BSA, Textract FORMS extracts all key-value pairs. Adding targeted QUERIES for critical fields (Company Name, Tax ID) costs ~$0.10 more per doc but could improve accuracy. Worth it?
4. **KMS key management** - Single KMS key for all PII across document types, or per-plugin keys for finer access control?
5. **Frontend plugin rendering** - Schema-driven generic renderer (less work per plugin, less control) vs. per-plugin React components (more work, full control)?
6. **Regression testing strategy** - Refactoring Loan Package and Credit Agreement into plugins is the highest-risk part. How do we validate processing output is unchanged? (golden-file tests comparing before/after)
7. **Step Functions branching** - CDK Step Functions may not support fully dynamic branching from config at runtime. Do we: (a) generate branches at deploy time from registry, or (b) use a single generic Lambda that reads plugin config?

## Cost Projections

### Per-Document Costs by Type

| Type | Router | Textract | Normalizer | Other | Total |
|------|--------|----------|------------|-------|-------|
| Loan Package | ~$0.006 | ~$0.30 (targeted pages) | ~$0.03 | - | **~$0.34** |
| Credit Agreement | ~$0.006 | ~$0.38 (targeted sections) | ~$0.013 | - | **~$0.40** |
| BSA Profile | ~$0.006 | ~$0.25 (FORMS, 5 pages) | ~$0.03 | KMS ~$0.00 | **~$0.29** |
| BSA + QUERIES | ~$0.006 | ~$0.35 (FORMS + QUERIES) | ~$0.03 | KMS ~$0.00 | **~$0.39** |

All types well under the $1/doc hard constraint.

## Technical Context

### Current Architecture (Pre-Plugin)
- Router: Single `handler.py` with hardcoded classification prompts for Loan + Credit Agreement
- Extractor: Single `handler.py` with document-type-specific Textract config
- Normalizer: Single `handler.py` with document-type-specific normalization prompts
- Step Functions: Hardcoded parallel branches per document type
- Frontend: `ExtractedValuesPanel.tsx` has `LoanPackageFields` and `CreditAgreementFields` components

### Assumptions and Risks to Validate in Planning

- **Step Functions dynamism** - CDK Step Functions may not support fully dynamic branching from config. Plan must determine the approach (see Open Question #7).
- **DynamoDB + field-level encryption** - KMS-encrypted fields cannot be queried or filtered. Searching by encrypted fields requires a separate approach (query by document ID, or encrypted search index).
- **Deduplication** - Existing SHA-256 content hashing applies to all document types including BSA. Identical re-uploads return cached results.
- **Checkbox extraction reliability** - Handwritten checkmarks on scanned forms have variable Textract FORMS accuracy. LLM normalizer cross-references with PyPDF text but is not a guarantee. Need to measure on real BSA samples.
- **Variable beneficial owners** - 0 to 4 owners plus optional trust. Schema must handle variable-length arrays; normalizer must detect which owner slots are filled vs. empty.
- **Form detection** - Router must distinguish BSA Profile from other form-like documents (e.g., Form 1003). Classification hints need specific markers ("BSA Profile", "Beneficial Ownership", "KYC").
- **Plugin refactor risk** - Changing working Loan and Credit Agreement code paths carries regression risk. This is mitigated by golden-file testing but remains the highest-risk part of the project.
