"""Tests for compliance-ingest LLM requirement extractor."""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'compliance-ingest'))
from extractor import extract_requirements, build_extraction_prompt
from parser import ParsedContent

_rv = lambda t: {
    "output": {"message": {"content": [{"text": t}]}},
    "usage": {"inputTokens": 1, "outputTokens": 1},
}


def test_prompt_contains_document_text():
    """build_extraction_prompt includes the document text."""
    content = ParsedContent(text="Must specify APR.")
    prompt = build_extraction_prompt(content)
    assert "APR" in prompt
    assert "testable compliance requirements" in prompt.lower() or "requirements" in prompt.lower()


@patch("extractor.bedrock_client")
def test_parse_requirements(mock_bedrock):
    """extract_requirements parses LLM JSON response into requirement dicts."""
    mock_bedrock.converse.return_value = _rv(
        json.dumps([{
            "text": "Must specify APR",
            "category": "Rates",
            "sourceReference": "Section 3",
            "evaluationHint": "Look for APR",
        }])
    )
    result = extract_requirements(ParsedContent(text="doc content"))
    assert len(result) == 1
    assert "requirementId" in result[0]
    assert result[0]["text"] == "Must specify APR"
    assert result[0]["criticality"] == "should-have"
    assert result[0]["confidenceThreshold"] == 0.8
    assert result[0]["status"] == "active"


@patch("extractor.bedrock_client")
def test_empty_requirements(mock_bedrock):
    """extract_requirements returns empty list for empty LLM response."""
    mock_bedrock.converse.return_value = _rv("[]")
    result = extract_requirements(ParsedContent(text="x"))
    assert result == []


@patch("extractor.bedrock_client")
def test_malformed_json_raises(mock_bedrock):
    """extract_requirements raises ValueError for malformed LLM response."""
    mock_bedrock.converse.return_value = _rv("this is not json")
    with pytest.raises(ValueError, match="Failed to parse"):
        extract_requirements(ParsedContent(text="x"))
