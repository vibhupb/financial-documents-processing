"""Unit tests for compliance evaluation Lambda."""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'compliance-evaluate'))


@pytest.fixture
def mock_tree():
    return {
        "structure": [
            {"title": "Section 3 — Rates", "page_range": [14, 16], "node_id": "n1", "nodes": []},
            {"title": "Section 5 — Execution", "page_range": [25, 27], "node_id": "n2", "nodes": []},
        ],
        "total_pages": 30,
    }


@pytest.fixture
def sample_baseline():
    return {
        "baselineId": "bl-1",
        "version": 1,
        "requirements": [
            {
                "requirementId": "req-001",
                "text": "Must specify APR",
                "category": "Rates",
                "criticality": "must-have",
                "evaluationHint": "Look for APR, annual percentage rate",
            },
            {
                "requirementId": "req-002",
                "text": "Must include signature page",
                "category": "Execution",
                "criticality": "must-have",
                "evaluationHint": "Look for signature lines",
            },
        ],
    }


@patch("evaluate.feedback_table")
@patch("evaluate.bedrock_client")
@patch("evaluate.baselines_table")
def test_evaluate_batches_and_scores(mock_bl_table, mock_bedrock, mock_fb_table,
                                      mock_tree, sample_baseline):
    """evaluate_document finds baselines, batches requirements, returns scored report."""
    mock_bl_table.query.return_value = {"Items": [sample_baseline]}
    mock_fb_table.query.return_value = {"Items": []}

    # Mock both LLM calls: tree navigation returns page list, evaluation returns verdicts
    mock_bedrock.converse.side_effect = [
        # Tree navigation response
        {"output": {"message": {"content": [{"text": "[14, 15, 25, 26]"}]}},
         "usage": {"inputTokens": 500, "outputTokens": 50}},
        # Evaluation response
        {"output": {"message": {"content": [{"text": json.dumps([
            {"requirementId": "req-001", "verdict": "PASS", "confidence": 0.92,
             "evidence": "The APR shall be 6.75%", "evidenceCharStart": 100,
             "evidenceCharEnd": 123, "pageReferences": [15]},
            {"requirementId": "req-002", "verdict": "FAIL", "confidence": 0.85,
             "evidence": "", "evidenceCharStart": None, "evidenceCharEnd": None,
             "pageReferences": []},
        ])}]}},
         "usage": {"inputTokens": 5000, "outputTokens": 1000}},
    ]

    from evaluate import evaluate_document
    result = evaluate_document("doc-123", "loan_package", mock_tree, b"fake pdf")

    assert result["overallScore"] == 50  # 1 PASS out of 2
    assert len(result["results"]) == 2
    assert result["status"] == "completed"
    assert result["baselineId"] == "bl-1"
    assert result["results"][0]["verdict"] == "PASS"
    assert result["results"][1]["verdict"] == "FAIL"


@patch("evaluate.feedback_table")
@patch("evaluate.bedrock_client")
@patch("evaluate.baselines_table")
def test_no_baselines_returns_immediately(mock_bl_table, mock_bedrock, mock_fb_table, mock_tree):
    """evaluate_document returns no_baselines status when no baselines match."""
    mock_bl_table.query.return_value = {"Items": []}

    from evaluate import evaluate_document
    result = evaluate_document("doc-123", "unknown_type", mock_tree, b"fake pdf")

    assert result["status"] == "no_baselines"
    assert result["overallScore"] == -1
    assert result["results"] == []
    mock_bedrock.converse.assert_not_called()
