#!/usr/bin/env python3
"""
Generate AWS Architecture Diagram for Financial Documents Processing System (v5.5.0).

Full architecture including:
- React Frontend on CloudFront/S3
- API Gateway + API Lambda + Compliance API Lambda
- S3 Document Ingestion + Trigger (SHA-256 dedup)
- Step Functions Orchestration with Router Pattern Pipeline + Compliance Pipeline
- 9 Lambda functions total
- Bedrock AI (Haiku 4.5 + Sonnet 4.6)
- Textract targeted extraction
- 6 DynamoDB tables + S3 Audit
- Cognito RBAC (3 groups) + KMS PII encryption
- CloudWatch monitoring
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.network import CloudFront, APIGateway
from diagrams.aws.database import Dynamodb
from diagrams.aws.storage import S3
from diagrams.aws.integration import StepFunctions
from diagrams.aws.ml import Bedrock, Textract
from diagrams.aws.general import Users
from diagrams.aws.management import Cloudwatch
from diagrams.aws.security import Cognito, KMS


# --- Light theme configuration ---
graph_attr = {
    "bgcolor": "#f8fafc",
    "fontcolor": "#1e293b",
    "fontname": "Arial Bold",
    "fontsize": "24",
    "pad": "1.0",
    "splines": "ortho",
    "nodesep": "0.8",
    "ranksep": "1.0",
    "dpi": "200",
    "compound": "true",
}

node_attr = {
    "fontcolor": "#1e293b",
    "fontname": "Arial",
    "fontsize": "11",
}

edge_attr = {
    "fontcolor": "#475569",
    "fontname": "Arial",
    "fontsize": "9",
}

# --- Cluster styles ---
aws_cloud_style = {
    "bgcolor": "#fff7ed",
    "fontcolor": "#c2410c",
    "fontsize": "18",
    "pencolor": "#f97316",
    "penwidth": "3",
    "style": "rounded",
}

frontend_cluster_style = {
    "bgcolor": "#eff6ff",
    "fontcolor": "#1d4ed8",
    "fontsize": "14",
    "pencolor": "#3b82f6",
    "penwidth": "2",
    "style": "rounded",
}

api_cluster_style = {
    "bgcolor": "#f0fdf4",
    "fontcolor": "#15803d",
    "fontsize": "14",
    "pencolor": "#22c55e",
    "penwidth": "2",
    "style": "rounded",
}

ingestion_cluster_style = {
    "bgcolor": "#f1f5f9",
    "fontcolor": "#475569",
    "fontsize": "14",
    "pencolor": "#64748b",
    "penwidth": "2",
    "style": "rounded",
}

step_functions_cluster_style = {
    "bgcolor": "#fff1f2",
    "fontcolor": "#be123c",
    "fontsize": "14",
    "pencolor": "#f43f5e",
    "penwidth": "2",
    "style": "rounded",
}

router_pipeline_style = {
    "bgcolor": "#faf5ff",
    "fontcolor": "#7c3aed",
    "fontsize": "12",
    "pencolor": "#8b5cf6",
    "penwidth": "2",
    "style": "rounded",
}

compliance_pipeline_style = {
    "bgcolor": "#fefce8",
    "fontcolor": "#a16207",
    "fontsize": "12",
    "pencolor": "#eab308",
    "penwidth": "2",
    "style": "rounded",
}

ai_cluster_style = {
    "bgcolor": "#fffbeb",
    "fontcolor": "#b45309",
    "fontsize": "14",
    "pencolor": "#f59e0b",
    "penwidth": "2",
    "style": "rounded",
}

storage_cluster_style = {
    "bgcolor": "#f1f5f9",
    "fontcolor": "#475569",
    "fontsize": "14",
    "pencolor": "#64748b",
    "penwidth": "2",
    "style": "rounded",
}

security_cluster_style = {
    "bgcolor": "#fdf2f8",
    "fontcolor": "#9d174d",
    "fontsize": "14",
    "pencolor": "#ec4899",
    "penwidth": "2",
    "style": "rounded",
}


# --- Diagram ---
with Diagram(
    "Financial Documents Processing - v5.5.0 Architecture",
    filename="docs/aws-architecture",
    outformat="png",
    show=False,
    direction="TB",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    # Users
    users = Users("Users")

    with Cluster("AWS Cloud", graph_attr=aws_cloud_style):

        # ---- 1. Frontend ----
        with Cluster("Frontend", graph_attr=frontend_cluster_style):
            cloudfront = CloudFront("CloudFront CDN")
            s3_frontend = S3("S3 Frontend\nStatic Hosting")

        # ---- 7. Security ----
        with Cluster("Security", graph_attr=security_cluster_style):
            cognito = Cognito("Cognito\n(3 RBAC Groups)")
            kms = KMS("KMS\nPII Encryption")

        # ---- 2. API Layer ----
        with Cluster("API Layer", graph_attr=api_cluster_style):
            api_gw = APIGateway("API Gateway")
            api_lambda = Lambda("doc-processor-api\n(CRUD, Upload,\nReview, Q&A)")
            compliance_api = Lambda("doc-processor-\ncompliance-api\n(Baseline CRUD)")

        # ---- 3. Document Ingestion ----
        with Cluster("Document Ingestion", graph_attr=ingestion_cluster_style):
            s3_ingest = S3("S3 Documents\nBucket")
            trigger_lambda = Lambda("doc-processor-trigger\n(SHA-256 Dedup)")

        # ---- 4. Step Functions ----
        with Cluster("Step Functions Orchestrator", graph_attr=step_functions_cluster_style):
            sfn = StepFunctions("financial-doc-\nprocessor")

            # Router Pipeline
            with Cluster("Router Pipeline", graph_attr=router_pipeline_style):
                router_lambda = Lambda("doc-processor-\nrouter\n(Classification)")
                pageindex_lambda = Lambda("doc-processor-\npageindex\n(Tree Building)")
                extractor_lambda = Lambda("doc-processor-\nextractor\n(Textract)")
                normalizer_lambda = Lambda("doc-processor-\nnormalizer\n(Refinement)")

            # Compliance Pipeline
            with Cluster("Compliance Pipeline", graph_attr=compliance_pipeline_style):
                compliance_ingest = Lambda("doc-processor-\ncompliance-ingest\n(Req Extraction)")
                compliance_evaluate = Lambda("doc-processor-\ncompliance-evaluate\n(Semantic Eval)")

        # ---- 5. AI Services ----
        with Cluster("AI Services", graph_attr=ai_cluster_style):
            bedrock_haiku = Bedrock("Bedrock\nClaude Haiku 4.5")
            bedrock_sonnet = Bedrock("Bedrock\nClaude Sonnet 4.6")
            textract = Textract("Amazon Textract\nTables + Queries")

        # ---- 6. Data Storage ----
        with Cluster("Data Storage", graph_attr=storage_cluster_style):
            ddb_documents = Dynamodb("financial-\ndocuments")
            ddb_baselines = Dynamodb("compliance-\nbaselines")
            ddb_reports = Dynamodb("compliance-\nreports")
            ddb_feedback = Dynamodb("compliance-\nfeedback")
            ddb_plugins = Dynamodb("document-\nplugin-configs")
            ddb_pii = Dynamodb("financial-documents-\npii-audit")
            s3_audit = S3("S3 Audit Trail\n(Raw Results)")

        # Monitoring
        cloudwatch = Cloudwatch("CloudWatch\nLogs & Metrics")

    # ===== Edge Flows =====

    # 1. Users -> CloudFront -> S3 Frontend
    users >> Edge(color="#3b82f6", penwidth="2", label="HTTPS") >> cloudfront
    cloudfront >> Edge(color="#3b82f6") >> s3_frontend

    # 2. Users -> API Gateway -> API Lambda -> DynamoDB
    users >> Edge(color="#22c55e", penwidth="2", label="REST API") >> api_gw
    api_gw >> Edge(color="#22c55e") >> api_lambda
    api_gw >> Edge(color="#22c55e") >> compliance_api
    api_lambda >> Edge(color="#22c55e", style="dashed") >> ddb_documents
    compliance_api >> Edge(color="#22c55e", style="dashed") >> ddb_baselines

    # 8. Cognito -> API Gateway (auth)
    cognito >> Edge(color="#ec4899", penwidth="2", label="Auth") >> api_gw

    # 3. S3 Ingest -> Trigger -> Step Functions
    api_lambda >> Edge(
        color="#22c55e", style="dashed", label="Presigned URL"
    ) >> s3_ingest
    s3_ingest >> Edge(
        color="#f43f5e", penwidth="2", label="S3 Event"
    ) >> trigger_lambda
    trigger_lambda >> Edge(
        color="#f43f5e", label="Check Dup"
    ) >> ddb_documents
    trigger_lambda >> Edge(
        color="#f43f5e", penwidth="2", label="Start Execution"
    ) >> sfn

    # 4. Step Functions internal: Router Pipeline
    sfn >> Edge(color="#8b5cf6", penwidth="2") >> router_lambda
    router_lambda >> Edge(
        color="#8b5cf6", penwidth="2"
    ) >> pageindex_lambda
    pageindex_lambda >> Edge(
        color="#8b5cf6", penwidth="2"
    ) >> extractor_lambda
    extractor_lambda >> Edge(
        color="#8b5cf6", penwidth="2"
    ) >> normalizer_lambda
    normalizer_lambda >> Edge(
        color="#64748b", penwidth="2", label="Final Data"
    ) >> ddb_documents

    # 4b. Step Functions internal: Compliance Pipeline (parallel with extraction)
    sfn >> Edge(
        color="#eab308", penwidth="2", style="dashed"
    ) >> compliance_ingest
    compliance_ingest >> Edge(
        color="#eab308", penwidth="2"
    ) >> compliance_evaluate
    compliance_evaluate >> Edge(
        color="#64748b", style="dashed"
    ) >> ddb_reports

    # 6. Router/PageIndex/Normalizer -> Bedrock Haiku
    router_lambda >> Edge(color="#f59e0b", label="Classify") >> bedrock_haiku
    pageindex_lambda >> Edge(
        color="#f59e0b", label="Build Tree"
    ) >> bedrock_haiku
    normalizer_lambda >> Edge(
        color="#f59e0b", label="Normalize"
    ) >> bedrock_haiku

    # 5. Compliance Ingest/Evaluate -> Bedrock Sonnet
    compliance_ingest >> Edge(
        color="#f59e0b", label="Extract Reqs"
    ) >> bedrock_haiku
    compliance_evaluate >> Edge(
        color="#f59e0b", label="Semantic Eval"
    ) >> bedrock_sonnet

    # 7. Extractor -> Textract
    extractor_lambda >> Edge(
        color="#f59e0b", label="OCR Pages"
    ) >> textract

    # 9. KMS encryption (dashed to storage)
    kms >> Edge(
        color="#ec4899", style="dashed", label="Encrypt"
    ) >> ddb_pii
    kms >> Edge(color="#ec4899", style="dashed") >> s3_ingest

    # Audit trail
    normalizer_lambda >> Edge(
        color="#64748b", style="dashed", label="Audit"
    ) >> s3_audit
    pageindex_lambda >> Edge(
        color="#64748b", style="dashed", label="Cache Tree"
    ) >> ddb_documents

    # Monitoring
    sfn >> Edge(color="#94a3b8", style="dashed") >> cloudwatch


print("Architecture diagram saved to docs/aws-architecture.png")
