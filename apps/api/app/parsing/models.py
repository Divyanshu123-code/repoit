"""Data models for code parsing, symbols, and imports (P1-04)."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SymbolType(str, Enum):
    """Classification of code symbols."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


@dataclass(frozen=True)
class Symbol:
    """Represents a code symbol (class, function, method, module)."""

    name: str
    full_name: str
    symbol_type: SymbolType
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed
    start_col: int  # 0-indexed
    end_col: int  # 0-indexed
    docstring: str | None = None
    parameters: list[str] = field(default_factory=list)
    parent_symbol: str | None = None
    decorators: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    is_async: bool = False


@dataclass(frozen=True)
class ImportItem:
    """Individual item imported in an import statement."""

    name: str
    alias: str | None = None


@dataclass(frozen=True)
class ImportStatement:
    """Represents an imported module or imported symbols."""

    module: str  # e.g., "math", "app.repos.models", ".utils"
    items: list[ImportItem] = field(default_factory=list)
    alias: str | None = None  # e.g., "np" in "import numpy as np"
    is_from_import: bool = False
    start_line: int = 1
    end_line: int = 1
    raw_statement: str = ""


@dataclass
class ParsedModule:
    """Complete AST parsing output for a Python file."""

    file_path: Path
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[ImportStatement] = field(default_factory=list)
    total_lines: int = 0
    docstring: str | None = None
    has_syntax_errors: bool = False
    source_sha256: str = ""
