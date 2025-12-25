"""AWS client factory functions with connection pooling."""

import boto3
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def get_s3_client() -> Any:
    """Get a cached S3 client instance."""
    return boto3.client("s3")


@lru_cache(maxsize=1)
def get_bedrock_client() -> Any:
    """Get a cached Bedrock Runtime client instance."""
    return boto3.client("bedrock-runtime")


@lru_cache(maxsize=1)
def get_textract_client() -> Any:
    """Get a cached Textract client instance."""
    return boto3.client("textract")


@lru_cache(maxsize=1)
def get_dynamodb_resource() -> Any:
    """Get a cached DynamoDB resource instance."""
    return boto3.resource("dynamodb")


@lru_cache(maxsize=1)
def get_stepfunctions_client() -> Any:
    """Get a cached Step Functions client instance."""
    return boto3.client("stepfunctions")
