#!/usr/bin/env python3
"""
Generate AWS Architecture Diagram for Financial Documents Processing System.

This creates a professional, publication-ready architecture diagram showing:
- React Frontend on CloudFront/S3
- API Gateway + Lambda API
- S3 Document Ingestion
- Step Functions Orchestration (Router Pattern)
- Lambda Processing Pipeline (Router -> Extractor -> Normalizer)
- Bedrock AI (Claude Haiku) & Textract
- DynamoDB & S3 Audit Storage
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


# Light theme configuration for presentations
graph_attr = {
    "bgcolor": "#f8fafc",       # Light slate background
    "fontcolor": "#1e293b",     # Dark text for titles
    "fontname": "Arial Bold",
    "fontsize": "24",
    "pad": "1.0",
    "splines": "ortho",         # Straight orthogonal lines
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

# Cluster styles - Light theme
aws_cloud_style = {
    "bgcolor": "#fff7ed",       # Light orange tint
    "fontcolor": "#c2410c",     # AWS Orange darker
    "fontsize": "18",
    "pencolor": "#f97316",      # AWS Orange
    "penwidth": "3",
    "style": "rounded",
}

frontend_cluster_style = {
    "bgcolor": "#eff6ff",       # Light blue
    "fontcolor": "#1d4ed8",
    "fontsize": "14",
    "pencolor": "#3b82f6",
    "penwidth": "2",
    "style": "rounded",
}

api_cluster_style = {
    "bgcolor": "#f0fdf4",       # Light green
    "fontcolor": "#15803d",
    "fontsize": "14",
    "pencolor": "#22c55e",
    "penwidth": "2",
    "style": "rounded",
}

processing_cluster_style = {
    "bgcolor": "#faf5ff",       # Light purple
    "fontcolor": "#7c3aed",
    "fontsize": "14",
    "pencolor": "#8b5cf6",
    "penwidth": "2",
    "style": "rounded",
}

ai_cluster_style = {
    "bgcolor": "#fffbeb",       # Light amber
    "fontcolor": "#b45309",
    "fontsize": "12",
    "pencolor": "#f59e0b",
    "penwidth": "2",
    "style": "rounded",
}

storage_cluster_style = {
    "bgcolor": "#f1f5f9",       # Light slate
    "fontcolor": "#475569",
    "fontsize": "14",
    "pencolor": "#64748b",
    "penwidth": "2",
    "style": "rounded",
}

step_functions_cluster_style = {
    "bgcolor": "#fff1f2",       # Light rose
    "fontcolor": "#be123c",
    "fontsize": "14",
    "pencolor": "#f43f5e",
    "penwidth": "2",
    "style": "rounded",
}

with Diagram(
    "Financial Documents Processing - Router Pattern Architecture",
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

        # Frontend Layer
        with Cluster("Frontend (CloudFront + S3)", graph_attr=frontend_cluster_style):
            cloudfront = CloudFront("CloudFront CDN")
            s3_frontend = S3("S3 Static\nHosting")

        # API Layer
        with Cluster("REST API", graph_attr=api_cluster_style):
            api_gw = APIGateway("API Gateway")
            api_lambda = Lambda("API Lambda\n(CRUD, Upload,\nReview)")

        # Ingestion
        with Cluster("Document Ingestion", graph_attr=storage_cluster_style):
            s3_ingest = S3("S3 Ingest\nBucket")
            trigger_lambda = Lambda("Trigger Lambda\n(Dedup, SHA-256)")

        # Step Functions Orchestration
        with Cluster("Step Functions Orchestrator", graph_attr=step_functions_cluster_style):
            sfn = StepFunctions("State Machine")

            # Processing Pipeline inside Step Functions
            with Cluster("Router Pattern Pipeline", graph_attr=processing_cluster_style):

                # Router Stage
                with Cluster("1. ROUTER: Classification", graph_attr=ai_cluster_style):
                    router_lambda = Lambda("Router Lambda")
                    bedrock_haiku = Bedrock("Claude 3 Haiku\n~$0.006/doc")

                # Extractor Stage
                with Cluster("2. EXTRACTOR: Targeted Pages", graph_attr=ai_cluster_style):
                    extractor_lambda = Lambda("Extractor Lambda")
                    textract = Textract("Textract\nTables+Queries\n~$0.30/doc")

                # Normalizer Stage
                with Cluster("3. NORMALIZER: Refinement", graph_attr=ai_cluster_style):
                    normalizer_lambda = Lambda("Normalizer Lambda")
                    bedrock_haiku_norm = Bedrock("Claude 3.5 Haiku\n~$0.03/doc")

        # Data Storage
        with Cluster("Data Storage", graph_attr=storage_cluster_style):
            dynamodb = Dynamodb("DynamoDB\n(Documents +\nExtracted Data)")
            s3_audit = S3("S3 Audit Trail\n(Raw Results)")

        # Monitoring
        cloudwatch = Cloudwatch("CloudWatch\nLogs & Metrics")

    # Connections - User Flow
    users >> Edge(color="#3b82f6", penwidth="2", label="HTTPS") >> cloudfront
    cloudfront >> Edge(color="#3b82f6") >> s3_frontend

    # API Flow
    users >> Edge(color="#22c55e", penwidth="2", label="REST API") >> api_gw
    api_gw >> Edge(color="#22c55e") >> api_lambda
    api_lambda >> Edge(color="#22c55e", style="dashed") >> dynamodb
    api_lambda >> Edge(color="#22c55e", style="dashed", label="Presigned URL") >> s3_ingest

    # Document Upload Flow
    cloudfront >> Edge(color="#f97316", label="Upload") >> s3_ingest
    s3_ingest >> Edge(color="#f43f5e", penwidth="2", label="S3 Event") >> trigger_lambda
    trigger_lambda >> Edge(color="#f43f5e", label="Check Duplicate") >> dynamodb
    trigger_lambda >> Edge(color="#f43f5e", penwidth="2", label="Start Execution") >> sfn

    # Step Functions Internal Flow
    sfn >> Edge(color="#8b5cf6", penwidth="2") >> router_lambda
    router_lambda >> Edge(color="#f59e0b", label="Classify") >> bedrock_haiku

    router_lambda >> Edge(color="#8b5cf6", penwidth="2", label="Page Map") >> extractor_lambda
    extractor_lambda >> Edge(color="#f59e0b", label="OCR Pages") >> textract

    extractor_lambda >> Edge(color="#8b5cf6", penwidth="2", label="Raw Data") >> normalizer_lambda
    normalizer_lambda >> Edge(color="#f59e0b", label="Normalize") >> bedrock_haiku_norm

    # Storage Output
    normalizer_lambda >> Edge(color="#64748b", penwidth="2", label="Final Data") >> dynamodb
    normalizer_lambda >> Edge(color="#64748b", style="dashed", label="Audit") >> s3_audit

    # Monitoring
    sfn >> Edge(color="#94a3b8", style="dashed") >> cloudwatch

print("Architecture diagram saved to docs/aws-architecture.png")
