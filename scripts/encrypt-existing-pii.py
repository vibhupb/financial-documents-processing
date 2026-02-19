#!/usr/bin/env python3
"""Encrypt existing unencrypted PII in DynamoDB records.

Usage:
    uv run python scripts/encrypt-existing-pii.py              # Dry run
    uv run python scripts/encrypt-existing-pii.py --execute    # Live run
"""

import argparse
import json
import os
import sys
import time

import boto3

# Add plugins layer to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'layers', 'plugins', 'python'))

from document_plugins.pii_crypto import encrypt_pii_fields, is_encrypted

DOCTYPE_TO_PLUGIN = {
    "LOAN_PACKAGE": "loan_package",
    "CREDIT_AGREEMENT": "credit_agreement",
    "LOAN_AGREEMENT": "loan_agreement",
    "BSA_PROFILE": "bsa_profile",
}


def migrate(table_name, kms_key_id, dry_run=True):
    os.environ["PII_KMS_KEY_ID"] = kms_key_id
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    stats = {"scanned": 0, "encrypted": 0, "skipped": 0, "errors": 0}

    print(f"\n{'DRY RUN' if dry_run else 'LIVE RUN'}: Scanning {table_name}...")

    response = table.scan()
    for item in response.get("Items", []):
        stats["scanned"] += 1
        if is_encrypted(item):
            stats["skipped"] += 1
            continue

        doc_type = item.get("documentType", "")
        plugin_id = DOCTYPE_TO_PLUGIN.get(doc_type, "")
        if not plugin_id:
            stats["skipped"] += 1
            continue

        if dry_run:
            print(f"  [DRY RUN] Would encrypt: {item.get('documentId', '?')[:12]}... ({doc_type})")
        else:
            try:
                encrypted = encrypt_pii_fields(item, plugin_id)
                table.put_item(Item=encrypted)
                stats["encrypted"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"  [ERROR] {item.get('documentId', '?')}: {e}")

    print(f"\nScanned: {stats['scanned']}, Encrypted: {stats['encrypted']}, "
          f"Skipped: {stats['skipped']}, Errors: {stats['errors']}")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encrypt existing PII in DynamoDB")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--table", default="financial-documents")
    parser.add_argument("--kms-key-id", default=os.environ.get("PII_KMS_KEY_ID", ""))
    args = parser.parse_args()

    if not args.kms_key_id:
        print("ERROR: --kms-key-id required or set PII_KMS_KEY_ID env var")
        sys.exit(1)

    migrate(args.table, args.kms_key_id, dry_run=not args.execute)
