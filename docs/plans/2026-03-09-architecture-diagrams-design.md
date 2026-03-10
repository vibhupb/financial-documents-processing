# Architecture Diagrams & README Restructure — Design

**Date**: 2026-03-09
**Status**: Approved

## Goal

Replace outdated architecture diagrams with accurate, enterprise-style visuals reflecting v5.5.0 state. Restructure README to be streamlined with links to detailed docs.

## Deliverables

| File | Content |
|------|---------|
| `README.md` | Streamlined: hero PNG, 5 Mermaid diagrams, quick start, links |
| `docs/ARCHITECTURE.md` | Deep dive: cost analysis, APIs, performance, diagrams 6-7 |
| `scripts/generate-architecture-diagram.py` | Rewritten for full current-state AWS icon diagram |
| `docs/aws-architecture.png` | Generated hero diagram |

## Diagrams

### In README.md (1-5)

1. **High-Level System Architecture** (PNG + Mermaid) — All AWS services, 9 Lambdas, 6 DynamoDB tables, 2 S3 buckets, Bedrock (Haiku + Sonnet), Textract, Cognito, KMS, CloudFront
2. **Step Functions Pipeline** (Mermaid) — 3 processing modes from ProcessingModeChoice. Extract: async PageIndex, blue/green extraction (plugin Map vs legacy Parallel), conditional compliance, normalize. Understand: sync PageIndex, compliance evaluate, normalize.
3. **Data Flow** (Mermaid sequence) — Upload → S3 → Trigger (SHA-256 dedup) → Step Functions → Router → PageIndex → Extractor/Compliance → Normalizer → DynamoDB → API → Frontend
4. **Compliance Engine** (Mermaid) — Reference docs → Ingest (Haiku, parallel workers) → Requirements → Evaluate (Sonnet 4.6 + tree nav Haiku) → Report → Reviewer Override → Feedback → Few-shot loop
5. **Plugin Architecture** (Mermaid) — Plugin Studio workflow → DynamoDB registry (60s TTL) → Router → ExtractionPlan → Map state → Extractor → Normalizer. Blue/green routing shown.

### In docs/ARCHITECTURE.md (6-7)

6. **Frontend Component Map** (Mermaid) — Pages → Components → API endpoints
7. **Security & Auth** (Mermaid) — Cognito → 3 RBAC groups → API Gateway → Lambda role checks → KMS decrypt/mask → PII Audit

## README.md Structure (streamlined)

```
# Financial Documents Processing
## Router Pattern — Cost-Optimized Intelligent Document Processing
[Hero PNG]
## Key Features (compact table)
## Architecture
  ### System Overview (Mermaid)
  ### Processing Pipeline (Mermaid — Step Functions)
  ### Data Flow (Mermaid sequence)
  ### Compliance Engine (Mermaid)
  ### Plugin Architecture (Mermaid)
## Supported Document Types (compact)
## Quick Start
## Project Structure (updated tree)
## Tech Stack (updated table)
## Documentation (links to ARCHITECTURE.md, VERSION_HISTORY, CREDITS)
## Acknowledgments
## License
```

## docs/ARCHITECTURE.md Structure

```
# Architecture Deep Dive
## Cost Analysis (per-doc breakdown, monthly estimates, comparison)
## Why Router Pattern? (full comparison vs Opus, BDA, GPT-4)
## API Endpoints (all 50+ endpoints, grouped)
## Performance Optimization (Lambda memory, processing times)
## DynamoDB Schema (all 6 tables, keys, GSIs)
## Frontend Component Map (Mermaid diagram 6)
## Security & Auth (Mermaid diagram 7)
## Environment Variables
```

## What's Missing from Current Diagrams

- Compliance pipeline (ingest, evaluate, feedback, 3 DynamoDB tables)
- PageIndex as shared foundation (async/sync modes)
- Plugin architecture (Plugin Studio, dynamic registry)
- Processing modes (extract/understand/both)
- 5 of 6 DynamoDB tables
- Cognito RBAC (3 groups)
- KMS PII encryption
- ~40 API endpoints
- Blue/green extraction routing
- Compliance API Lambda + parsers layer
