"""Semantic code indexing package: chunking, embeddings, and vector store (Phase 2)."""

from app.indexing.chunker import (
    CodeChunker,
    chunk_python_file,
    chunk_python_source,
)
from app.indexing.models import (
    ChunkStrategy,
    CodeChunk,
)

__all__ = [
    "ChunkStrategy",
    "CodeChunk",
    "CodeChunker",
    "chunk_python_file",
    "chunk_python_source",
]
