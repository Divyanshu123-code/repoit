"""Symbol-aware and sliding-window code chunker for Python files (P2-01).

Implements symbol-based chunking that preserves functions and classes intact,
with a sliding window fallback for scripts or oversized symbols.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

from app.indexing.models import ChunkStrategy, CodeChunk
from app.parsing import (
    ParsedModule,
    SymbolType,
    TreeSitterPythonParser,
    get_python_parser,
)


class CodeChunker:
    """Chunks source code into semantic units suitable for embeddings and vector search."""

    def __init__(
        self,
        max_chunk_chars: int = 1500,
        overlap_lines: int = 3,
        parser: TreeSitterPythonParser | None = None,
    ) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.overlap_lines = max(1, overlap_lines)
        self.parser = parser or get_python_parser()

    def _create_chunk(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        content: str,
        strategy: ChunkStrategy,
        symbol_name: str | None = None,
        symbol_type: str | None = None,
    ) -> CodeChunk:
        """Helper to construct a fully populated CodeChunk."""
        cleaned_content = content.strip("\n")
        sha256 = hashlib.sha256(cleaned_content.encode("utf-8")).hexdigest()

        header_lines = [f"# File: {file_path}"]
        if symbol_name:
            header_lines.append(f"# Symbol: {symbol_name}")
        context_header = "\n".join(header_lines) + "\n"

        return CodeChunk(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            content=cleaned_content,
            strategy=strategy,
            symbol_name=symbol_name,
            symbol_type=symbol_type,
            context_header=context_header,
            char_count=len(cleaned_content),
            estimated_tokens=max(1, len(cleaned_content) // 4),
            content_sha256=sha256,
        )

    def _window_fallback_chunking(
        self,
        lines: Sequence[str],
        file_path: str,
        start_line_offset: int = 1,
        symbol_name: str | None = None,
        symbol_type: str | None = None,
    ) -> list[CodeChunk]:
        """Sliding window fallback by lines with overlap."""
        chunks: list[CodeChunk] = []
        total_lines = len(lines)
        if total_lines == 0:
            return chunks

        i = 0
        while i < total_lines:
            curr_lines: list[str] = []
            curr_chars = 0
            j = i

            while j < total_lines:
                line_len = len(lines[j])
                if curr_chars + line_len > self.max_chunk_chars and curr_lines:
                    break
                curr_lines.append(lines[j])
                curr_chars += line_len
                j += 1

            chunk_content = "".join(curr_lines)
            if chunk_content.strip():
                start_l = start_line_offset + i
                end_l = start_line_offset + j - 1
                chunks.append(
                    self._create_chunk(
                        file_path=file_path,
                        start_line=start_l,
                        end_line=end_l,
                        content=chunk_content,
                        strategy=ChunkStrategy.WINDOW_FALLBACK,
                        symbol_name=symbol_name,
                        symbol_type=symbol_type,
                    )
                )

            # Advance window by taking overlap into account
            step = max(1, (j - i) - self.overlap_lines)
            if j >= total_lines:
                break
            i += step

        return chunks

    def chunk_module(
        self,
        code: str,
        file_path: str = "module.py",
        parsed_module: ParsedModule | None = None,
    ) -> list[CodeChunk]:
        """Partition Python code into chunks.

        Guarantees:
        - Standalone functions and class methods are never split mid-body if they fit within max_chunk_chars.
        - Falls back to sliding window chunking for oversized symbols or files without symbols.
        """
        if not code.strip():
            return []

        lines = code.splitlines(keepends=True)
        total_lines = len(lines)

        # Parse symbols if not provided
        parsed = parsed_module or self.parser.parse_source(code, file_path=file_path)
        symbols = parsed.symbols

        # If file has no symbols, fallback completely to window chunking
        if not symbols:
            return self._window_fallback_chunking(lines, file_path=file_path)

        chunks: list[CodeChunk] = []

        # Separate symbols into classes, methods, and functions
        top_level_symbols = [s for s in symbols if s.parent_symbol is None]
        top_level_symbols.sort(key=lambda s: s.start_line)

        # 1. Preamble before first symbol (imports, module docstrings, constants)
        first_sym_line = top_level_symbols[0].start_line
        if first_sym_line > 1:
            preamble_lines = lines[: first_sym_line - 1]
            preamble_text = "".join(preamble_lines)
            if preamble_text.strip():
                if len(preamble_text) <= self.max_chunk_chars:
                    chunks.append(
                        self._create_chunk(
                            file_path=file_path,
                            start_line=1,
                            end_line=first_sym_line - 1,
                            content=preamble_text,
                            strategy=ChunkStrategy.MODULE_PREAMBLE,
                        )
                    )
                else:
                    chunks.extend(
                        self._window_fallback_chunking(
                            preamble_lines, file_path=file_path, start_line_offset=1
                        )
                    )

        # 2. Process each top-level symbol (functions, classes)
        last_processed_line = first_sym_line - 1

        for i, sym in enumerate(top_level_symbols):
            # Check gap code between previous symbol and current symbol
            if sym.start_line > last_processed_line + 1:
                gap_lines = lines[last_processed_line : sym.start_line - 1]
                gap_text = "".join(gap_lines)
                if gap_text.strip():
                    if len(gap_text) <= self.max_chunk_chars:
                        chunks.append(
                            self._create_chunk(
                                file_path=file_path,
                                start_line=last_processed_line + 1,
                                end_line=sym.start_line - 1,
                                content=gap_text,
                                strategy=ChunkStrategy.WINDOW_FALLBACK,
                            )
                        )
                    else:
                        chunks.extend(
                            self._window_fallback_chunking(
                                gap_lines,
                                file_path=file_path,
                                start_line_offset=last_processed_line + 1,
                            )
                        )

            sym_lines = lines[sym.start_line - 1 : sym.end_line]
            sym_content = "".join(sym_lines)

            if sym.symbol_type == SymbolType.FUNCTION:
                # Standalone Function
                if len(sym_content) <= self.max_chunk_chars:
                    # ACCEPTANCE CRITERIA: never split a function mid-body when it fits limit
                    chunks.append(
                        self._create_chunk(
                            file_path=file_path,
                            start_line=sym.start_line,
                            end_line=sym.end_line,
                            content=sym_content,
                            strategy=ChunkStrategy.SYMBOL_BASED,
                            symbol_name=sym.full_name,
                            symbol_type=sym.symbol_type.value,
                        )
                    )
                else:
                    # Oversized function: fallback to sliding window within the function
                    chunks.extend(
                        self._window_fallback_chunking(
                            sym_lines,
                            file_path=file_path,
                            start_line_offset=sym.start_line,
                            symbol_name=sym.full_name,
                            symbol_type=sym.symbol_type.value,
                        )
                    )

            elif sym.symbol_type == SymbolType.CLASS:
                # Class definition
                class_methods = [
                    s
                    for s in symbols
                    if s.parent_symbol == sym.full_name and s.symbol_type == SymbolType.METHOD
                ]
                class_methods.sort(key=lambda s: s.start_line)

                # If whole class fits limit, keep whole class as single chunk
                if len(sym_content) <= self.max_chunk_chars:
                    chunks.append(
                        self._create_chunk(
                            file_path=file_path,
                            start_line=sym.start_line,
                            end_line=sym.end_line,
                            content=sym_content,
                            strategy=ChunkStrategy.SYMBOL_BASED,
                            symbol_name=sym.full_name,
                            symbol_type=sym.symbol_type.value,
                        )
                    )
                elif class_methods:
                    # Class is large: chunk each method as an atomic symbol block
                    # Class header / preamble
                    first_method_line = class_methods[0].start_line
                    header_lines = lines[sym.start_line - 1 : first_method_line - 1]
                    header_text = "".join(header_lines)
                    if header_text.strip():
                        chunks.append(
                            self._create_chunk(
                                file_path=file_path,
                                start_line=sym.start_line,
                                end_line=first_method_line - 1,
                                content=header_text,
                                strategy=ChunkStrategy.SYMBOL_BASED,
                                symbol_name=f"{sym.full_name}.__header__",
                                symbol_type=sym.symbol_type.value,
                            )
                        )

                    for method in class_methods:
                        method_lines = lines[method.start_line - 1 : method.end_line]
                        method_content = "".join(method_lines)

                        if len(method_content) <= self.max_chunk_chars:
                            # Method fits limit: keep entire method intact
                            chunks.append(
                                self._create_chunk(
                                    file_path=file_path,
                                    start_line=method.start_line,
                                    end_line=method.end_line,
                                    content=method_content,
                                    strategy=ChunkStrategy.SYMBOL_BASED,
                                    symbol_name=method.full_name,
                                    symbol_type=method.symbol_type.value,
                                )
                            )
                        else:
                            # Oversized method
                            chunks.extend(
                                self._window_fallback_chunking(
                                    method_lines,
                                    file_path=file_path,
                                    start_line_offset=method.start_line,
                                    symbol_name=method.full_name,
                                    symbol_type=method.symbol_type.value,
                                )
                            )
                else:
                    # Large class with no methods (e.g. huge dataclass/constants class)
                    chunks.extend(
                        self._window_fallback_chunking(
                            sym_lines,
                            file_path=file_path,
                            start_line_offset=sym.start_line,
                            symbol_name=sym.full_name,
                            symbol_type=sym.symbol_type.value,
                        )
                    )

            last_processed_line = sym.end_line

        # 3. Trailing code after last symbol (e.g. if __name__ == '__main__': ...)
        if last_processed_line < total_lines:
            trailing_lines = lines[last_processed_line:]
            trailing_text = "".join(trailing_lines)
            if trailing_text.strip():
                if len(trailing_text) <= self.max_chunk_chars:
                    chunks.append(
                        self._create_chunk(
                            file_path=file_path,
                            start_line=last_processed_line + 1,
                            end_line=total_lines,
                            content=trailing_text,
                            strategy=ChunkStrategy.WINDOW_FALLBACK,
                        )
                    )
                else:
                    chunks.extend(
                        self._window_fallback_chunking(
                            trailing_lines,
                            file_path=file_path,
                            start_line_offset=last_processed_line + 1,
                        )
                    )

        return chunks


def chunk_python_source(
    code: str,
    file_path: str = "module.py",
    max_chunk_chars: int = 1500,
) -> list[CodeChunk]:
    """Convenience helper to chunk Python source code."""
    chunker = CodeChunker(max_chunk_chars=max_chunk_chars)
    return chunker.chunk_module(code, file_path=file_path)


def chunk_python_file(
    file_path: Path,
    max_chunk_chars: int = 1500,
) -> list[CodeChunk]:
    """Convenience helper to chunk a Python file from disk."""
    code = file_path.read_text(encoding="utf-8", errors="replace")
    return chunk_python_source(code, file_path=str(file_path), max_chunk_chars=max_chunk_chars)
