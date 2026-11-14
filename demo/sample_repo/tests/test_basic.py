"""Basic tests for demo repository."""

from app.crypto import hash_secret, verify_secret
from app.database import DatabasePool


def test_crypto_hashing() -> None:
    h = hash_secret("my_secret")
    assert verify_secret("my_secret", h)
    assert not verify_secret("wrong_secret", h)


def test_database_query() -> None:
    db = DatabasePool()
    users = db.execute_query("SELECT * FROM users")
    assert len(users) == 2
    assert users[0]["username"] == "alice"

