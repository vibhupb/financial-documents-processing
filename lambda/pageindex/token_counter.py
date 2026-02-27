"""Approximate token counting for Claude models.

Replaces tiktoken (OpenAI-specific) with a character-based approximation.
Claude tokenizes at roughly 4 characters per token for English text.
"""

from __future__ import annotations


def count_tokens(text: str) -> int:
    """Approximate token count for Claude models (~4 chars/token)."""
    if not text:
        return 0
    return len(text) // 4


def count_tokens_messages(messages: list[dict]) -> int:
    """Approximate token count for a list of chat messages."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += count_tokens(block.get("text", ""))
        elif isinstance(content, str):
            total += count_tokens(content)
    return total
