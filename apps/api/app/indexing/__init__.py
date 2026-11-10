"""Semantic code indexing package: chunking, embeddings, and vector store (Phase 2)."""

from app.indexing.chunker import (
    CodeChunker,
    chunk_python_file,
    chunk_python_source,
)
from app.indexing.models import (
    ChunkStrategy,
    CodeChunk,
    CodeChunkRecord,
    SearchResponse,
    SearchResultItem,
)
from app.indexing.search_service import SemanticSearchService

__all__ = [
    "ChunkStrategy",
    "CodeChunk",
    "CodeChunkRecord",
    "CodeChunker",
    "SearchResponse",
    "SearchResultItem",
    "SemanticSearchService",
    "chunk_python_file",
    "chunk_python_source",
]
