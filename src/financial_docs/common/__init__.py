"""Common utilities for Financial Documents Processing Lambda functions."""

from .aws_clients import get_s3_client, get_bedrock_client, get_textract_client, get_dynamodb_resource
from .config import Settings
from .models import DocumentClassification, ExtractionResult, NormalizedLoanData
from .exceptions import DocumentProcessingError, ClassificationError, ExtractionError

__all__ = [
    "get_s3_client",
    "get_bedrock_client",
    "get_textract_client",
    "get_dynamodb_resource",
    "Settings",
    "DocumentClassification",
    "ExtractionResult",
    "NormalizedLoanData",
    "DocumentProcessingError",
    "ClassificationError",
    "ExtractionError",
]
