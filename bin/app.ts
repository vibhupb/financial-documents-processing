#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DocumentProcessingStack } from '../lib/stacks/document-processing-stack';

const app = new cdk.App();

// Get environment from context or use defaults
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT || process.env.AWS_ACCOUNT_ID,
  region: process.env.CDK_DEFAULT_REGION || process.env.AWS_REGION || 'us-east-1',
};

new DocumentProcessingStack(app, 'FinancialDocProcessingStack', {
  env,
  description: 'Router Pattern - Cost-Optimized Intelligent Document Processing for Financial Industry',
  tags: {
    Project: 'financial-documents-processing',
    Pattern: 'router-pattern',
    CostCenter: 'document-processing',
  },
});

app.synth();
