---
name: troubleshooting
description: Common issues and solutions for Lambda timeouts, Textract errors, Bedrock errors, Step Functions failures, frontend issues, and DynamoDB errors
---
# Troubleshooting Guide

## Lambda Timeout
- **Router**: Increase memory to speed up PDF processing
- **Extractor**: Check if Textract is running async for large docs

## Textract Errors
- Ensure S3 bucket is in the same region as Textract
- Check IAM permissions for `textract:AnalyzeDocument`

## Bedrock Errors
- Verify model access is enabled in AWS Console
- Check that region supports the model ID

## Step Functions Failures
- Check CloudWatch Logs for detailed error messages
- Verify Lambda function permissions

## Frontend Not Showing Data
- Check if `extractedData` vs `data` is being accessed correctly
- Verify API response structure matches TypeScript types
- Check browser console for errors
- Hard refresh (Cmd+Shift+R) after CloudFront invalidation

## DynamoDB Float Error (`Float types are not supported`)
- Always use `Decimal(str(value))` for numeric fields in DynamoDB items
- Common in compliance baselines (`confidenceThreshold`) and scores

## Frontend Tests Fail ("document is not defined")
- Vitest must be run from `frontend/` directory, not project root
- The jsdom environment is configured in `frontend/vite.config.ts`

## CORS Errors
- API Lambda returns CORS headers for all responses
- Check `CORS_ORIGIN` environment variable
- Ensure presigned URLs use regional S3 endpoint
