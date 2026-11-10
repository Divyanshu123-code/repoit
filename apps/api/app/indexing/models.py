"""Data models for code chunking and semantic indexing (P2-01)."""

from dataclasses import dataclass
from enum import Enum


class ChunkStrategy(str, Enum):
    """Strategy used to partition source code into a chunk."""

    SYMBOL_BASED = "symbol_based"
    WINDOW_FALLBACK = "window_fallback"
    MODULE_PREAMBLE = "module_preamble"


@dataclass(frozen=True)
class CodeChunk:
    """Represents a chunk of code ready for embedding and semantic retrieval."""

    file_path: str
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed
    content: str
    strategy: ChunkStrategy
    symbol_name: str | None = None
    symbol_type: str | None = None
    context_header: str = ""
    char_count: int = 0
    estimated_tokens: int = 0
    content_sha256: str = ""
