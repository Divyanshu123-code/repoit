"""create_code_chunks_pgvector

Revision ID: e5a7b8c9d012
Revises: c7e2b10a45f9
Create Date: 2026-11-11 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a7b8c9d012"
down_revision: str | Sequence[str] | None = "c7e2b10a45f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: ensure vector extension and create code_chunks table."""
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create code_chunks table
    op.create_table(
        "code_chunks",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "repository_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context_header", sa.Text(), server_default="", nullable=False),
        sa.Column("strategy", sa.String(length=50), nullable=False),
        sa.Column("symbol_name", sa.String(length=255), nullable=True),
        sa.Column("symbol_type", sa.String(length=50), nullable=True),
        sa.Column("char_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_index("ix_code_chunks_repository_id", "code_chunks", ["repository_id"], unique=False)
    op.create_index("ix_code_chunks_file_path", "code_chunks", ["file_path"], unique=False)
    op.create_index(
        "ix_code_chunks_repo_file", "code_chunks", ["repository_id", "file_path"], unique=False
    )
    op.create_index(
        "ix_code_chunks_content_sha256", "code_chunks", ["content_sha256"], unique=False
    )
    op.create_index("ix_code_chunks_symbol_name", "code_chunks", ["symbol_name"], unique=False)

    # 3. Create HNSW index on embeddings for fast cosine similarity search
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_code_chunks_embedding_hnsw "
        "ON code_chunks USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    """Downgrade schema: drop code_chunks table and index."""
    op.execute("DROP INDEX IF EXISTS ix_code_chunks_embedding_hnsw;")
    op.drop_index("ix_code_chunks_symbol_name", table_name="code_chunks")
    op.drop_index("ix_code_chunks_content_sha256", table_name="code_chunks")
    op.drop_index("ix_code_chunks_repo_file", table_name="code_chunks")
    op.drop_index("ix_code_chunks_file_path", table_name="code_chunks")
    op.drop_index("ix_code_chunks_repository_id", table_name="code_chunks")
    op.drop_table("code_chunks")
