"""Field validation utilities for extracted document data.

This module provides validation functions to ensure extracted values
meet the requirements defined in extraction schemas.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from ..schemas.extraction_fields import ExtractionField, FieldType


@dataclass
class ValidationResult:
    """Result of field validation."""

    is_valid: bool
    value: Any  # Normalized/parsed value
    original_value: Any
    field_id: str
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "isValid": self.is_valid,
            "value": self.value,
            "originalValue": self.original_value,
            "fieldId": self.field_id,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_field(field: ExtractionField, value: Any) -> ValidationResult:
    """Validate an extracted value against its field definition.

    Args:
        field: Field definition with validation rules
        value: Extracted value to validate

    Returns:
        ValidationResult with parsed value and any errors/warnings
    """
    errors: list[str] = []
    warnings: list[str] = []
    normalized_value = value

    # Check required
    if field.required and (value is None or value == ""):
        errors.append(f"Required field '{field.name}' is missing")
        return ValidationResult(
            is_valid=False,
            value=None,
            original_value=value,
            field_id=field.id,
            errors=errors,
            warnings=warnings,
        )

    # Skip validation for None/empty optional fields
    if value is None or value == "":
        return ValidationResult(
            is_valid=True,
            value=None,
            original_value=value,
            field_id=field.id,
            errors=errors,
            warnings=warnings,
        )

    # Type-specific validation
    try:
        if field.field_type == FieldType.STRING:
            normalized_value = str(value).strip()

        elif field.field_type == FieldType.NUMBER:
            normalized_value = _parse_number(value)
            _validate_numeric_range(normalized_value, field, errors)

        elif field.field_type == FieldType.CURRENCY:
            normalized_value = _parse_currency(value)
            _validate_numeric_range(normalized_value, field, errors)

        elif field.field_type == FieldType.PERCENTAGE:
            normalized_value = _parse_percentage(value)
            _validate_numeric_range(normalized_value, field, errors)

        elif field.field_type == FieldType.DATE:
            normalized_value = _parse_date(value)

        elif field.field_type == FieldType.BOOLEAN:
            normalized_value = _parse_boolean(value)

        elif field.field_type == FieldType.ADDRESS:
            normalized_value = _normalize_address(value)

        elif field.field_type == FieldType.PHONE:
            normalized_value, is_valid = _validate_phone(value)
            if not is_valid:
                warnings.append(f"Phone number may be invalid: {value}")

        elif field.field_type == FieldType.EMAIL:
            normalized_value, is_valid = _validate_email(value)
            if not is_valid:
                errors.append(f"Invalid email format: {value}")

        elif field.field_type == FieldType.SSN:
            normalized_value, is_valid = _validate_ssn(value)
            if not is_valid:
                errors.append(f"Invalid SSN format: {value}")

        elif field.field_type == FieldType.EIN:
            normalized_value, is_valid = _validate_ein(value)
            if not is_valid:
                errors.append(f"Invalid EIN format: {value}")

        elif field.field_type == FieldType.ACCOUNT_NUMBER:
            normalized_value = str(value).strip()

    except (ValueError, InvalidOperation) as e:
        errors.append(f"Failed to parse {field.field_type.value}: {str(e)}")

    # Custom regex validation
    if field.validation_regex and normalized_value:
        if not re.match(field.validation_regex, str(normalized_value)):
            errors.append(f"Value does not match pattern: {field.validation_regex}")

    return ValidationResult(
        is_valid=len(errors) == 0,
        value=normalized_value,
        original_value=value,
        field_id=field.id,
        errors=errors,
        warnings=warnings,
    )


def validate_extraction_result(
    fields: list[ExtractionField],
    extracted_data: dict[str, Any],
) -> dict[str, ValidationResult]:
    """Validate all extracted fields against their definitions.

    Args:
        fields: List of field definitions
        extracted_data: Dictionary of field_id -> extracted_value

    Returns:
        Dictionary of field_id -> ValidationResult
    """
    results = {}

    for field in fields:
        value = extracted_data.get(field.id)
        results[field.id] = validate_field(field, value)

    return results


def _parse_number(value: Any) -> float:
    """Parse a numeric value."""
    if isinstance(value, (int, float)):
        return float(value)

    # Clean string value
    cleaned = str(value).strip()
    cleaned = cleaned.replace(",", "")  # Remove thousands separator
    cleaned = cleaned.replace(" ", "")

    return float(cleaned)


def _parse_currency(value: Any) -> float:
    """Parse a currency value, removing currency symbols."""
    if isinstance(value, (int, float)):
        return float(value)

    cleaned = str(value).strip()
    # Remove common currency symbols
    cleaned = re.sub(r"[$€£¥]", "", cleaned)
    cleaned = cleaned.replace(",", "")
    cleaned = cleaned.replace(" ", "")

    # Handle parentheses for negative (accounting format)
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]

    return float(cleaned)


def _parse_percentage(value: Any) -> float:
    """Parse a percentage value to decimal form."""
    if isinstance(value, (int, float)):
        # Assume already in correct form if small
        return float(value) if float(value) <= 1 else float(value) / 100

    cleaned = str(value).strip()
    cleaned = cleaned.replace("%", "")
    cleaned = cleaned.replace(" ", "")

    num = float(cleaned)

    # If > 1, assume it's like "6.5" meaning 6.5%
    # Return as percentage (6.5), not decimal (0.065)
    return num


def _parse_date(value: Any) -> str:
    """Parse and normalize a date to ISO format."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    date_str = str(value).strip()

    # Common date formats to try
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%y",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Return as-is if can't parse
    return date_str


def _parse_boolean(value: Any) -> bool:
    """Parse a boolean value."""
    if isinstance(value, bool):
        return value

    str_val = str(value).lower().strip()
    truthy = {"true", "yes", "y", "1", "x", "checked"}
    falsy = {"false", "no", "n", "0", "", "unchecked"}

    if str_val in truthy:
        return True
    if str_val in falsy:
        return False

    raise ValueError(f"Cannot parse boolean from: {value}")


def _normalize_address(value: Any) -> str:
    """Normalize an address string."""
    address = str(value).strip()

    # Normalize common abbreviations
    replacements = {
        " st.": " Street",
        " st,": " Street,",
        " ave.": " Avenue",
        " ave,": " Avenue,",
        " blvd.": " Boulevard",
        " blvd,": " Boulevard,",
        " dr.": " Drive",
        " dr,": " Drive,",
        " ln.": " Lane",
        " ln,": " Lane,",
        " rd.": " Road",
        " rd,": " Road,",
    }

    address_lower = address.lower()
    for abbrev, full in replacements.items():
        if abbrev in address_lower:
            idx = address_lower.find(abbrev)
            address = address[:idx] + full + address[idx + len(abbrev) :]
            address_lower = address.lower()

    return address


def _validate_phone(value: Any) -> tuple[str, bool]:
    """Validate and normalize a phone number."""
    phone = re.sub(r"[^\d+]", "", str(value))

    # Basic validation - should have 10+ digits
    digits = re.sub(r"\D", "", phone)
    is_valid = len(digits) >= 10

    # Format as (XXX) XXX-XXXX if US number
    if len(digits) == 10:
        phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == "1":
        phone = f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

    return phone, is_valid


def _validate_email(value: Any) -> tuple[str, bool]:
    """Validate an email address."""
    email = str(value).strip().lower()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    is_valid = bool(re.match(pattern, email))
    return email, is_valid


def _validate_ssn(value: Any) -> tuple[str, bool]:
    """Validate a Social Security Number."""
    ssn = re.sub(r"[^\d]", "", str(value))

    is_valid = len(ssn) == 9

    # Format as XXX-XX-XXXX (masked for display: ***-**-XXXX)
    if len(ssn) == 9:
        formatted = f"{ssn[:3]}-{ssn[3:5]}-{ssn[5:]}"
    else:
        formatted = str(value)

    return formatted, is_valid


def _validate_ein(value: Any) -> tuple[str, bool]:
    """Validate an Employer Identification Number."""
    ein = re.sub(r"[^\d]", "", str(value))

    is_valid = len(ein) == 9

    # Format as XX-XXXXXXX
    if len(ein) == 9:
        formatted = f"{ein[:2]}-{ein[2:]}"
    else:
        formatted = str(value)

    return formatted, is_valid


def _validate_numeric_range(
    value: float,
    field: ExtractionField,
    errors: list[str],
) -> None:
    """Check numeric value against min/max constraints."""
    if field.min_value is not None and value < field.min_value:
        errors.append(f"Value {value} is below minimum {field.min_value}")

    if field.max_value is not None and value > field.max_value:
        errors.append(f"Value {value} is above maximum {field.max_value}")
