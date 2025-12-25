"""Custom exceptions for Financial Documents Processing."""


class DocumentProcessingError(Exception):
    """Base exception for document processing errors."""

    def __init__(self, message: str, document_id: str | None = None, cause: Exception | None = None):
        self.message = message
        self.document_id = document_id
        self.cause = cause
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "documentId": self.document_id,
            "cause": str(self.cause) if self.cause else None,
        }


class ClassificationError(DocumentProcessingError):
    """Error during document classification."""
    pass


class ExtractionError(DocumentProcessingError):
    """Error during Textract extraction."""

    def __init__(
        self,
        message: str,
        document_id: str | None = None,
        page_number: int | None = None,
        extraction_type: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, document_id, cause)
        self.page_number = page_number
        self.extraction_type = extraction_type

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = super().to_dict()
        result.update({
            "pageNumber": self.page_number,
            "extractionType": self.extraction_type,
        })
        return result


class NormalizationError(DocumentProcessingError):
    """Error during data normalization."""
    pass


class StorageError(DocumentProcessingError):
    """Error during storage operations."""

    def __init__(
        self,
        message: str,
        document_id: str | None = None,
        storage_type: str | None = None,  # "s3" or "dynamodb"
        cause: Exception | None = None,
    ):
        super().__init__(message, document_id, cause)
        self.storage_type = storage_type


class ValidationError(DocumentProcessingError):
    """Error during data validation."""

    def __init__(
        self,
        message: str,
        document_id: str | None = None,
        field_name: str | None = None,
        expected_value: str | None = None,
        actual_value: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, document_id, cause)
        self.field_name = field_name
        self.expected_value = expected_value
        self.actual_value = actual_value
