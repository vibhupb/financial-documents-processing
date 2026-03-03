"""Extract requirements from parsed docs via Bedrock Haiku 4.5."""
from __future__ import annotations

import json
import os
import re
import uuid

import boto3
from botocore.config import Config

from parser import ParsedContent

bedrock_client = boto3.client(
    "bedrock-runtime", config=Config(max_pool_connections=10)
)
MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)


def build_extraction_prompt(content: ParsedContent) -> str:
    """Build the prompt for LLM requirement extraction."""
    return (
        "Extract all testable compliance requirements from this document.\n\n"
        "DOCUMENT:\n" + content.text[:80_000] + "\n\n"
        'For each requirement, return a JSON object with: '
        '"text", "category", "sourceReference", "evaluationHint".\n'
        "Return a JSON array only, no other text."
    )


def extract_requirements(content: ParsedContent) -> list[dict]:
    """Call Bedrock to extract requirements, return structured list."""
    resp = bedrock_client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": build_extraction_prompt(content)}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 4096},
    )
    raw = resp["output"]["message"]["content"][0]["text"].strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"```$", "", raw.strip())
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response: {e}") from e
    return [
        {
            "requirementId": f"req-{uuid.uuid4().hex[:8]}",
            "text": it["text"],
            "category": it.get("category", "General"),
            "sourceReference": it.get("sourceReference", ""),
            "evaluationHint": it.get("evaluationHint", ""),
            "criticality": "should-have",
            "confidenceThreshold": 0.8,
            "status": "active",
        }
        for it in items
    ]
