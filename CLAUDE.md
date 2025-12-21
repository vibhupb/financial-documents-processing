# CLAUDE.md - AI Development Assistant Configuration

This file provides context and guidance for Claude (Opus 4.5) when working on this project.

## Project Overview

**Project Name**: Financial Documents Processing
**Pattern**: Router Pattern - Cost-Optimized Intelligent Document Processing
**Industry**: Financial Services (Mortgage Loan Processing)
**Repository**: https://github.com/vibhupb/financial-documents-processing

### Purpose

This project implements a serverless AWS architecture for processing high-volume financial documents (Loan Packages, M&A Contracts) with optimal cost efficiency and precision. It uses a "Router Pattern" to classify documents first, then extract data only from relevant pages.

## Architecture Summary

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────────┐
│   S3 Ingest │────▶│   Trigger   │────▶│   Step Functions     │
│   Bucket    │     │   Lambda    │     │   Orchestrator       │
└─────────────┘     └─────────────┘     └──────────────────────┘
                                                   │
                    ┌──────────────────────────────┼──────────────────┐
                    │                              ▼                  │
                    │  ┌─────────────────────────────────────────┐    │
                    │  │  ROUTER: Classification (Claude Haiku)  │    │
                    │  │  - Extract text snippets from all pages │    │
                    │  │  - Identify key document types          │    │
                    │  │  - Cost: ~$0.01 per document            │    │
                    │  └─────────────────────────────────────────┘    │
                    │                              │                  │
                    │         ┌────────────────────┼────────────┐     │
                    │         ▼                    ▼            ▼     │
                    │  ┌────────────┐  ┌────────────┐  ┌──────────┐   │
                    │  │ Promissory │  │  Closing   │  │  Form    │   │
                    │  │    Note    │  │ Disclosure │  │  1003    │   │
                    │  └────────────┘  └────────────┘  └──────────┘   │
                    │                              │                  │
                    │  ┌─────────────────────────────────────────┐    │
                    │  │  SURGEON: Textract (Targeted Pages)     │    │
                    │  │  - Process ONLY identified pages        │    │
                    │  │  - Queries, Tables, Forms extraction    │    │
                    │  │  - Cost: ~$0.03 per document            │    │
                    │  └─────────────────────────────────────────┘    │
                    │                              │                  │
                    │  ┌─────────────────────────────────────────┐    │
                    │  │  CLOSER: Normalization (Claude Sonnet)  │    │
                    │  │  - Normalize rates, names, dates        │    │
                    │  │  - Cross-reference validation           │    │
                    │  │  - Schema-compliant JSON output         │    │
                    │  └─────────────────────────────────────────┘    │
                    └──────────────────────────────┼──────────────────┘
                                                   │
                              ┌────────────────────┴────────────┐
                              ▼                                 ▼
                       ┌────────────┐                    ┌────────────┐
                       │  DynamoDB  │                    │  S3 Audit  │
                       │  (Results) │                    │   Trail    │
                       └────────────┘                    └────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Infrastructure | AWS CDK (TypeScript) | Infrastructure as Code |
| Orchestration | AWS Step Functions | Workflow management |
| Storage | Amazon S3 | Document storage & audit trail |
| Database | Amazon DynamoDB | Extracted data storage |
| Classification | Amazon Bedrock (Claude 3 Haiku) | Fast document routing |
| Extraction | Amazon Textract | Visual document extraction |
| Normalization | Amazon Bedrock (Claude 3.5 Sonnet) | Data refinement |
| Functions | AWS Lambda (Python 3.11) | Serverless compute |

## Project Structure

```
financial-documents-processing/
├── bin/
│   └── app.ts                    # CDK app entry point
├── lib/
│   └── stacks/
│       └── document-processing-stack.ts  # Main infrastructure
├── lambda/
│   ├── trigger/                  # S3 event → Step Functions
│   │   └── handler.py
│   ├── router/                   # Document classification
│   │   └── handler.py
│   ├── extractor/                # Textract extraction
│   │   └── handler.py
│   ├── normalizer/               # Data normalization
│   │   └── handler.py
│   └── layers/
│       └── pypdf/                # PyPDF Lambda layer
│           ├── requirements.txt
│           └── build.sh
├── scripts/
│   ├── deploy.sh                 # One-command deployment
│   ├── test-local.sh             # Local testing
│   └── upload-test-doc.sh        # Test document upload
├── .vscode/                      # VS Code configuration
├── package.json                  # Node.js dependencies
├── tsconfig.json                 # TypeScript config
├── cdk.json                      # CDK configuration
├── CLAUDE.md                     # This file
└── README.md                     # Project documentation
```

## Development Guidelines

### Code Style

**TypeScript (CDK Infrastructure)**:
- Use strict TypeScript settings
- Prefer `const` over `let`
- Use meaningful variable names
- Document complex logic with comments

**Python (Lambda Functions)**:
- Follow PEP 8 style guide
- Use type hints for function signatures
- Document functions with docstrings
- Handle errors explicitly with try/except

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| CDK Constructs | PascalCase | `DocumentBucket` |
| Lambda Functions | kebab-case | `doc-processor-router` |
| Environment Variables | SCREAMING_SNAKE | `BUCKET_NAME` |
| Python functions | snake_case | `extract_page_snippets` |
| TypeScript functions | camelCase | `createStateMachine` |

### AWS Resource Naming

- S3 Bucket: `financial-docs-{account}-{region}`
- DynamoDB Table: `financial-documents`
- Step Functions: `financial-doc-processor`
- Lambda: `doc-processor-{function}`

## Key Design Decisions

### 1. Cost Optimization Strategy
- **Why**: Processing 300-page documents with full OCR costs ~$4.50
- **Solution**: Use cheap Claude Haiku ($0.01) to classify first, then extract only needed pages ($0.03)
- **Result**: 98.7% cost reduction

### 2. PyPDF for Text Extraction
- **Why**: Faster and cheaper than OCR for text-based PDFs
- **Trade-off**: Won't work for scanned images (would need Textract for those)
- **Solution**: Check if page has extractable text; fallback to Textract if needed

### 3. Parallel Extraction
- **Why**: Different document types need different extraction methods
- **Solution**: Step Functions Parallel state runs Queries, Tables, Forms extraction concurrently

### 4. Dual Storage (DynamoDB + S3)
- **DynamoDB**: Fast queries for application use
- **S3**: Complete audit trail for compliance

## Common Tasks

### Adding a New Document Type

1. Update `lambda/router/handler.py`:
   - Add document type to the classification prompt
   - Add corresponding key to the JSON response

2. Update `lib/stacks/document-processing-stack.ts`:
   - Add new extraction branch in `parallelExtraction`
   - Configure appropriate Textract features

3. Update `lambda/normalizer/handler.py`:
   - Add normalization rules for the new document type
   - Update the output schema

### Modifying Extraction Queries

Edit `lib/stacks/document-processing-stack.ts` in the `extractPromissoryNote` task:
```typescript
queries: [
  'What is the Interest Rate?',
  'Your new query here',
],
```

### Adding New Lambda Environment Variables

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

## Testing

### Local Testing
```bash
./scripts/test-local.sh
```

### Integration Testing
```bash
# Deploy to AWS
./scripts/deploy.sh

# Upload a test document
./scripts/upload-test-doc.sh path/to/test.pdf

# Monitor execution
aws stepfunctions list-executions --state-machine-arn <arn>
```

### Unit Testing (Future)
```bash
npm test          # CDK tests
pytest lambda/    # Python Lambda tests
```

## Deployment

### Prerequisites
- Node.js 18+
- Python 3.11+
- AWS CLI configured with appropriate credentials
- AWS CDK installed (`npm install -g aws-cdk`)

### Deploy Commands
```bash
# Full deployment
./scripts/deploy.sh

# Manual steps
npm install
npm run build
cdk deploy --all
```

### Destroy Infrastructure
```bash
cdk destroy --all
```

## AI Assistant Instructions

When working on this project, Claude should:

### DO:
- Follow the established code patterns and naming conventions
- Maintain cost-optimization as a primary concern
- Keep Lambda functions focused and single-purpose
- Document any non-obvious design decisions
- Ensure error handling is comprehensive
- Consider audit trail requirements for financial compliance
- Test changes locally before suggesting deployment

### DON'T:
- Introduce dependencies without justification
- Break the existing Step Functions workflow without updating all consumers
- Store PII in logs
- Use synchronous Textract for multi-page documents (use async for >1 page)
- Hardcode AWS account IDs or regions
- Skip error handling in Lambda functions

### When Adding Features:
1. Consider impact on cost (is there a cheaper way?)
2. Update CLAUDE.md if architecture changes
3. Ensure backward compatibility with existing documents
4. Add appropriate CloudWatch metrics/alarms
5. Update README.md with usage instructions

## Troubleshooting

### Common Issues

**Lambda Timeout**:
- Router: Increase memory to speed up PDF processing
- Extractor: Check if Textract is running async for large docs

**Textract Errors**:
- Ensure S3 bucket is in the same region as Textract
- Check IAM permissions for textract:AnalyzeDocument

**Bedrock Errors**:
- Verify model access is enabled in AWS Console
- Check that region supports the model ID

**Step Functions Failures**:
- Check CloudWatch Logs for detailed error messages
- Verify Lambda function permissions

## Cost Monitoring

### Key Metrics to Track
- Bedrock token usage (per model)
- Textract API calls (AnalyzeDocument)
- Lambda invocations and duration
- S3 storage and requests
- DynamoDB read/write capacity

### Cost Optimization Tips
1. Use Intelligent Tiering for S3 processed documents
2. Set DynamoDB TTL to auto-delete old records
3. Monitor Bedrock token usage with CloudWatch
4. Use reserved concurrency for predictable Lambda costs

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-12-21 | Initial implementation |

## Contact & Support

For questions about this project or AI-assisted development, refer to:
- Project README.md
- AWS Documentation
- Claude Code documentation

---

*This CLAUDE.md file is designed to provide context to Claude (Opus 4.5) for AI-assisted development. Keep it updated as the project evolves.*
