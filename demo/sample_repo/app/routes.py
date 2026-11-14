"""Application routing and controller endpoints for demo repository."""

from app.auth import AuthService


class UserController:
    """REST controller delegating authentication to AuthService."""

    def __init__(self, auth: AuthService | None = None) -> None:
        self.auth = auth or AuthService()

    def handle_login(self, username: str, secret: str) -> dict[str, str]:
        """Process incoming user login."""
        success = self.auth.authenticate(username, secret)
        if success:
            return {"status": "ok", "user": username}
        return {"status": "unauthorized"}

