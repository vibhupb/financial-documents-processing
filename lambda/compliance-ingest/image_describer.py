"""Describe embedded images using Bedrock Claude Haiku 4.5 vision.

Adapted from GAIK toolkit's VisionRagParser pattern: classify image type
(chart/diagram/table/photo) and apply a type-specific prompt for concise,
structured descriptions that are injected back into parsed text.
"""
from __future__ import annotations

import base64
import os

import boto3
from botocore.config import Config

bedrock = boto3.client("bedrock-runtime", config=Config(max_pool_connections=10))
MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)

VISION_PROMPTS = {
    "chart": (
        "This is a chart/graph from a financial regulatory document.\n"
        "1. State the title and axis labels if visible.\n"
        "2. List all data points or trends with exact numbers.\n"
        "3. Summarize the key insight in one sentence.\n"
        "Format: [Chart]: [Title] — key values and trend."
    ),
    "diagram": (
        "This is a diagram/flowchart from a compliance document.\n"
        "1. List all nodes/boxes and their connections.\n"
        "2. Describe the flow direction and decision points.\n"
        "Format: [Diagram]: [Title] — nodes → connections → outcome."
    ),
    "table": (
        "This is a table image from a financial document.\n"
        "Reproduce the table in markdown format with exact values.\n"
        "Format: [Table]: markdown table with headers and rows."
    ),
    "default": (
        "Describe this image from a financial regulatory document.\n"
        "Extract all visible text, numbers, and structural information.\n"
        "Format: [Image]: concise factual description."
    ),
}


def describe_images(images: list[bytes], context_hint: str = "") -> list[str]:
    """Send each image to Haiku vision, return text descriptions."""
    descriptions = []
    for img_bytes in images:
        # First pass: classify image type
        classify_resp = bedrock.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [
                {"image": {"format": "png", "source": {"bytes": img_bytes}}},
                {"text": "Classify: is this a chart, diagram, table, or other? One word."},
            ]}],
            inferenceConfig={"temperature": 0, "maxTokens": 10},
        )
        img_type = (
            classify_resp["output"]["message"]["content"][0]["text"].strip().lower()
        )
        prompt = VISION_PROMPTS.get(img_type, VISION_PROMPTS["default"])
        if context_hint:
            prompt += f"\n\nContext: this appears near text about: {context_hint[:200]}"
        # Second pass: describe with type-specific prompt
        resp = bedrock.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [
                {"image": {"format": "png", "source": {"bytes": img_bytes}}},
                {"text": prompt},
            ]}],
            inferenceConfig={"temperature": 0, "maxTokens": 512},
        )
        descriptions.append(resp["output"]["message"]["content"][0]["text"])
    return descriptions
