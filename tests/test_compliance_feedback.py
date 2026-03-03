"""Unit tests for few-shot feedback injection."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'compliance-evaluate'))

SAMPLE_FEEDBACK = [
    {
        "requirementId": "req-001",
        "originalVerdict": "FAIL",
        "correctedVerdict": "PASS",
        "reviewerNote": "APR was stated as 'annual interest rate' — treat as equivalent",
        "createdAt": "2026-03-01T10:00:00Z",
    },
    {
        "requirementId": "req-003",
        "originalVerdict": "PASS",
        "correctedVerdict": "PARTIAL",
        "reviewerNote": "Signature present but missing notarization",
        "createdAt": "2026-03-01T09:00:00Z",
    },
]


@patch("evaluate.feedback_table")
def test_corrections_block_includes_feedback(mock_fb_table):
    """Corrections block includes reviewer notes from feedback table."""
    mock_fb_table.query.return_value = {"Items": SAMPLE_FEEDBACK}
    from evaluate import _get_corrections_block
    block = _get_corrections_block("bl-1", [{"requirementId": "req-001"}])
    assert "PRIOR CORRECTIONS" in block
    assert "annual interest rate" in block
    assert "treat as equivalent" in block


@patch("evaluate.feedback_table")
def test_corrections_block_empty_when_no_feedback(mock_fb_table):
    """Corrections block is empty string when no feedback exists."""
    mock_fb_table.query.return_value = {"Items": []}
    from evaluate import _get_corrections_block
    block = _get_corrections_block("bl-1", [{"requirementId": "req-001"}])
    assert block == ""


@patch("evaluate.feedback_table")
def test_corrections_limited_to_max(mock_fb_table):
    """Corrections block contains at most MAX_CORRECTIONS entries."""
    items = [
        {
            "requirementId": f"req-{i:03d}",
            "originalVerdict": "FAIL",
            "correctedVerdict": "PASS",
            "reviewerNote": f"Note {i}",
            "createdAt": f"2026-03-01T{i:02d}:00:00Z",
        }
        for i in range(10)
    ]
    mock_fb_table.query.return_value = {"Items": items}
    from evaluate import _get_corrections_block
    block = _get_corrections_block("bl-1", [{"requirementId": "req-001"}])
    assert block.count("was marked") <= 5
