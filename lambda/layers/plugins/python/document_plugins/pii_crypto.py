"""PII field-level encryption using AWS KMS envelope encryption.

Envelope encryption: 1 KMS API call per record (not per field).
  ENCRYPT: KMS GenerateDataKey -> AES-256-GCM encrypt each PII field
  DECRYPT: KMS Decrypt -> AES-256-GCM decrypt each PII field

Stores encrypted envelope as _pii_envelope key in DynamoDB records.
"""

import base64
import copy
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import boto3

# Configuration
KMS_KEY_ID = os.environ.get("PII_KMS_KEY_ID", "")
_ENVELOPE_KEY = "_pii_envelope"
_ENVELOPE_VERSION = 1
_kms_client = None


def _get_kms_client():
    global _kms_client
    if _kms_client is None:
        _kms_client = boto3.client("kms")
    return _kms_client


def _resolve_json_path(data: Any, path_parts: List[str]) -> List[Tuple[dict, str]]:
    """Walk a dotted path with [*] wildcards, returning (parent, key) pairs."""
    if not path_parts or data is None:
        return []
    current = path_parts[0]
    remaining = path_parts[1:]

    if current.endswith("[*]"):
        field = current[:-3]
        arr = data.get(field) if isinstance(data, dict) else None
        if not isinstance(arr, list):
            return []
        if not remaining:
            return [(data, field)]
        results = []
        for element in arr:
            results.extend(_resolve_json_path(element, remaining))
        return results

    if not remaining:
        if isinstance(data, dict) and current in data:
            return [(data, current)]
        return []

    if isinstance(data, dict) and current in data:
        return _resolve_json_path(data[current], remaining)
    return []


def _get_pii_paths(plugin_id: str) -> List[dict]:
    try:
        from document_plugins.registry import get_plugin
        config = get_plugin(plugin_id)
        return config.get("pii_paths", [])
    except (KeyError, ImportError):
        return []


def is_encrypted(record: dict) -> bool:
    """Check if a DynamoDB record has PII envelope encryption."""
    return _ENVELOPE_KEY in record


def encrypt_pii_fields(record: dict, plugin_id: str) -> dict:
    """Encrypt all PII fields using KMS envelope encryption.

    Returns new dict with PII replaced by [ENCRYPTED] sentinels
    and _pii_envelope containing encrypted values.
    """
    kms_key_id = KMS_KEY_ID
    if not kms_key_id:
        return record  # No KMS key configured, skip encryption

    pii_paths = _get_pii_paths(plugin_id)
    if not pii_paths or is_encrypted(record):
        return record

    result = copy.deepcopy(record)
    extracted_data = result.get("extractedData", {})
    if not extracted_data:
        return result

    # Generate one DEK for all fields
    kms = _get_kms_client()
    response = kms.generate_data_key(KeyId=kms_key_id, KeySpec="AES_256")
    plaintext_dek = response["Plaintext"]
    encrypted_dek = response["CiphertextBlob"]

    encrypted_fields: Dict[str, dict] = {}

    try:
        # Try to import cryptography for AES-GCM
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(plaintext_dek)

        for marker in pii_paths:
            json_path = marker["json_path"]
            targets = _resolve_json_path(extracted_data, json_path.split("."))
            for parent, key in targets:
                value = parent.get(key)
                if value is None or value == "[ENCRYPTED]":
                    continue
                # Encrypt
                nonce = os.urandom(12)
                ct_and_tag = aesgcm.encrypt(nonce, str(value).encode(), None)
                encrypted_fields[json_path] = {
                    "ciphertext": base64.b64encode(ct_and_tag[:-16]).decode(),
                    "nonce": base64.b64encode(nonce).decode(),
                    "tag": base64.b64encode(ct_and_tag[-16:]).decode(),
                }
                parent[key] = "[ENCRYPTED]"
    except ImportError:
        print("WARNING: cryptography package not available, storing PII unencrypted")
        return record
    finally:
        plaintext_dek = b"\x00" * len(plaintext_dek)

    if encrypted_fields:
        result["extractedData"] = extracted_data
        result[_ENVELOPE_KEY] = {
            "version": _ENVELOPE_VERSION,
            "kms_key_id": kms_key_id,
            "encrypted_dek": base64.b64encode(encrypted_dek).decode(),
            "fields": encrypted_fields,
        }

    return result


def decrypt_pii_fields(record: dict, plugin_id: str) -> dict:
    """Decrypt all PII fields using KMS envelope decryption."""
    if not is_encrypted(record):
        return record

    result = copy.deepcopy(record)
    envelope = result.pop(_ENVELOPE_KEY)
    encrypted_dek = base64.b64decode(envelope["encrypted_dek"])
    fields = envelope.get("fields", {})
    if not fields:
        return result

    kms = _get_kms_client()
    response = kms.decrypt(CiphertextBlob=encrypted_dek)
    plaintext_dek = response["Plaintext"]
    extracted_data = result.get("extractedData", {})

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(plaintext_dek)

        for storage_key, enc_field in fields.items():
            nonce = base64.b64decode(enc_field["nonce"])
            ciphertext = base64.b64decode(enc_field["ciphertext"])
            tag = base64.b64decode(enc_field["tag"])
            decrypted = aesgcm.decrypt(nonce, ciphertext + tag, None).decode()

            # Set value back at path
            parts = storage_key.replace("[*]", ".[*]").split(".")
            _set_nested(extracted_data, parts, decrypted)
    except ImportError:
        print("WARNING: cryptography package not available for decryption")
    finally:
        plaintext_dek = b"\x00" * len(plaintext_dek)

    result["extractedData"] = extracted_data
    return result


def _set_nested(data: Any, parts: List[str], value: str) -> None:
    """Set a value at a nested path."""
    current = data
    for i, part in enumerate(parts[:-1]):
        match = re.match(r"^(.+)\[(\d+)\]$", part)
        if match:
            current = current.get(match.group(1), [])[int(match.group(2))]
        elif part == "[*]":
            continue  # Skip wildcard in setter
        elif isinstance(current, dict):
            current = current.get(part, {})
    if isinstance(current, dict):
        current[parts[-1]] = value
