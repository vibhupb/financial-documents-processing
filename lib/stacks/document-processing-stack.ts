import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as logs from 'aws-cdk-lib/aws-logs';
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
      ],
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

    // ==========================================
    // Lambda Layers
    // ==========================================

    // PyPDF Layer for PDF processing
    const pypdfLayer = new lambda.LayerVersion(this, 'PyPDFLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/layers/pypdf')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'PyPDF library for PDF text extraction',
    });

    // ==========================================
    // Layer 2: Router Lambda (Classification)
    // ==========================================

    const routerLambda = new lambda.Function(this, 'RouterLambda', {
      functionName: 'doc-processor-router',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/router')),
      layers: [pypdfLayer],
      memorySize: 1024,
      timeout: cdk.Duration.minutes(5),
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        BEDROCK_MODEL_ID: 'anthropic.claude-3-haiku-20240307-v1:0',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    // Grant permissions
    documentBucket.grantRead(routerLambda);
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
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/extractor')),
      memorySize: 512,
      timeout: cdk.Duration.minutes(5),
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
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
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/normalizer')),
      memorySize: 512,
      timeout: cdk.Duration.minutes(5),
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        TABLE_NAME: documentTable.tableName,
        BEDROCK_MODEL_ID: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    documentBucket.grantReadWrite(normalizerLambda);
    documentTable.grantWriteData(normalizerLambda);
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

    // Parallel extraction state
    const parallelExtraction = new sfn.Parallel(this, 'ParallelExtraction', {
      resultPath: '$.extractions',
    });

    parallelExtraction.branch(extractPromissoryNote);
    parallelExtraction.branch(extractClosingDisclosure);
    parallelExtraction.branch(extractForm1003);

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

    // Build the state machine
    const definition = classifyDocument
      .next(parallelExtraction)
      .next(normalizeData)
      .next(processingComplete);

    // Add error handling
    classifyDocument.addCatch(handleError, {
      resultPath: '$.error',
    });
    parallelExtraction.addCatch(handleError, {
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
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/trigger')),
      memorySize: 256,
      timeout: cdk.Duration.seconds(30),
      environment: {
        STATE_MACHINE_ARN: stateMachine.stateMachineArn,
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    stateMachine.grantStartExecution(triggerLambda);

    // S3 event notification
    documentBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(triggerLambda),
      { prefix: 'ingest/' }
    );

    // ==========================================
    // Outputs
    // ==========================================

    new cdk.CfnOutput(this, 'DocumentBucketName', {
      value: documentBucket.bucketName,
      description: 'S3 bucket for document ingestion',
      exportName: 'FinancialDocBucket',
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

    new cdk.CfnOutput(this, 'UploadCommand', {
      value: `aws s3 cp <your-file.pdf> s3://${documentBucket.bucketName}/ingest/`,
      description: 'Command to upload a document for processing',
    });
  }
}
