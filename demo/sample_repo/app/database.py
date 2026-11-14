"""Sample database pool module for RepoPilot demo repository."""

from typing import Any


class DatabasePool:
    """Manages connection pools and simulated queries."""

    def __init__(self, dsn: str = "sqlite:///:memory:") -> None:
        self.dsn = dsn
        self.is_connected = True

    def execute_query(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Simulate SQL query execution."""
        if not self.is_connected:
            raise ConnectionError("Database pool is disconnected.")
        return [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}]

    def close(self) -> None:
        """Close pool connections."""
        self.is_connected = False
