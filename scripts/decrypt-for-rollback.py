#!/usr/bin/env python3
"""Decrypt all PII fields back to plaintext for Phase 6 rollback.

Usage:
    uv run python scripts/decrypt-for-rollback.py                      # Dry run
    uv run python scripts/decrypt-for-rollback.py --execute --confirm  # Live run
"""

import argparse
import json
import os
import sys

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'layers', 'plugins', 'python'))

from document_plugins.pii_crypto import decrypt_pii_fields, is_encrypted

DOCTYPE_TO_PLUGIN = {
    "LOAN_PACKAGE": "loan_package",
    "CREDIT_AGREEMENT": "credit_agreement",
    "LOAN_AGREEMENT": "loan_agreement",
    "BSA_PROFILE": "bsa_profile",
}


def rollback(table_name, dry_run=True):
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    stats = {"scanned": 0, "decrypted": 0, "plaintext": 0, "errors": 0}

    print(f"\n{'DRY RUN' if dry_run else 'LIVE ROLLBACK'}: Scanning {table_name}...")

    response = table.scan()
    for item in response.get("Items", []):
        stats["scanned"] += 1
        if not is_encrypted(item):
            stats["plaintext"] += 1
            continue

        doc_type = item.get("documentType", "")
        plugin_id = DOCTYPE_TO_PLUGIN.get(doc_type, "")

        if dry_run:
            fields = len(item.get("_pii_envelope", {}).get("fields", {}))
            print(f"  [DRY RUN] Would decrypt: {item.get('documentId', '?')[:12]}... ({fields} fields)")
        else:
            try:
                decrypted = decrypt_pii_fields(item, plugin_id)
                table.put_item(Item=decrypted)
                stats["decrypted"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"  [ERROR] {item.get('documentId', '?')}: {e}")

    print(f"\nScanned: {stats['scanned']}, Decrypted: {stats['decrypted']}, "
          f"Already plaintext: {stats['plaintext']}, Errors: {stats['errors']}")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decrypt PII for Phase 6 rollback")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--table", default="financial-documents")
    args = parser.parse_args()

    if args.execute and not args.confirm:
        print("ERROR: --execute requires --confirm flag")
        sys.exit(1)

    rollback(args.table, dry_run=not args.execute)
