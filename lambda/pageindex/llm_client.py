"""Bedrock converse wrapper for PageIndex tree building.

Replaces PageIndex's OpenAI ChatGPT_API functions with AWS Bedrock equivalents.
Three call patterns mirroring the original:
  - bedrock_converse()              → sync single response
  - bedrock_converse_with_stop()    → sync with finish reason (for long generation)
  - bedrock_converse_threaded()     → concurrent calls via ThreadPoolExecutor
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import boto3

bedrock = boto3.client("bedrock-runtime")
DEFAULT_MODEL = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
MAX_RETRIES = 5
RETRY_BACKOFF = 1  # seconds


def _build_messages(
    prompt: str, chat_history: list[dict] | None = None
) -> list[dict]:
    """Build Bedrock converse message list."""
    if chat_history:
        messages = list(chat_history)
        messages.append({"role": "user", "content": [{"text": prompt}]})
        return messages
    return [{"role": "user", "content": [{"text": prompt}]}]


def bedrock_converse(
    prompt: str,
    model: str = "",
    chat_history: list[dict] | None = None,
    max_tokens: int = 4096,
) -> str:
    """Synchronous single-response LLM call via Bedrock converse API.

    Equivalent to PageIndex's ChatGPT_API().
    """
    model = model or DEFAULT_MODEL
    messages = _build_messages(prompt, chat_history)

    for attempt in range(MAX_RETRIES):
        try:
            response = bedrock.converse(
                modelId=model,
                messages=messages,
                inferenceConfig={"temperature": 0, "maxTokens": max_tokens},
            )
            return response["output"]["message"]["content"][0]["text"]
        except Exception as e:
            print(f"[LLM] Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF * (attempt + 1))
    return "Error"


def bedrock_converse_with_stop(
    prompt: str,
    model: str = "",
    chat_history: list[dict] | None = None,
    max_tokens: int = 4096,
) -> tuple[str, str]:
    """Synchronous call that returns (content, finish_status).

    finish_status is "finished" or "max_output_reached".
    Equivalent to PageIndex's ChatGPT_API_with_finish_reason().
    """
    model = model or DEFAULT_MODEL
    messages = _build_messages(prompt, chat_history)

    for attempt in range(MAX_RETRIES):
        try:
            response = bedrock.converse(
                modelId=model,
                messages=messages,
                inferenceConfig={"temperature": 0, "maxTokens": max_tokens},
            )
            content = response["output"]["message"]["content"][0]["text"]
            stop_reason = response.get("stopReason", "end_turn")
            finished = (
                "max_output_reached"
                if stop_reason == "max_tokens"
                else "finished"
            )
            return content, finished
        except Exception as e:
            print(f"[LLM] Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF * (attempt + 1))
    return "Error", "finished"


def bedrock_converse_threaded(
    prompts: list[str],
    model: str = "",
    max_workers: int = 10,
    max_tokens: int = 4096,
) -> list[str]:
    """Run multiple LLM calls concurrently using ThreadPoolExecutor.

    Equivalent to PageIndex's async ChatGPT_API_async() pattern
    using asyncio.gather(), but adapted for sync Bedrock SDK.
    """
    model = model or DEFAULT_MODEL

    def _call(prompt: str) -> str:
        return bedrock_converse(prompt, model=model, max_tokens=max_tokens)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(_call, prompts))
