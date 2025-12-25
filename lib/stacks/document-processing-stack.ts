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
      description: 'PyPDF library for PDF text extraction',
    });

    // ==========================================
    // Layer 2: Router Lambda (Classification)
    // ==========================================

    const routerLambda = new lambda.Function(this, 'RouterLambda', {
      functionName: 'doc-processor-router',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/router')),
      layers: [pypdfLayer],
      memorySize: 1024,
      timeout: cdk.Duration.minutes(5),
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        TABLE_NAME: documentTable.tableName,  // For status updates
        BEDROCK_MODEL_ID: 'us.anthropic.claude-3-haiku-20240307-v1:0',
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
      layers: [pypdfLayer],
      memorySize: 1024,  // Increased for multi-page PDF rendering
      timeout: cdk.Duration.minutes(10),  // Increased for large sections
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        // AWS recommends 90%+ for financial applications; using 85% as default
        // to balance accuracy with data completeness
        CONFIDENCE_THRESHOLD: '85.0',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    documentBucket.grantReadWrite(extractorLambda);
    extractorLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'textract:AnalyzeDocument',
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
      memorySize: 512,  // Reduced - Claude 3.5 Haiku is efficient
      timeout: cdk.Duration.minutes(5),  // Reduced - Haiku is faster
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        TABLE_NAME: documentTable.tableName,
        BEDROCK_MODEL_ID: 'us.anthropic.claude-3-5-haiku-20241022-v1:0',  // Claude 3.5 Haiku for cost optimization
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
          'What is the Interest Rate?',
          'What is the Principal Amount?',
          'Who is the Borrower?',
          'What is the Maturity Date?',
          'What is the Monthly Payment Amount?',
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
        extractionType: 'TABLES',
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
    // Document Type Routing (Choice State)
    // ==========================================

    // Choice state to route based on primary document type
    const documentTypeChoice = new sfn.Choice(this, 'DocumentTypeChoice', {
      comment: 'Route based on the primary document type detected by the router',
    });

    // Credit Agreement path: parallel section extraction -> normalize
    parallelCreditAgreementExtraction.next(normalizeData);

    // Mortgage document path: parallel extraction -> normalize
    parallelMortgageExtraction.next(normalizeData);

    // Build the state machine with document type routing
    const definition = classifyDocument.next(
      documentTypeChoice
        .when(
          sfn.Condition.isPresent('$.creditAgreementSections'),
          parallelCreditAgreementExtraction
        )
        .otherwise(parallelMortgageExtraction)
    );

    // Normalize leads to processing complete
    normalizeData.next(processingComplete);

    // Add error handling
    classifyDocument.addCatch(handleError, {
      resultPath: '$.error',
    });
    parallelCreditAgreementExtraction.addCatch(handleError, {
      resultPath: '$.error',
    });
    parallelMortgageExtraction.addCatch(handleError, {
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
        level: sfn.LogLevel.ALL,
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
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        TABLE_NAME: documentTable.tableName,
        STATE_MACHINE_ARN: stateMachine.stateMachineArn,
        CORS_ORIGIN: '*',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    documentBucket.grantReadWrite(apiLambda);
    documentTable.grantReadWriteData(apiLambda);  // Read/Write for review workflow
    stateMachine.grantRead(apiLambda);
    stateMachine.grantStartExecution(apiLambda);  // For re-processing rejected documents

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

    // API Routes
    const documentsResource = api.root.addResource('documents');
    documentsResource.addMethod('GET', apiIntegration);

    const documentByIdResource = documentsResource.addResource('{documentId}');
    documentByIdResource.addMethod('GET', apiIntegration);

    const documentAuditResource = documentByIdResource.addResource('audit');
    documentAuditResource.addMethod('GET', apiIntegration);

    const documentStatusResource = documentByIdResource.addResource('status');
    documentStatusResource.addMethod('GET', apiIntegration);

    const documentPdfResource = documentByIdResource.addResource('pdf');
    documentPdfResource.addMethod('GET', apiIntegration);

    // Document correction and reprocessing routes
    const documentFieldsResource = documentByIdResource.addResource('fields');
    documentFieldsResource.addMethod('PUT', apiIntegration);

    const documentReprocessResource = documentByIdResource.addResource('reprocess');
    documentReprocessResource.addMethod('POST', apiIntegration);

    const uploadResource = api.root.addResource('upload');
    uploadResource.addMethod('POST', apiIntegration);

    const metricsResource = api.root.addResource('metrics');
    metricsResource.addMethod('GET', apiIntegration);

    // Review workflow routes
    const reviewResource = api.root.addResource('review');
    reviewResource.addMethod('GET', apiIntegration);  // List review queue

    const reviewByIdResource = reviewResource.addResource('{documentId}');
    reviewByIdResource.addMethod('GET', apiIntegration);  // Get document for review

    const reviewApproveResource = reviewByIdResource.addResource('approve');
    reviewApproveResource.addMethod('POST', apiIntegration);  // Approve document

    const reviewRejectResource = reviewByIdResource.addResource('reject');
    reviewRejectResource.addMethod('POST', apiIntegration);  // Reject document

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
    // Outputs
    // ==========================================

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
