"""Extract requirements from parsed docs via Bedrock Haiku 4.5."""
from __future__ import annotations

import json
import os
import re
import uuid
from decimal import Decimal

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
        "You are a compliance analyst extracting testable requirements from "
        "a regulatory or policy document.\n\n"
        "EXTRACTION PRINCIPLES:\n"
        "- Extract EVERY distinct obligation, rule, threshold, or condition\n"
        "- Include quantitative requirements (ratios, percentages, limits)\n"
        "- Include procedural requirements (must file, must notify, must maintain)\n"
        "- Include definitional requirements (what constitutes compliance)\n"
        "- For each requirement, provide a clear evaluationHint that describes "
        "what to look for in a target document to verify compliance\n"
        "- Category should reflect the domain (e.g., 'Financial Covenants', "
        "'Insurance', 'Reporting', 'Collateral', 'Governance')\n\n"
        "DOCUMENT:\n" + content.text[:120_000] + "\n\n"
        "For each requirement return a JSON object with:\n"
        '- "text": the requirement statement\n'
        '- "category": domain category\n'
        '- "sourceReference": section/page reference in the source document\n'
        '- "evaluationHint": what to look for when evaluating a target document\n\n'
        "Return a JSON array only, no other text."
    )


def extract_requirements(content: ParsedContent, source_document: str = "") -> list[dict]:
    """Call Bedrock to extract requirements, return structured list."""
    resp = bedrock_client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": build_extraction_prompt(content)}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 16384},
    )
    raw = resp["output"]["message"]["content"][0]["text"].strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"```$", "", raw.strip())
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        # LLM may prepend/append text around JSON — find first [ or { anywhere
        start_idx = raw.find("[")
        if start_idx < 0:
            start_idx = raw.find("{")
        if start_idx >= 0:
            bracket = raw[start_idx]
            close = "]" if bracket == "[" else "}"
            depth, end = 0, 0
            for i in range(start_idx, len(raw)):
                if raw[i] == bracket:
                    depth += 1
                elif raw[i] == close:
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end > 0:
                items = json.loads(raw[start_idx:end])
                # If we got a single object, wrap in list
                if isinstance(items, dict):
                    items = [items]
            else:
                # JSON likely truncated (maxTokens hit) — salvage complete objects
                # Find all complete {...} objects within a truncated array
                salvaged = []
                obj_depth, obj_start = 0, -1
                for i in range(start_idx, len(raw)):
                    if raw[i] == "{":
                        if obj_depth == 0:
                            obj_start = i
                        obj_depth += 1
                    elif raw[i] == "}":
                        obj_depth -= 1
                        if obj_depth == 0 and obj_start >= 0:
                            try:
                                salvaged.append(json.loads(raw[obj_start:i + 1]))
                            except json.JSONDecodeError:
                                pass
                            obj_start = -1
                if salvaged:
                    print(f"[Ingest] Salvaged {len(salvaged)} complete objects from truncated JSON")
                    items = salvaged
                else:
                    print(f"[Ingest] Could not salvage any objects from LLM response (first 500 chars): {raw[:500]}")
                    raise ValueError("Failed to parse LLM response as JSON array")
        else:
            print(f"[Ingest] No JSON found in LLM response (first 500 chars): {raw[:500]}")
            raise ValueError("Failed to parse LLM response as JSON array")
    return [
        {
            "requirementId": f"req-{uuid.uuid4().hex[:8]}",
            "text": it["text"],
            "category": it.get("category", "General"),
            "sourceReference": it.get("sourceReference", ""),
            "evaluationHint": it.get("evaluationHint", ""),
            "sourceDocument": source_document,
            "criticality": "should-have",
            "confidenceThreshold": Decimal("0.8"),
            "status": "active",
        }
        for it in items
    ]


def deduplicate_requirements(reqs: list[dict]) -> list[dict]:
    """Use LLM to deduplicate overlapping requirements from multiple documents.

    When multiple reference documents are ingested, they may express the same
    requirement in different words. This function sends all requirements to
    the LLM to identify and merge duplicates.
    """
    if len(reqs) <= 5:
        return reqs  # Too few to have meaningful duplicates

    req_texts = "\n".join(
        f"{i + 1}. [{r['requirementId']}] {r['text']} (category: {r['category']})"
        for i, r in enumerate(reqs)
    )
    prompt = (
        "Review these compliance requirements extracted from multiple documents. "
        "Identify duplicates or near-duplicates (same obligation expressed differently).\n\n"
        f"REQUIREMENTS:\n{req_texts}\n\n"
        "Return a JSON array of requirement IDs to REMOVE (the duplicates). "
        "Keep the most comprehensive version of each duplicate pair. "
        "Only remove true duplicates — requirements that cover the SAME obligation. "
        "Similar but distinct requirements should both be kept.\n\n"
        "Return JSON array of IDs to remove, e.g.: [\"req-abc123\", \"req-def456\"]\n"
        "If no duplicates found, return an empty array: []"
    )
    try:
        resp = bedrock_client.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 4096},
        )
        raw = resp["output"]["message"]["content"][0]["text"].strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"```$", "", raw.strip())
        ids_to_remove = set(json.loads(raw))
        if ids_to_remove:
            print(f"[Ingest] Removing {len(ids_to_remove)} duplicate requirements")
        return [r for r in reqs if r["requirementId"] not in ids_to_remove]
    except Exception as e:
        print(f"[Ingest] Deduplication failed (keeping all): {e}")
        return reqs
