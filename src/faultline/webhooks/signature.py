"""HMAC-SHA256 signature verification for GitHub Webhook deliveries."""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional


def verify_webhook_signature(
    payload: bytes,
    signature_header: Optional[str],
    secret: str,
) -> bool:
    """
    Verifies that the GitHub payload matches the X-Hub-Signature-256 header using constant-time comparison.
    """
    if not signature_header or not isinstance(signature_header, str):
        return False

    if not signature_header.startswith("sha256="):
        return False

    if not secret:
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)
