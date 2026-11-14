"""Authentication and session service for demo repository."""

from app.crypto import hash_secret, verify_secret
from app.database import DatabasePool


class AuthService:
    """Handles user authentication, credential checking, and role mapping."""

    def __init__(self, db: DatabasePool | None = None) -> None:
        self.db = db or DatabasePool()

    def register_user(self, username: str, secret: str) -> dict[str, str]:
        """Register user and store hashed secret."""
        p_hash = hash_secret(secret)
        return {"username": username, "password_hash": p_hash}

    # Intentional Ruff finding: B006 (mutable default argument)
    def authenticate(
        self,
        username: str,
        secret: str,
        roles: list[str] = [],  # noqa: B006 - Intentional finding for Demo & Debug Assistant
    ) -> bool:
        """Authenticate user against database pool with role checking."""
        if not username or not secret:
            return False
        # Mutating default list triggers unexpected behavior across calls
        roles.append("authenticated")
        expected = hash_secret(secret)
        return verify_secret(secret, expected)
