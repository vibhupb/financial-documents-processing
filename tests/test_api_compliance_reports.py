"""Unit tests for compliance report + reviewer override API."""
import json
import os
import sys

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Add the lambda/api directory to sys.path for handler import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda", "api"))

import handler


@patch.object(handler, "dynamodb")
def test_get_compliance_reports(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.query.return_value = {
        "Items": [
            {
                "reportId": "rpt-1",
                "documentId": "doc-1",
                "overallScore": 85,
                "status": "completed",
                "results": [],
            }
        ]
    }
    result = handler.get_compliance_reports("doc-1")
    assert len(result["reports"]) == 1
    assert result["reports"][0]["overallScore"] == 85


@patch.object(handler, "dynamodb")
def test_get_compliance_report_single(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {
        "Item": {
            "reportId": "rpt-1",
            "documentId": "doc-1",
            "overallScore": 85,
            "status": "completed",
            "results": [],
        }
    }
    result = handler.get_compliance_report("doc-1", "rpt-1")
    assert result["report"]["reportId"] == "rpt-1"


@patch.object(handler, "dynamodb")
def test_get_compliance_report_not_found(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {}
    result = handler.get_compliance_report("doc-1", "rpt-missing")
    assert "error" in result


@patch.object(handler, "dynamodb")
def test_submit_reviewer_override(mock_dynamo):
    reports_tbl = MagicMock()
    feedback_tbl = MagicMock()

    def table_router(name):
        if "reports" in name:
            return reports_tbl
        return feedback_tbl

    mock_dynamo.Table.side_effect = table_router
    reports_tbl.get_item.return_value = {
        "Item": {
            "reportId": "rpt-1",
            "documentId": "doc-1",
            "baselineId": "bl-1",
            "results": [
                {
                    "requirementId": "req-001",
                    "verdict": "FAIL",
                    "confidence": 0.9,
                }
            ],
        }
    }
    result = handler.submit_compliance_review(
        "doc-1",
        "rpt-1",
        {
            "overrides": [
                {
                    "requirementId": "req-001",
                    "correctedVerdict": "PASS",
                    "reviewerNote": "Rate was stated differently",
                }
            ]
        },
        "reviewer-1",
    )
    assert result["status"] == "reviewed"
    assert result["overrideCount"] == 1
    feedback_tbl.put_item.assert_called_once()


@patch.object(handler, "dynamodb")
def test_submit_review_report_not_found(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {}
    result = handler.submit_compliance_review(
        "doc-1", "rpt-missing", {"overrides": []}, "user-1"
    )
    assert "error" in result
