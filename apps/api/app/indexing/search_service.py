"""Semantic search and chunk indexing service (P2-03, ADR 3).

Stores chunk embeddings in pgvector and executes cosine similarity searches.
"""

import math
import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import EmbeddingProvider, get_embedding_provider
from app.indexing.models import CodeChunk, CodeChunkRecord, SearchResultItem


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Calculate cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(dot / (norm_a * norm_b))


class SemanticSearchService:
    """Orchestrates indexing of code chunks into pgvector and semantic similarity search."""

    def __init__(self, embedding_provider: EmbeddingProvider | None = None) -> None:
        self.provider = embedding_provider or get_embedding_provider()

    async def index_chunks(
        self,
        db: AsyncSession,
        repository_id: uuid.UUID,
        chunks: Sequence[CodeChunk],
    ) -> int:
        """Embed and persist code chunks for a repository, replacing any existing ones."""
        if not chunks:
            return 0

        # Delete any existing chunks for this repository (idempotent re-indexing)
        await db.execute(
            delete(CodeChunkRecord).where(CodeChunkRecord.repository_id == repository_id)
        )

        # Batch embed chunk contents
        texts_to_embed = [
            f"{c.context_header}\n{c.content}" if c.context_header else c.content for c in chunks
        ]
        embeddings = await self.provider.embed_documents(texts_to_embed)

        records: list[CodeChunkRecord] = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            rec = CodeChunkRecord(
                id=uuid.uuid4(),
                repository_id=repository_id,
                file_path=chunk.file_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                context_header=chunk.context_header,
                strategy=chunk.strategy.value,
                symbol_name=chunk.symbol_name,
                symbol_type=chunk.symbol_type,
                char_count=chunk.char_count,
                estimated_tokens=chunk.estimated_tokens,
                content_sha256=chunk.content_sha256,
                embedding=embedding,
            )
            records.append(rec)
            db.add(rec)

        await db.commit()
        return len(records)

    async def search(
        self,
        db: AsyncSession,
        repository_id: uuid.UUID,
        query: str,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[SearchResultItem]:
        """Search code chunks for a repository using semantic similarity.

        Guarantees:
        - Returns path + line range + score (Acceptance Criteria P2-03)
        - Labelled with source="static" (Hard Rule 5)
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        query_vector = await self.provider.embed_query(cleaned_query)

        # First, attempt native pgvector cosine distance query
        try:
            distance_expr = CodeChunkRecord.embedding.cosine_distance(query_vector)
            stmt = (
                select(CodeChunkRecord, (1.0 - distance_expr).label("similarity"))
                .where(CodeChunkRecord.repository_id == repository_id)
                .where(CodeChunkRecord.embedding.is_not(None))
                .order_by(distance_expr.asc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            rows = result.all()

            search_results: list[SearchResultItem] = []
            for row in rows:
                if isinstance(row, CodeChunkRecord):
                    record = row
                    similarity = (
                        _cosine_similarity(query_vector, record.embedding)
                        if record.embedding is not None
                        else 0.0
                    )
                elif isinstance(row, (tuple, list)):
                    record = row[0]
                    similarity = float(row[1]) if len(row) > 1 and row[1] is not None else 0.0
                else:
                    record = getattr(row, "CodeChunkRecord", row)
                    similarity = float(getattr(row, "similarity", 0.0))

                if similarity < min_score:
                    continue

                search_results.append(
                    SearchResultItem(
                        id=record.id,
                        path=record.file_path,
                        start_line=record.start_line,
                        end_line=record.end_line,
                        score=round(similarity, 4),
                        content=record.content,
                        symbol_name=record.symbol_name,
                        symbol_type=record.symbol_type,
                        context_header=record.context_header,
                        source="static",
                    )
                )

            # Ensure sorted descending by score and capped by limit
            search_results.sort(key=lambda x: x.score, reverse=True)
            return search_results[:limit]

        except (SQLAlchemyError, TypeError, AttributeError, KeyError):
            # Fallback for environments / SQLite unit tests without native pgvector C extension
            stmt_all = (
                select(CodeChunkRecord)
                .where(CodeChunkRecord.repository_id == repository_id)
                .where(CodeChunkRecord.embedding.is_not(None))
            )
            result_all = await db.execute(stmt_all)
            all_records = list(result_all.scalars().all())

            scored_records: list[tuple[CodeChunkRecord, float]] = []
            for rec in all_records:
                if rec.embedding is not None:
                    sim = _cosine_similarity(query_vector, rec.embedding)
                    if sim >= min_score:
                        scored_records.append((rec, sim))

            # Sort by descending similarity score
            scored_records.sort(key=lambda x: x[1], reverse=True)
            top_records = scored_records[:limit]

            return [
                SearchResultItem(
                    id=rec.id,
                    path=rec.file_path,
                    start_line=rec.start_line,
                    end_line=rec.end_line,
                    score=round(sim, 4),
                    content=rec.content,
                    symbol_name=rec.symbol_name,
                    symbol_type=rec.symbol_type,
                    context_header=rec.context_header,
                    source="static",
                )
                for rec, sim in top_records
            ]
