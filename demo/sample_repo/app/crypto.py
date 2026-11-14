"""Cryptographic utility functions for demo repository."""

import hashlib
import hmac


def hash_secret(secret: str, salt: str = "repopilot_salt") -> str:
    """Compute secure HMAC-SHA256 signature."""
    key = salt.encode("utf-8")
    msg = secret.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_secret(secret: str, expected_hash: str, salt: str = "repopilot_salt") -> bool:
    """Verify secret against expected hash."""
    computed = hash_secret(secret, salt=salt)
    return hmac.compare_digest(computed, expected_hash)

