"""Tests for data models."""

import pytest
from src.financial_docs.common.models import (
    DocumentClassification,
    ExtractionResult,
    ProcessingStatus,
    ConfidenceLevel,
)


class TestDocumentClassification:
    """Tests for DocumentClassification model."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        classification = DocumentClassification(
            promissory_note_page=5,
            closing_disclosure_page=42,
            form_1003_page=87,
            confidence=ConfidenceLevel.HIGH,
            total_pages_analyzed=150,
        )

        result = classification.to_dict()

        assert result["promissoryNote"] == 5
        assert result["closingDisclosure"] == 42
        assert result["form1003"] == 87
        assert result["confidence"] == "high"
        assert result["totalPagesAnalyzed"] == 150

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "promissoryNote": 5,
            "closingDisclosure": 42,
            "form1003": 87,
            "confidence": "high",
            "totalPagesAnalyzed": 150,
        }

        classification = DocumentClassification.from_dict(data)

        assert classification.promissory_note_page == 5
        assert classification.closing_disclosure_page == 42
        assert classification.form_1003_page == 87
        assert classification.confidence == ConfidenceLevel.HIGH
        assert classification.total_pages_analyzed == 150

    def test_from_dict_with_nulls(self):
        """Test creation from dictionary with null values."""
        data = {
            "promissoryNote": None,
            "closingDisclosure": 42,
            "form1003": None,
            "confidence": "medium",
        }

        classification = DocumentClassification.from_dict(data)

        assert classification.promissory_note_page is None
        assert classification.closing_disclosure_page == 42
        assert classification.form_1003_page is None
        assert classification.confidence == ConfidenceLevel.MEDIUM


class TestExtractionResult:
    """Tests for ExtractionResult model."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ExtractionResult(
            document_id="test-123",
            extraction_type="QUERIES",
            page_number=5,
            status=ProcessingStatus.EXTRACTED,
            results={"interest_rate": "5.5%"},
        )

        data = result.to_dict()

        assert data["documentId"] == "test-123"
        assert data["extractionType"] == "QUERIES"
        assert data["pageNumber"] == 5
        assert data["status"] == "EXTRACTED"
        assert data["results"]["interest_rate"] == "5.5%"

    def test_skipped_status(self):
        """Test extraction result with skipped status."""
        result = ExtractionResult(
            document_id="test-123",
            extraction_type="QUERIES",
            page_number=None,
            status=ProcessingStatus.SKIPPED,
            reason="Document type not found",
        )

        data = result.to_dict()

        assert data["status"] == "SKIPPED"
        assert data["pageNumber"] is None
        assert data["reason"] == "Document type not found"
