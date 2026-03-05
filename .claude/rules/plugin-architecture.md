---
paths:
  - "lambda/layers/plugins/**"
  - "lambda/router/**"
  - "lambda/extractor/**"
  - "lambda/normalizer/**"
---
# Plugin Architecture

## Self-Registering Pattern
Adding a new document type requires **exactly 2 files** -- no router, normalizer, frontend, or CDK changes:
```
lambda/layers/plugins/python/document_plugins/
  types/{doc_type}.py      <- Plugin config (classification, extraction, schema)
  prompts/{doc_type}.txt   <- Normalization prompt template
```

Everything auto-derives:
- **Router**: Builds classification prompt from plugin registry keywords
- **Extractor**: Reads Textract features + queries from plugin section config
- **Normalizer**: Loads prompt template from plugin's `normalization.prompt_template`
- **Frontend**: `GenericDataFields` renders ANY document type dynamically
- **API**: `GET /plugins` returns all registered types with schemas

## Three Page-Targeting Strategies

| Strategy | Config | When | Savings |
|----------|--------|------|---------|
| **KEYWORD DENSITY** | `has_sections: True` | Large docs (50-300+ pages) | ~90% |
| **LLM START-PAGE** | `section_names: [...]` | Multi-doc packages | ~70% |
| **ALL PAGES** | `target_all_pages: True` | Small forms (1-5 pages) | N/A |

## Plugin Contract (DocumentPluginConfig)
Each plugin exports `PLUGIN_CONFIG: DocumentPluginConfig` with:
- `plugin_id`, `name`, `description`, `plugin_version`
- `classification` -- keywords, page strategy, distinguishing rules
- `sections` -- per-section Textract features, queries, keywords for page targeting
- `normalization` -- prompt template name, LLM model, max tokens, field overrides
- `output_schema` -- JSON Schema defining the normalized output structure
- `pii_paths` -- JSON path markers for PII encryption
- `cost_budget` -- max/warn thresholds, section priority for budget trimming

## Supported Document Types
| Plugin ID | Name | Sections | Page Strategy | PII | Cost |
|-----------|------|----------|---------------|-----|------|
| `loan_package` | Loan Package (Mortgage) | 3 | LLM start-page | No | ~$0.34 |
| `credit_agreement` | Credit Agreement | 7 | Keyword density | No | ~$0.40-$2.00 |
| `loan_agreement` | Loan Agreement | 8 | Keyword density | No | ~$0.18-$0.60 |
| `bsa_profile` | BSA Profile (KYC/CDD) | 1 | All pages | Yes | ~$0.13 |
| `w2` | W-2 Wage and Tax Statement | 1 | All pages | Yes | ~$0.10 |
| `drivers_license` | Driver's License | 1 | All pages | Yes | ~$0.08 |

## Adding a New Document Type
1. Create `lambda/layers/plugins/python/document_plugins/types/{doc_type}.py` -- export `PLUGIN_CONFIG`
2. Create `lambda/layers/plugins/python/document_plugins/prompts/{doc_type}.txt` -- use `{{`/`}}` for JSON braces
3. Deploy: `./scripts/deploy-backend.sh`
4. Optional: Add custom UI in `frontend/src/components/{DocType}Fields.tsx`

## Modifying Extraction Queries
Edit plugin file directly:
```python
"sections": {
    "my_section": {
        "queries": ["What is the Interest Rate?", "Your new query here"],
    },
}
```
