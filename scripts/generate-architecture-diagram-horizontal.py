#!/usr/bin/env python3
"""
Generate Horizontal AWS Architecture Diagram for Financial Documents Processing.
Optimized for presentations and README display with light theme.
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.network import CloudFront, APIGateway
from diagrams.aws.database import Dynamodb
from diagrams.aws.storage import S3
from diagrams.aws.integration import StepFunctions
from diagrams.aws.ml import Bedrock, Textract
from diagrams.aws.general import Users

# Light theme configuration for presentations
graph_attr = {
    "bgcolor": "#f8fafc",       # Light slate background
    "fontcolor": "#1e293b",     # Dark text
    "fontname": "Arial Bold",
    "fontsize": "20",
    "pad": "0.8",
    "splines": "ortho",         # Straight orthogonal lines
    "nodesep": "0.6",
    "ranksep": "0.8",
    "dpi": "150",
}

node_attr = {
    "fontcolor": "#1e293b",
    "fontname": "Arial",
    "fontsize": "10",
}

edge_attr = {
    "fontcolor": "#475569",
    "fontname": "Arial",
    "fontsize": "8",
}

# Cluster styles - Light theme
aws_cloud_style = {
    "bgcolor": "#fff7ed",
    "fontcolor": "#c2410c",
    "fontsize": "14",
    "pencolor": "#f97316",
    "penwidth": "2",
    "style": "rounded",
}

frontend_style = {
    "bgcolor": "#eff6ff",
    "fontcolor": "#1d4ed8",
    "fontsize": "11",
    "style": "rounded",
}

processing_style = {
    "bgcolor": "#faf5ff",
    "fontcolor": "#7c3aed",
    "fontsize": "11",
    "pencolor": "#8b5cf6",
    "penwidth": "2",
    "style": "rounded",
}

ai_style = {
    "bgcolor": "#fffbeb",
    "fontcolor": "#b45309",
    "fontsize": "10",
    "style": "rounded",
}

storage_style = {
    "bgcolor": "#f1f5f9",
    "fontcolor": "#475569",
    "fontsize": "11",
    "style": "rounded",
}

with Diagram(
    "Financial Documents Processing - Router Pattern",
    filename="docs/aws-architecture-horizontal",
    outformat="png",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    users = Users("Users")

    with Cluster("AWS Cloud", graph_attr=aws_cloud_style):

        # Frontend
        with Cluster("Frontend", graph_attr=frontend_style):
            cloudfront = CloudFront("CloudFront")
            s3_web = S3("S3 Static")

        # API
        api_gw = APIGateway("API Gateway")
        api_lambda = Lambda("API")

        # Ingestion
        with Cluster("Ingestion", graph_attr=storage_style):
            s3_ingest = S3("S3 Ingest")
            trigger = Lambda("Trigger")

        # Step Functions
        with Cluster("Step Functions - Router Pattern", graph_attr=processing_style):
            sfn = StepFunctions("Orchestrator")

            with Cluster("1. Router", graph_attr=ai_style):
                router = Lambda("Classify")
                haiku1 = Bedrock("Haiku 4.5\n$0.023")

            with Cluster("2. Extractor", graph_attr=ai_style):
                extractor = Lambda("Extract")
                textract = Textract("Textract\n$0.30")

            with Cluster("3. Normalizer", graph_attr=ai_style):
                normalizer = Lambda("Normalize")
                haiku2 = Bedrock("Haiku 4.5\n$0.013")

        # Storage
        with Cluster("Storage", graph_attr=storage_style):
            dynamodb = Dynamodb("DynamoDB")
            s3_audit = S3("S3 Audit")

    # Connections
    users >> Edge(color="#3b82f6", penwidth="2") >> cloudfront
    cloudfront >> s3_web

    users >> Edge(color="#22c55e", style="dashed") >> api_gw
    api_gw >> api_lambda
    api_lambda >> Edge(color="#22c55e", style="dashed") >> s3_ingest

    s3_ingest >> Edge(color="#f43f5e", penwidth="2") >> trigger
    trigger >> Edge(color="#f43f5e", penwidth="2") >> sfn

    sfn >> Edge(color="#8b5cf6") >> router
    router >> Edge(color="#f59e0b") >> haiku1

    router >> Edge(color="#8b5cf6") >> extractor
    extractor >> Edge(color="#f59e0b") >> textract

    extractor >> Edge(color="#8b5cf6") >> normalizer
    normalizer >> Edge(color="#f59e0b") >> haiku2

    normalizer >> Edge(color="#64748b", penwidth="2") >> dynamodb
    normalizer >> Edge(color="#64748b", style="dashed") >> s3_audit

    api_lambda >> Edge(color="#22c55e", style="dashed") >> dynamodb

print("Horizontal diagram saved to docs/aws-architecture-horizontal.png")
