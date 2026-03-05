---
name: cost-analysis
description: Per-document cost breakdown, AWS service pricing reference, monthly cost estimates, key metrics to track, and cost optimization tips
---
# Cost Analysis

## Per-Document Cost Breakdown (20-page Credit Agreement)

| Stage | Service | Details | Cost |
|-------|---------|---------|------|
| **Router** | Claude Haiku 4.5 | ~20K input + 500 output tokens | ~$0.023 |
| **Textract** | Tables + Queries | ~19 pages x $0.02/page | ~$0.38 |
| **Normalizer** | Claude Haiku 4.5 | ~6K input + 1.4K output tokens | ~$0.013 |
| **Step Functions** | Standard Workflow | 11 state transitions x $0.000025 | ~$0.0003 |
| **Lambda** | Compute | 4 invocations + ~50 GB-seconds | ~$0.0008 |
| **Total** | | | **~$0.42** |

## AWS Service Pricing Reference

| Service | Pricing | Use Case |
|---------|---------|----------|
| Claude Haiku 4.5 | $0.001/1K input, $0.005/1K output | Router & Normalizer |
| Textract (Tables + Queries) | $0.02/page | Extraction |
| Step Functions (Standard) | $0.000025/state transition | Orchestration |
| Lambda | $0.0000002/invocation + $0.0000166667/GB-sec | Compute |

## Monthly Cost Estimates

| Volume | Per-Doc Cost | Monthly Cost |
|--------|-------------|--------------|
| 100 docs | $0.42 | $42 |
| 1,000 docs | $0.42 | $420 |
| 10,000 docs | $0.42 | $4,200 |

## Key Metrics to Track
- Bedrock token usage (per model)
- Textract API calls (AnalyzeDocument)
- Lambda invocations and duration
- Step Functions state transitions
- S3 storage and requests
- DynamoDB read/write capacity
- CloudFront requests and data transfer

## Cost Optimization Tips
1. Use Intelligent Tiering for S3 processed documents
2. Set DynamoDB TTL to auto-delete old records
3. Monitor Bedrock token usage with CloudWatch
4. Use reserved concurrency for predictable Lambda costs
5. **Claude Haiku 4.5** for classification + normalization ($1.00/MTok in, $5.00/MTok out)
6. Content deduplication prevents reprocessing identical documents
7. **MAX_PARALLEL_WORKERS=30** for faster Textract processing (~60% of 50 TPS quota)
8. **2GB Lambda memory** for Router/Normalizer/Extractor (1 vCPU for CPU-bound ops)
