"""initial_empty

Revision ID: 676d5b6e6af4
Revises:
Create Date: 2026-11-03 16:13:12.228871

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "676d5b6e6af4"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
