"""Tests for symbol-aware code chunking (P2-01).

Acceptance Criteria:
- Chunks never split a function mid-body when it fits limit.
"""

from pathlib import Path

from app.indexing import (
    ChunkStrategy,
    CodeChunker,
    chunk_python_file,
    chunk_python_source,
)


def test_function_never_split_mid_body_when_fits_limit() -> None:
    """AC: A function that fits within max_chunk_chars is kept as a single atomic chunk."""
    source = '''"""Module docstring."""

def calculate_metrics(values: list[int]) -> dict[str, float]:
    """Calculate basic metrics."""
    if not values:
        return {"mean": 0.0, "total": 0.0}
    total = float(sum(values))
    mean = total / len(values)
    return {"mean": mean, "total": total}
'''
    chunks = chunk_python_source(source, max_chunk_chars=500)

    # Find the function chunk
    func_chunks = [c for c in chunks if c.symbol_name == "calculate_metrics"]
    assert len(func_chunks) == 1
    chunk = func_chunks[0]

    assert chunk.strategy == ChunkStrategy.SYMBOL_BASED
    assert chunk.symbol_name == "calculate_metrics"
    assert chunk.symbol_type == "function"
    assert "def calculate_metrics" in chunk.content
    assert 'return {"mean": mean, "total": total}' in chunk.content
    assert chunk.start_line == 3
    assert chunk.end_line == 9
    assert chunk.char_count == len(chunk.content)
    assert len(chunk.content_sha256) == 64
    assert "# Symbol: calculate_metrics" in chunk.context_header


def test_module_preamble_captured() -> None:
    """Module docstrings and imports are captured in a preamble chunk."""
    source = '''"""This is a sample module."""
import os
import sys

from math import sqrt

def helper() -> int:
    return 42
'''
    chunks = chunk_python_source(source, max_chunk_chars=1000)
    assert len(chunks) == 2

    preamble = chunks[0]
    assert preamble.strategy == ChunkStrategy.MODULE_PREAMBLE
    assert preamble.start_line == 1
    assert preamble.end_line == 6
    assert '"""This is a sample module."""' in preamble.content
    assert "from math import sqrt" in preamble.content

    func_chunk = chunks[1]
    assert func_chunk.strategy == ChunkStrategy.SYMBOL_BASED
    assert func_chunk.symbol_name == "helper"
    assert func_chunk.start_line == 7
    assert func_chunk.end_line == 8


def test_multiple_functions_preserved_independently() -> None:
    """Multiple top-level functions each become distinct atomic symbol chunks."""
    source = """def func_one():
    return 1

def func_two():
    return 2

def func_three():
    return 3
"""
    chunks = chunk_python_source(source, max_chunk_chars=1000)
    func_chunks = [c for c in chunks if c.strategy == ChunkStrategy.SYMBOL_BASED]
    assert len(func_chunks) == 3
    names = [c.symbol_name for c in func_chunks]
    assert names == ["func_one", "func_two", "func_three"]


def test_small_class_kept_intact() -> None:
    """A class small enough to fit within max_chunk_chars stays a single atomic symbol chunk."""
    source = """class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def distance_from_origin(self) -> float:
        return (self.x ** 2 + self.y ** 2) ** 0.5
"""
    chunks = chunk_python_source(source, max_chunk_chars=1000)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.strategy == ChunkStrategy.SYMBOL_BASED
    assert chunk.symbol_name == "Point"
    assert chunk.symbol_type == "class"
    assert "class Point:" in chunk.content
    assert "distance_from_origin" in chunk.content


def test_large_class_split_by_methods_intact() -> None:
    """A class exceeding max_chunk_chars is split into header + atomic method chunks."""
    # Each method is small enough to fit in max_chunk_chars=250, but whole class > 250
    source = '''class DataService:
    """Service to process enterprise records."""
    version = "1.0.0"

    def fetch_records(self, limit: int = 100) -> list[dict]:
        """Fetch records from upstream storage."""
        records = []
        for idx in range(limit):
            records.append({"id": idx, "status": "active"})
        return records

    def transform_records(self, items: list[dict]) -> list[dict]:
        """Transform records into normalized representation."""
        output = []
        for item in items:
            output.append({"transformed_id": item["id"]})
        return output
'''
    chunker = CodeChunker(max_chunk_chars=260)
    chunks = chunker.chunk_module(source, file_path="service.py")

    method_chunks = [c for c in chunks if c.symbol_type == "method"]
    assert len(method_chunks) == 2

    fetch_chunk = next(c for c in method_chunks if c.symbol_name == "DataService.fetch_records")
    assert "def fetch_records" in fetch_chunk.content
    assert "return records" in fetch_chunk.content
    assert fetch_chunk.strategy == ChunkStrategy.SYMBOL_BASED

    transform_chunk = next(
        c for c in method_chunks if c.symbol_name == "DataService.transform_records"
    )
    assert "def transform_records" in transform_chunk.content
    assert "return output" in transform_chunk.content
    assert transform_chunk.strategy == ChunkStrategy.SYMBOL_BASED

    header_chunks = [c for c in chunks if c.symbol_name == "DataService.__header__"]
    assert len(header_chunks) == 1
    assert "class DataService:" in header_chunks[0].content


def test_oversized_function_falls_back_to_sliding_window() -> None:
    """When a single function exceeds max_chunk_chars, it falls back to sliding-window chunks."""
    long_body_lines = [f"    step_{i} = {i} * 2" for i in range(50)]
    source = "def very_long_function():\n" + "\n".join(long_body_lines) + "\n    return step_49\n"

    chunker = CodeChunker(max_chunk_chars=200, overlap_lines=2)
    chunks = chunker.chunk_module(source, file_path="long_func.py")

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.strategy == ChunkStrategy.WINDOW_FALLBACK
        assert chunk.symbol_name == "very_long_function"
        assert chunk.char_count <= 250  # window bounds reasonably respected


def test_script_with_no_symbols_falls_back_to_window() -> None:
    """A raw script with no classes or functions uses window fallback."""
    source = """x = 1
y = 2
z = x + y
print(z)
for i in range(10):
    print("Item:", i)
"""
    chunks = chunk_python_source(source, max_chunk_chars=50)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.strategy == ChunkStrategy.WINDOW_FALLBACK


def test_trailing_code_captured() -> None:
    """Code after the last symbol (like __main__ block) is captured."""
    source = """def add(a: int, b: int) -> int:
    return a + b

if __name__ == "__main__":
    result = add(10, 20)
    print("Sum:", result)
"""
    chunks = chunk_python_source(source, max_chunk_chars=500)
    assert len(chunks) == 2
    assert chunks[0].symbol_name == "add"
    assert chunks[1].strategy == ChunkStrategy.WINDOW_FALLBACK
    assert 'if __name__ == "__main__":' in chunks[1].content


def test_empty_or_whitespace_source() -> None:
    """Empty or whitespace source produces empty chunks list."""
    assert chunk_python_source("") == []
    assert chunk_python_source("   \n\n\t  ") == []


def test_chunk_python_file(tmp_path: Path) -> None:
    """chunk_python_file properly reads from disk and processes file."""
    test_file = tmp_path / "sample.py"
    test_file.write_text("def ping() -> str:\n    return 'pong'\n", encoding="utf-8")

    chunks = chunk_python_file(test_file)
    assert len(chunks) == 1
    assert chunks[0].symbol_name == "ping"
    assert chunks[0].content == "def ping() -> str:\n    return 'pong'"
