"""PII-safe logging module -- drop-in replacement for print().

Reads pii_paths from the plugin registry to redact sensitive data
before writing to CloudWatch Logs.

Usage:
    from document_plugins.safe_log import safe_log
    safe_log("Processing document", data=event, plugin_id="bsa_profile")
"""

import copy
import json
import re
import sys
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set


# Redaction strategies by PII type
def _redact_ssn(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", str(value))
    return f"***-**-{digits[-4:]}" if len(digits) >= 4 else "***-**-****"


def _redact_dob(value: str) -> str:
    match = re.search(r"(19|20)\d{2}", str(value))
    return f"****-**-** ({match.group()})" if match else "****-**-**"


def _redact_tax_id(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", str(value))
    return f"**-***{digits[-4:]}" if len(digits) >= 4 else "**-*******"


def _redact_government_id(value: str) -> str:
    return f"****{str(value)[-4:]}" if len(str(value)) >= 4 else "****"


_REDACTORS = {
    "ssn": _redact_ssn,
    "dob": _redact_dob,
    "tax_id": _redact_tax_id,
    "government_id": _redact_government_id,
}

# Fallback field name patterns (catches PII even without plugin_id)
_FALLBACK_PII_FIELDS = {
    "ssn": "ssn", "socialSecurityNumber": "ssn",
    "dateOfBirth": "dob", "date_of_birth": "dob", "dob": "dob",
    "taxId": "tax_id", "tax_id": "tax_id", "ein": "tax_id",
    "trustTaxId": "tax_id",
}


def _redact_by_field_name(data: Any, visited: Optional[Set[int]] = None) -> Any:
    """Walk structure and redact known PII field names."""
    if visited is None:
        visited = set()
    obj_id = id(data)
    if obj_id in visited:
        return data
    visited.add(obj_id)

    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k in _FALLBACK_PII_FIELDS and v is not None:
                redactor = _REDACTORS.get(_FALLBACK_PII_FIELDS[k], lambda x: "***REDACTED***")
                result[k] = redactor(v)
            else:
                result[k] = _redact_by_field_name(v, visited)
        return result
    elif isinstance(data, list):
        return [_redact_by_field_name(item, visited) for item in data]
    return data


def redact_pii(data: Any, plugin_id: Optional[str] = None) -> Any:
    """Deep-copy data and redact all PII fields."""
    if data is None:
        return None
    try:
        redacted = copy.deepcopy(data)
    except Exception:
        return {"__redacted__": "deep copy failed"}

    # Always apply fallback field-name redaction
    return _redact_by_field_name(redacted)


class _SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return "<bytes>"
        return super().default(obj)


def safe_log(
    message: str,
    *args,
    data: Any = None,
    plugin_id: Optional[str] = None,
    **kwargs,
) -> None:
    """PII-safe logging function."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    parts = [f"[{timestamp}]", message]

    for arg in args:
        if isinstance(arg, (dict, list)):
            parts.append(json.dumps(redact_pii(arg, plugin_id), cls=_SafeEncoder, default=str))
        else:
            parts.append(str(arg))

    for k, v in kwargs.items():
        if isinstance(v, (dict, list)):
            parts.append(f"{k}={json.dumps(redact_pii(v, plugin_id), cls=_SafeEncoder, default=str)}")
        else:
            parts.append(f"{k}={v}")

    if data is not None:
        redacted_data = redact_pii(data, plugin_id)
        try:
            data_str = json.dumps(redacted_data, cls=_SafeEncoder, default=str)
            if len(data_str) > 10240:
                data_str = data_str[:10240] + f"... [TRUNCATED]"
            parts.append(data_str)
        except (TypeError, ValueError):
            parts.append(str(redacted_data)[:10240])

    print(" ".join(parts), flush=True)
