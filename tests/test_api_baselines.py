"""Unit tests for baseline CRUD API routes."""
import importlib
import json
import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


def _load_api_handler():
    """Load the API handler module, ensuring we get the right one even if
    another handler module is already cached in sys.modules."""
    api_dir = os.path.join(os.path.dirname(__file__), "..", "lambda", "api")
    api_dir = os.path.abspath(api_dir)
    # Remove any previously cached 'handler' from a different Lambda
    if "handler" in sys.modules:
        prev = sys.modules.pop("handler")
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)
    import handler
    return handler


@patch.dict(os.environ, {"AWS_REGION": "us-west-2"}, clear=False)
@patch("boto3.resource")
@patch("boto3.client")
def _get_handler(mock_client, mock_resource):
    """Import handler with boto3 mocked so module-level init succeeds."""
    return _load_api_handler()


# Load once at module level with mocked boto3
handler = _get_handler()


@patch.object(handler, "dynamodb")
def test_list_baselines(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.scan.return_value = {
        "Items": [
            {"baselineId": "bl-1", "name": "OCC Reqs", "status": "published"}
        ]
    }

    result = handler.list_baselines({"status": "published"})
    assert len(result["baselines"]) == 1
    assert result["baselines"][0]["status"] == "published"


@patch.object(handler, "dynamodb")
def test_list_baselines_no_filter(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.scan.return_value = {
        "Items": [
            {"baselineId": "bl-1", "name": "OCC Reqs", "status": "published"},
            {"baselineId": "bl-2", "name": "Draft BL", "status": "draft"},
        ]
    }

    result = handler.list_baselines({})
    assert len(result["baselines"]) == 2


@patch.object(handler, "dynamodb")
def test_create_baseline(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table

    result = handler.create_baseline(
        {"name": "Test", "description": "Desc", "pluginIds": ["loan_package"]},
        "user-1",
    )
    assert "baselineId" in result
    assert result["name"] == "Test"
    assert result["status"] == "draft"
    assert result["version"] == 0
    assert result["createdBy"] == "user-1"
    table.put_item.assert_called_once()


@patch.object(handler, "dynamodb")
def test_get_baseline_found(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {
        "Item": {"baselineId": "bl-1", "name": "Test BL"}
    }

    result = handler.get_baseline("bl-1")
    assert result["baseline"]["baselineId"] == "bl-1"


@patch.object(handler, "dynamodb")
def test_get_baseline_not_found(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {}

    result = handler.get_baseline("bl-missing")
    assert "error" in result


@patch.object(handler, "dynamodb")
def test_update_baseline(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table

    result = handler.update_baseline("bl-1", {"name": "Updated Name"})
    assert result["updated"] is True
    table.update_item.assert_called_once()


@patch.object(handler, "dynamodb")
def test_archive_baseline(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table

    result = handler.archive_baseline("bl-1")
    assert result["status"] == "archived"
    table.update_item.assert_called_once()


@patch.object(handler, "dynamodb")
def test_publish_baseline(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {
        "Item": {
            "baselineId": "bl-1",
            "status": "draft",
            "version": 1,
            "requirements": [{"requirementId": "r1"}],
        }
    }

    result = handler.publish_baseline("bl-1")
    assert result["status"] == "published"
    assert result["version"] == 2


@patch.object(handler, "dynamodb")
def test_publish_baseline_no_requirements(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {
        "Item": {
            "baselineId": "bl-1",
            "status": "draft",
            "version": 1,
            "requirements": [],
        }
    }

    result = handler.publish_baseline("bl-1")
    assert "error" in result
    assert "no requirements" in result["error"].lower()


@patch.object(handler, "dynamodb")
def test_publish_baseline_not_found(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {}

    result = handler.publish_baseline("bl-missing")
    assert "error" in result


@patch.object(handler, "dynamodb")
def test_add_requirement(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table

    result = handler.add_requirement(
        "bl-1",
        {"text": "Must verify borrower identity", "category": "kyc", "criticality": "must-have"},
    )
    assert result["baselineId"] == "bl-1"
    assert "requirement" in result
    assert result["requirement"]["text"] == "Must verify borrower identity"
    assert result["requirement"]["category"] == "kyc"
    assert result["requirement"]["criticality"] == "must-have"
    table.update_item.assert_called_once()


@patch.object(handler, "dynamodb")
def test_update_requirement(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {
        "Item": {
            "baselineId": "bl-1",
            "requirements": [
                {"requirementId": "req-1", "text": "Old text", "category": "general"},
            ],
        }
    }

    result = handler.update_requirement("bl-1", "req-1", {"text": "Updated text"})
    assert result["updated"] is True
    table.update_item.assert_called_once()


@patch.object(handler, "dynamodb")
def test_update_requirement_not_found(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {
        "Item": {
            "baselineId": "bl-1",
            "requirements": [
                {"requirementId": "req-1", "text": "Old text"},
            ],
        }
    }

    result = handler.update_requirement("bl-1", "req-missing", {"text": "Updated"})
    assert "error" in result


@patch.object(handler, "dynamodb")
def test_delete_requirement(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {
        "Item": {
            "baselineId": "bl-1",
            "requirements": [
                {"requirementId": "req-1", "text": "Keep this"},
                {"requirementId": "req-2", "text": "Delete this"},
            ],
        }
    }

    result = handler.delete_requirement("bl-1", "req-2")
    assert result["deleted"] is True
    # Verify the update_item was called with the filtered list
    call_kwargs = table.update_item.call_args[1]
    remaining_reqs = call_kwargs["ExpressionAttributeValues"][":r"]
    assert len(remaining_reqs) == 1
    assert remaining_reqs[0]["requirementId"] == "req-1"


@patch.object(handler, "dynamodb")
def test_delete_requirement_baseline_not_found(mock_dynamo):
    table = MagicMock()
    mock_dynamo.Table.return_value = table
    table.get_item.return_value = {}

    result = handler.delete_requirement("bl-missing", "req-1")
    assert "error" in result
