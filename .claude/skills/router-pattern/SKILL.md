---
name: router-pattern
description: Router Pattern architecture rationale, cost comparisons vs alternatives (Opus, BDA, GPT-4), and when to use which approach
---
# Router Pattern Architecture

## Philosophy
> "Use a cheap model to figure out WHERE to look, then use specialized tools to extract WHAT you need."

## Key Insights
1. **Classification is cheap** — Claude Haiku 4.5 excels at understanding document structure (~$0.023)
2. **OCR is specialized** — Textract beats LLM vision for tables/forms ($0.02/page)
3. **Normalization needs intelligence** — But not $75/M output token intelligence (~$0.013)

## Cost Comparison

| Approach | Cost/300-page Doc | Limitations |
|----------|-------------------|-------------|
| Claude Opus 4.5 (tool calling) | ~$15-25 | Token limits truncate large docs; cost prohibitive at scale |
| GPT-4 Turbo (function calling) | ~$8-15 | Rate limits; same truncation issues |
| Bedrock Data Automation (BDA) | ~$2-5 | Processes entire document; limited customization |
| **Router Pattern** | **~$0.42** | Surgical precision; ~91% cost reduction |

## vs. Claude Opus 4.5 with Tool Calling
- Cost prohibitive: $15/M input + $75/M output tokens
- Context limits may truncate 300-page documents
- No page-level audit trail for compliance
- Overkill: Using a genius to do a librarian's job

## vs. Bedrock Data Automation (BDA)
- Still processes entire document (no intelligent page selection)
- Limited schema customization (pre-defined templates)
- Higher per-document cost (~$2-5 vs $0.34)
- Less control (black-box pipeline)

## Router Pattern Advantages
- ~91% cost reduction: $0.42/doc vs $4.55 (Textract) or $15+ (Opus)
- Page-level audit trail: Know exactly which page data came from
- Schema flexibility: Custom extraction for any document type
- Parallel extraction: Process sections simultaneously
- Deduplication: SHA-256 prevents reprocessing identical documents
- Human-in-the-loop: Built-in review workflow

## Cost at Scale

| Volume | Router Pattern | BDA | Opus 4.5 |
|--------|----------------|-----|----------|
| 100 docs/month | $42 | ~$300 | ~$2,000 |
| 1,000 docs/month | $420 | ~$3,000 | ~$20,000 |
| 10,000 docs/month | **$4,200** | ~$30,000 | ~$200,000 |

## When to Use Router Pattern

| Use Case | Recommendation |
|----------|----------------|
| High-volume financial docs (1000+/month) | Router Pattern |
| Documents >50 pages | Router Pattern |
| Need page-level audit trail | Router Pattern |
| One-off complex analysis | Consider Opus 4.5 |
| Simple single-page forms | BDA or direct Textract |
