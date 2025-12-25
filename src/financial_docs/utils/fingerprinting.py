"""Document fingerprinting utilities for deduplication.

This module provides functions to calculate unique fingerprints (hashes)
for documents to enable deduplication. If the same document is uploaded
again, we can skip processing and return cached results from DynamoDB.
"""

import hashlib
import io
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, BinaryIO


@dataclass
class DocumentFingerprint:
    """Represents a document's unique fingerprint."""

    content_hash: str  # SHA-256 hash of file content
    file_size: int  # File size in bytes
    created_at: str  # ISO timestamp when fingerprint was created
    algorithm: str = "sha256"  # Hash algorithm used

    def to_dict(self) -> dict:
        """Convert to dictionary for DynamoDB storage."""
        return {
            "contentHash": self.content_hash,
            "fileSize": self.file_size,
            "createdAt": self.created_at,
            "algorithm": self.algorithm,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentFingerprint":
        """Create from DynamoDB item."""
        return cls(
            content_hash=data["contentHash"],
            file_size=int(data["fileSize"]),
            created_at=data["createdAt"],
            algorithm=data.get("algorithm", "sha256"),
        )


def calculate_content_hash(content: bytes, algorithm: str = "sha256") -> str:
    """Calculate hash of raw bytes content.

    Args:
        content: Raw bytes to hash
        algorithm: Hash algorithm (default: sha256)

    Returns:
        Hexadecimal hash string
    """
    if algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha1":
        hasher = hashlib.sha1()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    hasher.update(content)
    return hasher.hexdigest()


def calculate_document_hash(
    file_content: bytes | BinaryIO,
    chunk_size: int = 8192,
) -> DocumentFingerprint:
    """Calculate a unique fingerprint for a document.

    Uses SHA-256 for content hashing. For large files, processes
    in chunks to minimize memory usage.

    Args:
        file_content: Either raw bytes or a file-like object
        chunk_size: Size of chunks for streaming hash (default: 8KB)

    Returns:
        DocumentFingerprint with hash and metadata
    """
    hasher = hashlib.sha256()
    total_size = 0

    if isinstance(file_content, bytes):
        # Direct bytes input
        hasher.update(file_content)
        total_size = len(file_content)
    else:
        # File-like object - process in chunks
        while True:
            chunk = file_content.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            total_size += len(chunk)

        # Reset file pointer if possible
        if hasattr(file_content, "seek"):
            file_content.seek(0)

    return DocumentFingerprint(
        content_hash=hasher.hexdigest(),
        file_size=total_size,
        created_at=datetime.utcnow().isoformat() + "Z",
        algorithm="sha256",
    )


def calculate_s3_etag_hash(content: bytes, chunk_size: int = 8 * 1024 * 1024) -> str:
    """Calculate hash similar to S3 ETag for multipart uploads.

    S3 calculates ETags differently for single vs multipart uploads.
    For single uploads, ETag is MD5 of content.
    For multipart, ETag is MD5 of concatenated part MD5s + "-" + part count.

    This function calculates a consistent hash regardless of upload method.

    Args:
        content: File content bytes
        chunk_size: Part size for multipart calculation (default: 8MB)

    Returns:
        Hash string matching S3 ETag format
    """
    if len(content) <= chunk_size:
        # Single part - standard MD5
        return hashlib.md5(content).hexdigest()

    # Multipart - calculate part hashes
    part_hashes = []
    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        part_hashes.append(hashlib.md5(chunk).digest())

    # Concatenate part hashes and hash again
    combined = b"".join(part_hashes)
    final_hash = hashlib.md5(combined).hexdigest()

    return f"{final_hash}-{len(part_hashes)}"


def normalize_content_for_hash(content: bytes) -> bytes:
    """Normalize document content before hashing.

    This helps identify documents that are semantically the same
    but may have minor differences (like different metadata).

    For PDFs, this could strip metadata and normalize whitespace.
    Currently returns content as-is for exact matching.

    Args:
        content: Raw document bytes

    Returns:
        Normalized bytes for consistent hashing
    """
    # For now, return as-is for exact byte matching
    # Future: Could use PyPDF to strip metadata and extract text-only hash
    return content


def generate_composite_fingerprint(
    content_hash: str,
    filename: str,
    file_size: int,
) -> str:
    """Generate a composite fingerprint combining multiple attributes.

    This creates a unique identifier that considers:
    - File content (via hash)
    - Original filename
    - File size

    Useful for distinguishing documents that might have same content
    but different names, or for creating partition-friendly keys.

    Args:
        content_hash: SHA-256 hash of content
        filename: Original filename
        file_size: File size in bytes

    Returns:
        Composite fingerprint string
    """
    composite = f"{content_hash}:{filename}:{file_size}"
    return hashlib.sha256(composite.encode()).hexdigest()[:32]
