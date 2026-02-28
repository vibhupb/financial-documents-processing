import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import { Construct } from 'constructs';
import * as path from 'path';

export class DocumentProcessingStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ==========================================
    // Layer 1: Storage Infrastructure
    // ==========================================

    // S3 Bucket for document ingestion and processing
    const documentBucket = new s3.Bucket(this, 'DocumentBucket', {
      bucketName: `financial-docs-${this.account}-${this.region}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      cors: [
        {
          allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.POST, s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          exposedHeaders: ['ETag', 'x-amz-meta-custom-header', 'x-amz-server-side-encryption', 'x-amz-request-id', 'x-amz-id-2'],
          maxAge: 3000,
        },
      ],
      lifecycleRules: [
        {
          id: 'ArchiveOldDocuments',
          prefix: 'processed/',
          transitions: [
            {
              storageClass: s3.StorageClass.INTELLIGENT_TIERING,
              transitionAfter: cdk.Duration.days(30),
            },
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
        },
        {
          id: 'CleanupTempFiles',
          prefix: 'temp/',
          expiration: cdk.Duration.days(1),
        },
        {
          id: 'CleanupExtractionIntermediates',
          prefix: 'extractions/',
          expiration: cdk.Duration.days(1),
        },
      ],
    });

    // S3 Bucket for frontend static hosting
    const frontendBucket = new s3.Bucket(this, 'FrontendBucket', {
      bucketName: `financial-docs-frontend-${this.account}-${this.region}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // DynamoDB table for extracted document data
    const documentTable = new dynamodb.Table(this, 'DocumentTable', {
      tableName: 'financial-documents',
      partitionKey: { name: 'documentId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'documentType', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: true,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
    });

    // GSI for querying by processing status
    documentTable.addGlobalSecondaryIndex({
      indexName: 'StatusIndex',
      partitionKey: { name: 'status', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI for content hash lookups (deduplication)
    // When a document is uploaded, we calculate its SHA-256 hash
    // and check if we've already processed the same content
    documentTable.addGlobalSecondaryIndex({
      indexName: 'ContentHashIndex',
      partitionKey: { name: 'contentHash', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI for review status lookups (review queue)
    // Enables querying documents by reviewStatus for the review workflow
    documentTable.addGlobalSecondaryIndex({
      indexName: 'ReviewStatusIndex',
      partitionKey: { name: 'reviewStatus', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // ==========================================
    // Lambda Layers
    // ==========================================

    // PyPDF Layer for PDF processing
    const pypdfLayer = new lambda.LayerVersion(this, 'PyPDFLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/layers/pypdf')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_13],
      description: 'PyPDF + PyMuPDF libraries for double-pass PDF text extraction',
    });

    // Plugins Layer for document type configurations
    const pluginsLayer = new lambda.LayerVersion(this, 'PluginsLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/layers/plugins')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_13],
      description: 'Document type plugin configurations (classification, extraction, normalization)',
    });

    // ==========================================
    // Layer 2: Router Lambda (Classification)
    // ==========================================

    const routerLambda = new lambda.Function(this, 'RouterLambda', {
      functionName: 'doc-processor-router',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/router')),
      layers: [pypdfLayer, pluginsLayer],
      memorySize: 2048,  // 2GB = 1 vCPU - faster PyPDF text extraction (CPU-bound)
      timeout: cdk.Duration.minutes(5),
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        TABLE_NAME: documentTable.tableName,  // For status updates
        BEDROCK_MODEL_ID: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
        ROUTER_OUTPUT_FORMAT: 'dual',  // Emit both legacy keys AND extractionPlan
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    // Grant permissions
    documentBucket.grantRead(routerLambda);
    documentTable.grantReadWriteData(routerLambda);  // For status updates (query + update)
    routerLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel'],
      resources: ['*'],
    }));

    // ==========================================
    // Layer 3: Textract Extraction Lambda
    // ==========================================

    const extractorLambda = new lambda.Function(this, 'ExtractorLambda', {
      functionName: 'doc-processor-extractor',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/extractor')),
      layers: [pypdfLayer, pluginsLayer],
      memorySize: 2048,  // 2GB provides 2x CPU for faster PDF rendering with 30 parallel workers
      timeout: cdk.Duration.minutes(10),  // Increased for large sections
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        // AWS recommends 90%+ for financial applications; using 85% as default
        // to balance accuracy with data completeness
        CONFIDENCE_THRESHOLD: '85.0',
        // Parallel processing: number of concurrent Textract API calls per section
        // 30 workers utilizes ~60% of 50 TPS quota (leaves headroom for burst/overhead)
        MAX_PARALLEL_WORKERS: '30',
        // Image rendering DPI - 150 provides good OCR quality with faster processing
        IMAGE_DPI: '150',
        TABLE_NAME: documentTable.tableName,  // For processing event logging
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    documentBucket.grantReadWrite(extractorLambda);
    documentTable.grantReadWriteData(extractorLambda);  // For processing event logging
    extractorLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'textract:AnalyzeDocument',
        'textract:DetectDocumentText',  // For OCR extraction of scanned documents (HYBRID approach)
        'textract:StartDocumentAnalysis',
        'textract:GetDocumentAnalysis',
      ],
      resources: ['*'],
    }));

    // ==========================================
    // Layer 4: Normalizer Lambda (Refinement)
    // ==========================================

    const normalizerLambda = new lambda.Function(this, 'NormalizerLambda', {
      functionName: 'doc-processor-normalizer',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/normalizer')),
      layers: [pluginsLayer],
      memorySize: 2048,  // 2GB = 1 vCPU - faster JSON parsing and processing
      timeout: cdk.Duration.minutes(5),  // Haiku is fast
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        TABLE_NAME: documentTable.tableName,
        BEDROCK_MODEL_ID: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',  // Claude Haiku 4.5 for normalization
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    documentBucket.grantReadWrite(normalizerLambda);
    documentTable.grantReadWriteData(normalizerLambda);  // Need read for query + write for put/delete
    normalizerLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel'],
      resources: ['*'],
    }));

    // ==========================================
    // Layer 5: PageIndex Lambda (Tree Building)
    // ==========================================

    const pageIndexLambda = new lambda.Function(this, 'PageIndexLambda', {
      functionName: 'doc-processor-pageindex',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/pageindex')),
      layers: [pypdfLayer, pluginsLayer],
      memorySize: 2048,  // 2GB = 1 vCPU for PDF text extraction + concurrent LLM calls
      timeout: cdk.Duration.minutes(10),  // Large docs (300+ pages) need multiple LLM rounds
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        TABLE_NAME: documentTable.tableName,
        BEDROCK_MODEL_ID: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    documentBucket.grantRead(pageIndexLambda);
    documentBucket.grantWrite(pageIndexLambda);  // For S3 audit trail
    documentTable.grantReadWriteData(pageIndexLambda);
    pageIndexLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel'],
      resources: ['*'],
    }));

    // ==========================================
    // Step Functions State Machine
    // ==========================================

    // Define states
    const classifyDocument = new tasks.LambdaInvoke(this, 'ClassifyDocument', {
      lambdaFunction: routerLambda,
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    const extractPromissoryNote = new tasks.LambdaInvoke(this, 'ExtractPromissoryNote', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'pageNumber.$': '$.classification.promissoryNote',
        extractionType: 'QUERIES',
        queries: [
          // =====================================================
          // CORE LOAN TERMS (from schema: total_loan_facility_amount, maturity_date)
          // =====================================================
          'What is the Interest Rate or Annual Percentage Rate (APR)?',
          'What is the Principal Amount or Loan Amount?',
          'What is the Total Loan Amount including fees?',
          'What is the Maturity Date or Final Payment Date?',
          'What is the Monthly Payment Amount?',
          'What is the First Payment Date?',
          'What is the Payment Due Day of each month?',
          'What is the Loan Term (months or years)?',

          // =====================================================
          // BORROWER INFORMATION (from schema: borrower_names)
          // =====================================================
          'Who is the Borrower or Maker of this Note?',
          'Who is the Co-Borrower or Co-Maker?',
          'What is the Borrower Address?',

          // =====================================================
          // LENDER INFORMATION (from schema: agent, lender_type)
          // =====================================================
          'Who is the Lender or Payee?',
          'What is the Lender Address?',

          // =====================================================
          // INTEREST RATE DETAILS (from schema: interest_rate_type, rate_index, spread_rate, rate_calculation_method)
          // =====================================================
          'Is this a Fixed Rate or Variable Rate loan?',
          'What is the Index Rate used (Prime, SOFR, Term SOFR, Daily SOFR, Fed Funds)?',
          'What is the Margin or Spread added to Index Rate?',
          'What is the Interest Rate Floor or Minimum Rate?',
          'What is the Interest Rate Ceiling or Cap?',
          'What is the Default Interest Rate or Penalty Rate?',
          'How is interest calculated (Actual/360, Actual/365, 30/360)?',
          'What is the Rate Calculation Method or Day Count Basis?',

          // =====================================================
          // PAYMENT DETAILS (from schema: billing_frequency, billing_type)
          // =====================================================
          'What is the Total Number of Payments?',
          'How many payments remain?',
          'What is the Balloon Payment Amount?',
          'What is the Late Payment Fee or Late Charge?',
          'What is the Grace Period for late payments?',
          'Is Interest payable In Arrears or In Advance?',
          'What is the Payment Frequency (monthly, quarterly)?',

          // =====================================================
          // SECURITY AND COLLATERAL (from schema: collateral_details)
          // =====================================================
          'Is this loan Secured or Unsecured?',
          'What is the Collateral or Security for this loan?',
          'What is the Property Address if secured by real estate?',

          // =====================================================
          // PREPAYMENT (from schema: prepayment_penalty)
          // =====================================================
          'Is there a Prepayment Penalty?',
          'What is the Prepayment Penalty Amount or Terms?',

          // =====================================================
          // DOCUMENT IDENTIFICATION (from schema: instrument, effective_date)
          // =====================================================
          'What is the Loan Number or Note Number?',
          'What is the Date of this Note?',
          'What is the Effective Date?',

          // =====================================================
          // LEGAL AND OPERATIONAL (from schema: governing_law, currency)
          // =====================================================
          'What is the Governing Law or Jurisdiction?',
          'What is the Currency of this loan (USD)?',
        ],
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    const extractClosingDisclosure = new tasks.LambdaInvoke(this, 'ExtractClosingDisclosure', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'pageNumber.$': '$.classification.closingDisclosure',
        extractionType: 'QUERIES_AND_TABLES',
        queries: [
          // =====================================================
          // LOAN TERMS (Page 1) - from schema: instrument, effective_date
          // =====================================================
          'What is the Loan Term in months or years?',
          'What is the Loan Purpose?',
          'What is the Loan Product type?',
          'What is the Loan Type (Conventional, FHA, VA)?',
          'What is the Loan ID or Loan Number?',

          // =====================================================
          // LOAN AMOUNT AND INTEREST (from schema: interest_rate_type, rate_index)
          // =====================================================
          'What is the Loan Amount?',
          'What is the Interest Rate?',
          'What is the Annual Percentage Rate (APR)?',
          'Is the Interest Rate Adjustable or Fixed?',
          'Can the Interest Rate Increase?',
          'What is the Index Rate used (Prime, SOFR)?',
          'What is the Margin added to Index Rate?',
          'What is the Interest Rate Floor?',
          'What is the Interest Rate Ceiling or Cap?',

          // =====================================================
          // MONTHLY PAYMENT (from schema: billing_frequency, billing_type)
          // =====================================================
          'What is the Monthly Principal and Interest Payment?',
          'What is the Monthly Mortgage Insurance Payment?',
          'What is the Monthly Escrow Payment?',
          'What is the Total Monthly Payment?',
          'Can the Monthly Payment Increase?',
          'What is the First Payment Date?',

          // =====================================================
          // PROJECTED PAYMENTS
          // =====================================================
          'What is the Estimated Total Monthly Payment?',
          'What are the Projected Payments for Years 1-7?',
          'What are the Projected Payments for Years 8-30?',

          // =====================================================
          // COSTS AT CLOSING (from schema: associated_fees)
          // =====================================================
          'What is the Total Closing Costs?',
          'What is the Cash to Close?',
          'What are the Total Loan Costs?',
          'What are the Total Other Costs?',
          'What is the Total Payoffs and Payments?',

          // =====================================================
          // LOAN COSTS (Section A, B, C)
          // =====================================================
          'What is the Origination Charges total?',
          'What is the Points or Discount Points amount?',
          'What is the Services Borrower Did Not Shop For total?',
          'What is the Services Borrower Did Shop For total?',
          'What is the Appraisal Fee?',
          'What is the Credit Report Fee?',

          // =====================================================
          // OTHER COSTS (Section E, F, G, H)
          // =====================================================
          'What are the Total Taxes and Government Fees?',
          'What is the Recording Fee?',
          'What is the Transfer Tax?',
          'What are the Prepaids total?',
          'What is the Homeowners Insurance Premium?',
          'What is the Prepaid Interest?',
          'What are the Initial Escrow Payments?',

          // =====================================================
          // PROPERTY AND TRANSACTION (from schema: collateral_details)
          // =====================================================
          'What is the Property Address?',
          'What is the Sale Price of Property?',
          'What is the Appraised Value?',

          // =====================================================
          // PARTIES (from schema: borrower_names, agent)
          // =====================================================
          'Who is the Borrower Name?',
          'Who is the Co-Borrower Name?',
          'Who is the Seller Name?',
          'Who is the Lender Name?',
          'What is the Lender NMLS ID?',
          'Who is the Loan Officer?',

          // =====================================================
          // IMPORTANT DATES (from schema: effective_date, maturity_date)
          // =====================================================
          'What is the Closing Date?',
          'What is the Disbursement Date?',
          'What is the Settlement Date?',
          'What is the Maturity Date?',

          // =====================================================
          // ADDITIONAL DISCLOSURES (from schema: prepayment_penalty)
          // =====================================================
          'Is there a Prepayment Penalty?',
          'Is there a Balloon Payment?',
          'What is the Total Interest Percentage (TIP)?',
          'What is the Late Payment Fee?',
          'What is the Grace Period for late payments?',
        ],
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    const extractForm1003 = new tasks.LambdaInvoke(this, 'ExtractForm1003', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'pageNumber.$': '$.classification.form1003',
        extractionType: 'FORMS',
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    // ==========================================
    // Credit Agreement Section Extraction Tasks
    // ==========================================

    const extractCreditAgreementInfo = new tasks.LambdaInvoke(this, 'ExtractCreditAgreementInfo', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'contentHash.$': '$.contentHash',
        'size.$': '$.size',
        creditAgreementSection: 'agreementInfo',
        'sectionPages.$': '$.creditAgreementSections.sections.agreementInfo',
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    const extractCreditAgreementRates = new tasks.LambdaInvoke(this, 'ExtractCreditAgreementRates', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'contentHash.$': '$.contentHash',
        'size.$': '$.size',
        creditAgreementSection: 'applicableRates',
        'sectionPages.$': '$.creditAgreementSections.sections.applicableRates',
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    const extractCreditAgreementFacilityTerms = new tasks.LambdaInvoke(this, 'ExtractCreditAgreementFacilityTerms', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'contentHash.$': '$.contentHash',
        'size.$': '$.size',
        creditAgreementSection: 'facilityTerms',
        'sectionPages.$': '$.creditAgreementSections.sections.facilityTerms',
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    const extractCreditAgreementLenders = new tasks.LambdaInvoke(this, 'ExtractCreditAgreementLenders', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'contentHash.$': '$.contentHash',
        'size.$': '$.size',
        creditAgreementSection: 'lenderCommitments',
        'sectionPages.$': '$.creditAgreementSections.sections.lenderCommitments',
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    const extractCreditAgreementCovenants = new tasks.LambdaInvoke(this, 'ExtractCreditAgreementCovenants', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'contentHash.$': '$.contentHash',
        'size.$': '$.size',
        creditAgreementSection: 'covenants',
        'sectionPages.$': '$.creditAgreementSections.sections.covenants',
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    const extractCreditAgreementFees = new tasks.LambdaInvoke(this, 'ExtractCreditAgreementFees', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'contentHash.$': '$.contentHash',
        'size.$': '$.size',
        creditAgreementSection: 'fees',
        'sectionPages.$': '$.creditAgreementSections.sections.fees',
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    // Extract key definitions (Business Day, Interest Period, Maturity Date, LC, etc.)
    const extractCreditAgreementDefinitions = new tasks.LambdaInvoke(this, 'ExtractCreditAgreementDefinitions', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'contentHash.$': '$.contentHash',
        'size.$': '$.size',
        creditAgreementSection: 'definitions',
        'sectionPages.$': '$.creditAgreementSections.sections.definitions',
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    // Loan Agreement extraction (simple business/personal loans - not syndicated)
    // Uses comprehensive queries similar to promissory note but for multi-page agreements
    // loanAgreementSections provides router-identified target pages for intelligent extraction
    const extractLoanAgreement = new tasks.LambdaInvoke(this, 'ExtractLoanAgreement', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.documentId',
        'bucket.$': '$.bucket',
        'key.$': '$.key',
        'contentHash.$': '$.contentHash',
        'size.$': '$.size',
        'uploadedAt.$': '$.uploadedAt',
        'pageNumber.$': '$.classification.loanAgreement',
        'loanAgreementSections.$': '$.loanAgreementSections',  // Router-identified target pages
        'lowQualityPages.$': '$.lowQualityPages',  // Pages with garbled text needing Textract OCR
        isLoanAgreement: true,  // Marker for normalizer to distinguish from mortgage
        extractionType: 'QUERIES_AND_TABLES',
        queries: [
          // =====================================================
          // DOCUMENT IDENTIFICATION (from schema: instrument, effective_date)
          // =====================================================
          'What type of loan agreement is this?',
          'What is the Loan Number or Agreement Number?',
          'What is the Agreement Date or Effective Date?',
          'What is the Closing Date?',
          'What is the Instrument or Product Code?',

          // =====================================================
          // CORE LOAN TERMS (from schema: total_loan_facility_amount, maturity_date)
          // =====================================================
          'What is the Loan Amount or Principal Amount?',
          'What is the Total Credit Limit or Maximum Amount?',
          'What is the Total Facility Amount or Commitment?',
          'What is the Maturity Date or Expiration Date?',
          'What is the Loan Term (months or years)?',
          'Is this a Revolving Credit Facility or Term Loan?',
          'What is the Purpose of this loan or Use of Proceeds?',

          // =====================================================
          // INTEREST RATE DETAILS (from schema: interest_rate_type, rate_index, spread_rate, rate_calculation_method)
          // =====================================================
          'What is the Interest Rate?',
          'Is this a Fixed Rate or Variable/Floating Rate loan?',
          'What is the Annual Percentage Rate (APR)?',
          'What is the Index Rate used (Prime, SOFR, Term SOFR, Daily SOFR, Fed Funds)?',
          'What is the Margin or Spread over the Index Rate?',
          'What is the Interest Rate Floor or Minimum Rate?',
          'What is the Interest Rate Ceiling or Cap?',
          'What is the Default Interest Rate or Penalty Rate?',
          'How is interest calculated (Actual/360, Actual/365, 30/360)?',
          'What is the Rate Calculation Method or Day Count Basis?',

          // =====================================================
          // RATE SETTING (from schema: rate_setting, rate_maturity, index_frequency)
          // =====================================================
          'What is the Rate Setting Mechanism or how is the rate determined?',
          'What is the Rate Reset Frequency or Interest Period (1 Month, 3 Month, Daily)?',
          'How many Business Days before the Interest Period does the rate get set?',

          // =====================================================
          // PAYMENT INFORMATION (from schema: billing_frequency, billing_type, next_due_date)
          // =====================================================
          'What is the Monthly Payment Amount?',
          'What is the First Payment Date?',
          'When are payments due each month?',
          'What is the Payment Frequency (monthly, quarterly, semi-annually)?',
          'What is the Total Number of Payments?',
          'Is there a Balloon Payment? What amount?',
          'Is Interest payable In Arrears or In Advance?',
          'What is the Billing Type (Interest Only, Principal and Interest)?',

          // =====================================================
          // PARTIES (from schema: borrower_names, agent, lender_type)
          // =====================================================
          'Who is the Borrower or Company Name?',
          'What is the Borrower Address?',
          'Who is the Guarantor or Co-Signer?',
          'Who is the Lender?',
          'What is the Lender Address?',
          'Who is the Administrative Agent (if any)?',
          'Who is the Collateral Agent (if any)?',

          // =====================================================
          // SECURITY AND COLLATERAL (from schema: collateral_details)
          // =====================================================
          'Is this loan Secured or Unsecured?',
          'What is the Collateral for this loan?',
          'What is the Property Address if secured?',
          'What assets are pledged as Collateral?',

          // =====================================================
          // FEES AND CHARGES (from schema: associated_fees, commitment_fee)
          // =====================================================
          'What is the Origination Fee?',
          'What is the Late Payment Fee or Late Charge?',
          'What is the Grace Period for late payments?',
          'What are the Closing Costs?',
          'Are there any Annual Fees or Facility Fees?',
          'What is the Commitment Fee or Unused Fee rate?',
          'What is the Late Charge Grace Days?',

          // =====================================================
          // PREPAYMENT (from schema: prepayment_penalty)
          // =====================================================
          'Is there a Prepayment Penalty?',
          'What are the Prepayment Terms or Make-Whole provisions?',

          // =====================================================
          // FINANCIAL COVENANTS (from schema: financial_covenants with type, value, testing_frequency)
          // =====================================================
          'What are the Financial Covenants required?',
          'What is the required Debt Service Coverage Ratio (DSCR)?',
          'What is the required Current Ratio?',
          'What is the Minimum Liquidity Requirement?',
          'What is the Maximum Leverage Ratio or Debt to Equity?',
          'What is the Covenant Testing Frequency (monthly, quarterly)?',
          'What are the Negative Covenants or Restrictions?',

          // =====================================================
          // REPAYMENT TERMS (from schema: repayment schedules, billing)
          // =====================================================
          'What is the Repayment Schedule?',
          'Are there Principal Reductions or Amortization required?',
          'Is there an Interest Only Period? How long?',

          // =====================================================
          // DEFAULT AND REMEDIES (from schema: events_of_default)
          // =====================================================
          'What constitutes an Event of Default?',
          'What are the Remedies upon Default?',

          // =====================================================
          // LEGAL AND OPERATIONAL (from schema: governing_law, currency, calendar)
          // =====================================================
          'What is the Governing Law or Jurisdiction?',
          'What is the Currency of this loan (USD, EUR, GBP)?',
          'What Business Day Calendar is used (New York, London)?',
          'What are the Reporting Requirements or Financial Statements required?',
          'Is this loan Assignable or Transferable?',
        ],
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    // Parallel extraction for Loan Agreement documents (simple business loans)
    const parallelLoanAgreementExtraction = new sfn.Parallel(this, 'ParallelLoanAgreementExtraction', {
      resultPath: '$.extractions',
    });

    // Loan Agreement extraction uses comprehensive queries
    parallelLoanAgreementExtraction.branch(extractLoanAgreement);

    // Parallel extraction for mortgage documents
    const parallelMortgageExtraction = new sfn.Parallel(this, 'ParallelMortgageExtraction', {
      resultPath: '$.extractions',
    });

    parallelMortgageExtraction.branch(extractPromissoryNote);
    parallelMortgageExtraction.branch(extractClosingDisclosure);
    parallelMortgageExtraction.branch(extractForm1003);

    // Parallel extraction for Credit Agreement documents
    const parallelCreditAgreementExtraction = new sfn.Parallel(this, 'ParallelCreditAgreementExtraction', {
      resultPath: '$.extractions',
    });

    parallelCreditAgreementExtraction.branch(extractCreditAgreementInfo);
    parallelCreditAgreementExtraction.branch(extractCreditAgreementRates);
    parallelCreditAgreementExtraction.branch(extractCreditAgreementFacilityTerms);
    parallelCreditAgreementExtraction.branch(extractCreditAgreementLenders);
    parallelCreditAgreementExtraction.branch(extractCreditAgreementCovenants);
    parallelCreditAgreementExtraction.branch(extractCreditAgreementFees);
    parallelCreditAgreementExtraction.branch(extractCreditAgreementDefinitions);

    // Normalize and store
    const normalizeData = new tasks.LambdaInvoke(this, 'NormalizeData', {
      lambdaFunction: normalizerLambda,
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    // Success and failure states
    const processingComplete = new sfn.Succeed(this, 'ProcessingComplete');

    const processingFailed = new sfn.Fail(this, 'ProcessingFailed', {
      cause: 'Document processing failed',
      error: 'ProcessingError',
    });

    // Error handling
    const handleError = new sfn.Pass(this, 'HandleError', {
      result: sfn.Result.fromObject({ error: 'Processing failed' }),
    });

    // ==========================================
    // Plugin-Driven Map State (Phase 3)
    // ==========================================

    // Per-iteration failure handler for Map state
    const sectionExtractionFailed = new sfn.Pass(this, 'SectionExtractionFailed', {
      result: sfn.Result.fromObject({
        status: 'SECTION_FAILED',
        error: 'Extraction failed for this section',
      }),
    });

    // Inner LambdaInvoke for each Map iteration
    const extractSection = new tasks.LambdaInvoke(this, 'ExtractSection', {
      lambdaFunction: extractorLambda,
      payload: sfn.TaskInput.fromObject({
        'documentId.$': '$.sectionConfig.documentId',
        'bucket.$': '$.sectionConfig.bucket',
        'key.$': '$.sectionConfig.key',
        'contentHash.$': '$.sectionConfig.contentHash',
        'size.$': '$.sectionConfig.size',
        'sectionConfig.$': '$.sectionConfig',
        'pluginId.$': '$.sectionConfig.pluginId',
      }),
      outputPath: '$.Payload',
      retryOnServiceExceptions: false,
    });

    // Explicit retry for Textract throttling
    extractSection.addRetry({
      errors: [
        'ThrottlingException',
        'ProvisionedThroughputExceededException',
        'LimitExceededException',
        'Lambda.TooManyRequestsException',
      ],
      interval: cdk.Duration.seconds(2),
      maxAttempts: 3,
      backoffRate: 2.0,
    });

    // Per-iteration catch
    extractSection.addCatch(sectionExtractionFailed, {
      resultPath: '$.sectionError',
    });

    // Map state iterates over extraction plan from router
    const mapExtraction = new sfn.Map(this, 'MapExtraction', {
      comment: 'Plugin-driven: iterate over extraction plan sections from router',
      maxConcurrency: 10,
      itemsPath: '$.extractionPlan',
      itemSelector: {
        'sectionConfig.$': '$$.Map.Item.Value',
      },
      resultPath: '$.extractions',
    });

    mapExtraction.itemProcessor(extractSection);

    // Map extraction -> normalize
    mapExtraction.next(normalizeData);

    // ==========================================
    // Document Type Routing (Blue/Green)
    // ==========================================

    // Legacy choice state (retained for blue/green transition)
    const legacyDocumentTypeChoice = new sfn.Choice(this, 'LegacyDocumentTypeChoice', {
      comment: 'Legacy routing based on classification output (Parallel branches)',
    });

    // Credit Agreement path: parallel section extraction -> normalize
    parallelCreditAgreementExtraction.next(normalizeData);

    // Loan Agreement path: comprehensive loan extraction -> normalize
    parallelLoanAgreementExtraction.next(normalizeData);

    // Mortgage document path: parallel extraction -> normalize
    parallelMortgageExtraction.next(normalizeData);

    legacyDocumentTypeChoice
      .when(
        sfn.Condition.isPresent('$.creditAgreementSections'),
        parallelCreditAgreementExtraction
      )
      .when(
        sfn.Condition.isPresent('$.loanAgreementSections'),
        parallelLoanAgreementExtraction
      )
      .otherwise(parallelMortgageExtraction);

    // Primary choice: extractionPlan present AND non-empty -> Map; otherwise -> legacy
    // IMPORTANT: isPresent alone is insufficient — an empty array [] passes isPresent
    // but causes Map to run 0 iterations, producing no extraction data.
    // Belt-and-suspenders: router also omits the key when empty, but this guards
    // against any edge case where an empty array slips through.
    const extractionRouteChoice = new sfn.Choice(this, 'ExtractionRouteChoice', {
      comment: 'Blue/green: use plugin Map if router emits non-empty extractionPlan, else legacy Parallel',
    });

    extractionRouteChoice
      .when(
        sfn.Condition.and(
          sfn.Condition.isPresent('$.extractionPlan'),
          sfn.Condition.isPresent('$.extractionPlan[0]'),
        ),
        mapExtraction
      )
      .otherwise(legacyDocumentTypeChoice);

    // ==========================================
    // PageIndex Integration (Tree Building)
    // ==========================================

    // PageIndex Lambda invocation — builds hierarchical tree index
    const buildPageIndex = new tasks.LambdaInvoke(this, 'BuildPageIndex', {
      lambdaFunction: pageIndexLambda,
      outputPath: '$.Payload',
      retryOnServiceExceptions: true,
    });

    // Route choice: unstructured docs go through PageIndex, structured forms skip it
    const pageIndexRouteChoice = new sfn.Choice(this, 'PageIndexRouteChoice', {
      comment: 'Route unstructured docs (has_sections) through PageIndex tree building',
    });

    // After PageIndex: check if extraction should run now or be deferred
    const extractionModeChoice = new sfn.Choice(this, 'ExtractionModeChoice', {
      comment: 'Extract immediately or defer (understand-only mode)',
    });

    // For understand-only mode: mark document as INDEXED and complete
    const indexingComplete = new sfn.Succeed(this, 'IndexingComplete', {
      comment: 'Document indexed (tree built), extraction deferred',
    });

    // Wire PageIndex flow
    pageIndexRouteChoice
      .when(
        sfn.Condition.booleanEquals('$.classification.has_sections', true),
        buildPageIndex
      )
      .otherwise(extractionRouteChoice);

    buildPageIndex.next(extractionModeChoice);

    extractionModeChoice
      .when(
        sfn.Condition.stringEquals('$.processingMode', 'understand'),
        indexingComplete
      )
      .otherwise(extractionRouteChoice);

    // Add error handling for PageIndex
    buildPageIndex.addCatch(handleError, {
      resultPath: '$.error',
    });

    // Updated definition: classify -> PageIndex route -> extraction route
    const definition = classifyDocument.next(pageIndexRouteChoice);

    // Normalize leads to processing complete
    normalizeData.next(processingComplete);

    // Add error handling
    classifyDocument.addCatch(handleError, {
      resultPath: '$.error',
    });
    parallelCreditAgreementExtraction.addCatch(handleError, {
      resultPath: '$.error',
    });
    parallelLoanAgreementExtraction.addCatch(handleError, {
      resultPath: '$.error',
    });
    parallelMortgageExtraction.addCatch(handleError, {
      resultPath: '$.error',
    });
    mapExtraction.addCatch(handleError, {
      resultPath: '$.error',
    });
    normalizeData.addCatch(handleError, {
      resultPath: '$.error',
    });
    handleError.next(processingFailed);

    // Create state machine
    const stateMachine = new sfn.StateMachine(this, 'DocumentProcessingStateMachine', {
      stateMachineName: 'financial-doc-processor',
      definition,
      timeout: cdk.Duration.minutes(30),
      tracingEnabled: true,
      logs: {
        destination: new logs.LogGroup(this, 'StateMachineLogs', {
          logGroupName: '/aws/stepfunctions/financial-doc-processor',
          retention: logs.RetentionDays.ONE_MONTH,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
        level: sfn.LogLevel.ERROR,  // Prevent PII from financial documents appearing in CloudWatch
      },
    });

    // ==========================================
    // Trigger Lambda (S3 Event -> Step Functions)
    // ==========================================

    const triggerLambda = new lambda.Function(this, 'TriggerLambda', {
      functionName: 'doc-processor-trigger',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/trigger')),
      memorySize: 512,
      timeout: cdk.Duration.seconds(60),
      environment: {
        STATE_MACHINE_ARN: stateMachine.stateMachineArn,
        TABLE_NAME: documentTable.tableName,
        BUCKET_NAME: documentBucket.bucketName,
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    stateMachine.grantStartExecution(triggerLambda);
    documentTable.grantReadWriteData(triggerLambda);  // Need write for initial PENDING record
    documentBucket.grantRead(triggerLambda);

    // S3 event notification
    documentBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(triggerLambda),
      { prefix: 'ingest/' }
    );

    // ==========================================
    // API Lambda (REST API for Dashboard)
    // ==========================================

    const apiLambda = new lambda.Function(this, 'ApiLambda', {
      functionName: 'doc-processor-api',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/api')),
      layers: [pypdfLayer, pluginsLayer],
      memorySize: 1024,  // Plugin builder needs memory for PDF analysis
      timeout: cdk.Duration.seconds(60),  // Plugin analysis + AI generation can take time
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        TABLE_NAME: documentTable.tableName,
        STATE_MACHINE_ARN: stateMachine.stateMachineArn,
        PLUGIN_CONFIGS_TABLE: 'document-plugin-configs',
        BEDROCK_MODEL_ID: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
        CORS_ORIGIN: '*',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    documentBucket.grantReadWrite(apiLambda);
    documentTable.grantReadWriteData(apiLambda);  // Read/Write for review workflow
    stateMachine.grantRead(apiLambda);
    stateMachine.grantStartExecution(apiLambda);  // For re-processing rejected documents

    // Plugin builder needs Textract + Bedrock for sample analysis and AI config generation
    apiLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['textract:AnalyzeDocument', 'textract:DetectDocumentText'],
      resources: ['*'],
    }));
    apiLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel'],
      resources: ['*'],
    }));

    // ==========================================
    // API Gateway
    // ==========================================

    const api = new apigateway.RestApi(this, 'DocumentProcessingApi', {
      restApiName: 'Financial Documents API',
      description: 'REST API for document processing dashboard',
      deployOptions: {
        stageName: 'v1',
        tracingEnabled: true,
        loggingLevel: apigateway.MethodLoggingLevel.OFF,  // Disabled to avoid CloudWatch Logs role requirement
        dataTraceEnabled: false,
        metricsEnabled: true,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization', 'X-Api-Key'],
      },
    });

    const apiIntegration = new apigateway.LambdaIntegration(apiLambda);

    // API Routes — single proxy catches all paths to stay within Lambda
    // policy size limits (20KB). The Lambda handler does its own routing.
    api.root.addProxy({
      defaultIntegration: apiIntegration,
      anyMethod: true,
    });

    // ==========================================
    // CloudFront Distribution for Frontend
    // ==========================================

    // Origin Access Identity for CloudFront
    const originAccessIdentity = new cloudfront.OriginAccessIdentity(this, 'OAI', {
      comment: 'Financial Docs Dashboard OAI',
    });

    frontendBucket.grantRead(originAccessIdentity);

    // CloudFront Function to strip /api prefix before forwarding to API Gateway
    const apiUrlRewriteFunction = new cloudfront.Function(this, 'ApiUrlRewriteFunction', {
      functionName: `${this.stackName}-api-url-rewrite`,
      code: cloudfront.FunctionCode.fromInline(`
function handler(event) {
  var request = event.request;
  // Strip /api prefix from the URI
  if (request.uri.startsWith('/api')) {
    request.uri = request.uri.substring(4);
    // Ensure URI starts with /
    if (!request.uri.startsWith('/')) {
      request.uri = '/' + request.uri;
    }
    // Handle case where URI becomes empty
    if (request.uri === '') {
      request.uri = '/';
    }
  }
  return request;
}
      `),
      comment: 'Strips /api prefix from requests before forwarding to API Gateway',
    });

    // CloudFront distribution with custom domain
    const distribution = new cloudfront.Distribution(this, 'FrontendDistribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(frontendBucket, {
          originAccessIdentity,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      additionalBehaviors: {
        '/api/*': {
          origin: new origins.RestApiOrigin(api),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
          functionAssociations: [{
            function: apiUrlRewriteFunction,
            eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
          }],
        },
      },
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(5),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(5),
        },
      ],
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
    });

    // ==========================================
    // Phase 6: Security & Compliance
    // ==========================================

    // KMS key for PII field-level encryption
    const piiEncryptionKey = new kms.Key(this, 'PIIEncryptionKey', {
      alias: 'financial-docs-pii-encryption',
      description: 'Encrypts PII fields in financial document extractions',
      enableKeyRotation: true,
      pendingWindow: cdk.Duration.days(30),
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Cognito User Pool for API authentication
    const userPool = new cognito.UserPool(this, 'FinancialDocsUserPool', {
      userPoolName: 'financial-docs-users',
      selfSignUpEnabled: false,
      signInAliases: { email: true },
      standardAttributes: {
        email: { required: true, mutable: false },
      },
      passwordPolicy: {
        minLength: 12,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // RBAC Groups
    new cognito.CfnUserPoolGroup(this, 'AdminsGroup', {
      userPoolId: userPool.userPoolId,
      groupName: 'Admins',
      description: 'Full access: view decrypted PII, approve/reject, manage users',
    });

    new cognito.CfnUserPoolGroup(this, 'ReviewersGroup', {
      userPoolId: userPool.userPoolId,
      groupName: 'Reviewers',
      description: 'Review access: view decrypted PII, approve/reject documents',
    });

    new cognito.CfnUserPoolGroup(this, 'ViewersGroup', {
      userPoolId: userPool.userPoolId,
      groupName: 'Viewers',
      description: 'Read-only access: view masked PII only',
    });

    // App client for React frontend
    const userPoolClient = new cognito.UserPoolClient(this, 'FinancialDocsAppClient', {
      userPool,
      userPoolClientName: 'financial-docs-dashboard',
      generateSecret: false,
      authFlows: { userSrp: true },
      preventUserExistenceErrors: true,
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
    });

    // PII audit table (7-year retention for BSA/FinCEN compliance)
    const piiAuditTable = new dynamodb.Table(this, 'PIIAuditTable', {
      tableName: 'financial-documents-pii-audit',
      partitionKey: { name: 'documentId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'accessTimestamp', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: true,
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: piiEncryptionKey,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      timeToLiveAttribute: 'ttl',
    });

    piiAuditTable.addGlobalSecondaryIndex({
      indexName: 'AccessorIndex',
      partitionKey: { name: 'accessorId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'accessTimestamp', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // Cognito authorizer — deferred until attached to API methods
    // CDK requires authorizer to reference a RestApi. Will add when
    // frontend auth is enabled: { authorizer, authorizationType: COGNITO }

    // KMS grants
    piiEncryptionKey.grantEncryptDecrypt(normalizerLambda);
    piiEncryptionKey.grantEncryptDecrypt(apiLambda);
    piiAuditTable.grantWriteData(apiLambda);

    // ==========================================
    // Plugin Config Store (Self-Service Plugin Builder)
    // ==========================================

    const pluginConfigsTable = new dynamodb.Table(this, 'PluginConfigsTable', {
      tableName: 'document-plugin-configs',
      partitionKey: { name: 'pluginId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'version', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    pluginConfigsTable.addGlobalSecondaryIndex({
      indexName: 'StatusIndex',
      partitionKey: { name: 'status', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'updatedAt', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // API Lambda needs read/write for config CRUD
    pluginConfigsTable.grantReadWriteData(apiLambda);
    // Router/Extractor/Normalizer need read for published configs
    pluginConfigsTable.grantReadData(routerLambda);
    pluginConfigsTable.grantReadData(extractorLambda);
    pluginConfigsTable.grantReadData(normalizerLambda);
    pluginConfigsTable.grantReadData(pageIndexLambda);

    // ==========================================
    // Outputs
    // ==========================================

    new cdk.CfnOutput(this, 'PluginConfigsTableName', {
      value: pluginConfigsTable.tableName,
      description: 'DynamoDB table for dynamic plugin configurations',
      exportName: 'FinancialDocPluginConfigsTable',
    });

    new cdk.CfnOutput(this, 'UserPoolId', {
      value: userPool.userPoolId,
      description: 'Cognito User Pool ID',
      exportName: 'FinancialDocUserPoolId',
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: userPoolClient.userPoolClientId,
      description: 'Cognito App Client ID',
      exportName: 'FinancialDocUserPoolClientId',
    });

    new cdk.CfnOutput(this, 'PIIEncryptionKeyArn', {
      value: piiEncryptionKey.keyArn,
      description: 'KMS key ARN for PII encryption',
      exportName: 'FinancialDocPIIKeyArn',
    });

    new cdk.CfnOutput(this, 'PIIAuditTableName', {
      value: piiAuditTable.tableName,
      description: 'PII access audit table',
      exportName: 'FinancialDocPIIAuditTable',
    });

    new cdk.CfnOutput(this, 'DocumentBucketName', {
      value: documentBucket.bucketName,
      description: 'S3 bucket for document ingestion',
      exportName: 'FinancialDocBucket',
    });

    new cdk.CfnOutput(this, 'FrontendBucketName', {
      value: frontendBucket.bucketName,
      description: 'S3 bucket for frontend assets',
      exportName: 'FinancialDocFrontendBucket',
    });

    new cdk.CfnOutput(this, 'DocumentTableName', {
      value: documentTable.tableName,
      description: 'DynamoDB table for extracted data',
      exportName: 'FinancialDocTable',
    });

    new cdk.CfnOutput(this, 'StateMachineArn', {
      value: stateMachine.stateMachineArn,
      description: 'Step Functions state machine ARN',
      exportName: 'FinancialDocStateMachine',
    });

    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: api.url,
      description: 'API Gateway endpoint URL',
      exportName: 'FinancialDocApiEndpoint',
    });

    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      value: `https://${distribution.distributionDomainName}`,
      description: 'CloudFront distribution URL for the dashboard',
      exportName: 'FinancialDocDashboardUrl',
    });

    new cdk.CfnOutput(this, 'UploadCommand', {
      value: `aws s3 cp <your-file.pdf> s3://${documentBucket.bucketName}/ingest/`,
      description: 'Command to upload a document for processing',
    });
  }
}
