"""Unit tests for Tree-sitter AST symbol and import parsing (P1-04)."""

from pathlib import Path

import pytest

from app.parsing import (
    ImportStatement,
    ParsedModule,
    SymbolType,
    parse_python_file,
    parse_python_source,
)


@pytest.fixture
def fixture_parsing_repo(tmp_path: Path) -> Path:
    """Create a realistic Python repository fixture for parsing evaluation."""
    repo_dir = tmp_path / "python_fixture_repo"
    repo_dir.mkdir()

    calc_file = repo_dir / "calculator.py"
    calc_file.write_text(
        '''"""Calculator service with math helpers."""

import math
from typing import Union, List as MyList
from ..core.constants import PI, EPSILON as EPS

@dataclass
class BaseCalculator:
    """Base calculator contract."""

    def reset(self) -> None:
        """Reset internal accumulator."""
        pass

class AdvancedCalculator(BaseCalculator):
    """Advanced calculator supporting asynchronous computations."""

    def __init__(self, precision: int = 4) -> None:
        """Initialize calculator with precision."""
        self.precision = precision

    @log_execution
    async def compute_async(self, data: list[int], factor: float = 1.0) -> float:
        """Compute asynchronously with scaling factor."""
        return sum(data) * factor

def add_numbers(x: int, y: int) -> int:
    """Add two numbers together."""
    return x + y

def outer_factory(multiplier: int):
    """Factory creating scaled multiplier."""
    def scaled(value: int) -> int:
        return value * multiplier

    return scaled
'''
    )

    user_file = repo_dir / "user.py"
    user_file.write_text(
        """from dataclasses import dataclass

@dataclass
class User:
    id: str
    username: str

    def display_name(self) -> str:
        return f"User({self.username})"
"""
    )

    faulty_file = repo_dir / "syntax_error.py"
    faulty_file.write_text(
        """def invalid_func(
    x = 
"""
    )

    return repo_dir


def test_fixture_repo_extracts_expected_symbols_exactly(fixture_parsing_repo: Path) -> None:
    """Acceptance Criteria: fixture repo extracts expected symbol list exactly."""
    calc_path = fixture_parsing_repo / "calculator.py"
    parsed: ParsedModule = parse_python_file(calc_path)

    # 1. Verify exact full names of extracted symbols
    extracted_full_names = [s.full_name for s in parsed.symbols]
    expected_full_names = [
        "BaseCalculator",
        "BaseCalculator.reset",
        "AdvancedCalculator",
        "AdvancedCalculator.__init__",
        "AdvancedCalculator.compute_async",
        "add_numbers",
        "outer_factory",
        "outer_factory.scaled",
    ]
    assert extracted_full_names == expected_full_names, (
        f"Extracted symbols {extracted_full_names} do not match expected {expected_full_names}"
    )

    # 2. Verify exact symbol types
    symbols_by_name = {s.full_name: s for s in parsed.symbols}

    assert symbols_by_name["BaseCalculator"].symbol_type == SymbolType.CLASS
    assert symbols_by_name["BaseCalculator.reset"].symbol_type == SymbolType.METHOD
    assert symbols_by_name["AdvancedCalculator"].symbol_type == SymbolType.CLASS
    assert symbols_by_name["AdvancedCalculator.__init__"].symbol_type == SymbolType.METHOD
    assert symbols_by_name["AdvancedCalculator.compute_async"].symbol_type == SymbolType.METHOD
    assert symbols_by_name["add_numbers"].symbol_type == SymbolType.FUNCTION
    assert symbols_by_name["outer_factory"].symbol_type == SymbolType.FUNCTION
    assert symbols_by_name["outer_factory.scaled"].symbol_type == SymbolType.FUNCTION

    # 3. Verify parameters
    assert symbols_by_name["AdvancedCalculator.__init__"].parameters == ["self", "precision"]
    assert symbols_by_name["AdvancedCalculator.compute_async"].parameters == [
        "self",
        "data",
        "factor",
    ]
    assert symbols_by_name["add_numbers"].parameters == ["x", "y"]
    assert symbols_by_name["outer_factory"].parameters == ["multiplier"]
    assert symbols_by_name["outer_factory.scaled"].parameters == ["value"]

    # 4. Verify base classes
    assert symbols_by_name["AdvancedCalculator"].bases == ["BaseCalculator"]
    assert symbols_by_name["BaseCalculator"].bases == []

    # 5. Verify decorators
    assert symbols_by_name["BaseCalculator"].decorators == ["@dataclass"]
    assert symbols_by_name["AdvancedCalculator.compute_async"].decorators == ["@log_execution"]

    # 6. Verify async detection
    assert symbols_by_name["AdvancedCalculator.compute_async"].is_async is True
    assert symbols_by_name["add_numbers"].is_async is False

    # 7. Verify docstrings
    assert parsed.docstring == "Calculator service with math helpers."
    assert symbols_by_name["BaseCalculator"].docstring == "Base calculator contract."
    assert symbols_by_name["BaseCalculator.reset"].docstring == "Reset internal accumulator."
    assert (
        symbols_by_name["AdvancedCalculator"].docstring
        == "Advanced calculator supporting asynchronous computations."
    )
    assert (
        symbols_by_name["AdvancedCalculator.__init__"].docstring
        == "Initialize calculator with precision."
    )
    assert symbols_by_name["add_numbers"].docstring == "Add two numbers together."


def test_line_ranges_are_accurate_and_positive(fixture_parsing_repo: Path) -> None:
    """Verify that symbol start and end lines are accurate, 1-indexed, and monotonic."""
    calc_path = fixture_parsing_repo / "calculator.py"
    parsed = parse_python_file(calc_path)

    for sym in parsed.symbols:
        assert sym.start_line >= 1, (
            f"Symbol {sym.name} has non-positive start line {sym.start_line}"
        )
        assert sym.end_line >= sym.start_line, (
            f"Symbol {sym.name} end line {sym.end_line} is before start {sym.start_line}"
        )

    symbols_by_name = {s.full_name: s for s in parsed.symbols}
    # BaseCalculator begins with decorator on line 7 and ends around line 14
    base_calc = symbols_by_name["BaseCalculator"]
    assert base_calc.start_line == 7
    assert base_calc.end_line >= 13

    # reset method is inside BaseCalculator
    reset_method = symbols_by_name["BaseCalculator.reset"]
    assert reset_method.start_line >= base_calc.start_line
    assert reset_method.end_line <= base_calc.end_line


def test_import_extraction_exact(fixture_parsing_repo: Path) -> None:
    """Verify exact parsing of plain, from-import, aliased, and relative imports."""
    calc_path = fixture_parsing_repo / "calculator.py"
    parsed = parse_python_file(calc_path)

    imports: list[ImportStatement] = parsed.imports
    assert len(imports) == 3

    # import math
    assert imports[0].module == "math"
    assert imports[0].is_from_import is False
    assert imports[0].raw_statement == "import math"

    # from typing import Union, List as MyList
    assert imports[1].module == "typing"
    assert imports[1].is_from_import is True
    assert len(imports[1].items) == 2
    assert imports[1].items[0].name == "Union"
    assert imports[1].items[0].alias is None
    assert imports[1].items[1].name == "List"
    assert imports[1].items[1].alias == "MyList"

    # from ..core.constants import PI, EPSILON as EPS
    assert imports[2].module == "..core.constants"
    assert imports[2].is_from_import is True
    assert len(imports[2].items) == 2
    assert imports[2].items[0].name == "PI"
    assert imports[2].items[1].name == "EPSILON"
    assert imports[2].items[1].alias == "EPS"


def test_syntax_error_resilience(fixture_parsing_repo: Path) -> None:
    """Verify that files with syntax errors do not crash parser and flag has_syntax_errors."""
    faulty_path = fixture_parsing_repo / "syntax_error.py"
    parsed = parse_python_file(faulty_path)

    assert parsed.has_syntax_errors is True
    assert parsed.file_path == faulty_path


def test_parse_python_source_in_memory() -> None:
    """Verify parse_python_source function operates directly on strings and bytes."""
    code = """
def standalone():
    pass
"""
    parsed = parse_python_source(code, file_path="in_memory.py")
    assert len(parsed.symbols) == 1
    assert parsed.symbols[0].name == "standalone"
    assert parsed.total_lines == 3
    assert parsed.has_syntax_errors is False
    assert len(parsed.source_sha256) == 64
