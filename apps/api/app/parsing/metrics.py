"""Code metrics extraction using radon (LOC, CC, Halstead, MI) and fan-in/fan-out (P1-05)."""

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import radon.complexity as r_cc
import radon.metrics as r_metrics
import radon.raw as r_raw
from tree_sitter import Node, Parser

from app.parsing.parser import PY_LANGUAGE


@dataclass(frozen=True)
class HalsteadMetrics:
    """Halstead software science complexity metrics."""

    h1: int  # Number of distinct operators
    h2: int  # Number of distinct operands
    n1: int  # Total number of operators
    n2: int  # Total number of operands
    vocabulary: int
    length: int
    calculated_length: float
    volume: float
    difficulty: float
    effort: float
    time: float
    bugs: float


@dataclass(frozen=True)
class RawMetrics:
    """Source lines and comments analysis."""

    loc: int  # Total physical lines of code
    lloc: int  # Logical lines of code
    sloc: int  # Source lines of code (excluding blank and pure comments)
    comments: int  # Comments count
    multi: int  # Multi-line strings / docstrings lines
    blank: int  # Blank lines


@dataclass
class FunctionMetrics:
    """Complexity and coupling metrics for an individual function or method."""

    name: str
    full_name: str
    start_line: int
    end_line: int
    loc: int
    cyclomatic_complexity: int
    complexity_rank: str  # 'A' (1-5), 'B' (6-10), 'C' (11-20), 'D' (21-30), 'E' (31-40), 'F' (41+)
    halstead: HalsteadMetrics | None = None
    calls: list[str] = field(default_factory=list)
    fan_in: int = 0
    fan_out: int = 0


@dataclass
class ModuleMetrics:
    """Aggregated complexity and coupling metrics for a file or module."""

    file_path: str
    raw: RawMetrics
    cyclomatic_complexity: int  # Total cyclomatic complexity across functions
    average_complexity: float
    maintainability_index: float
    halstead: HalsteadMetrics
    functions: dict[str, FunctionMetrics] = field(default_factory=dict)
    imported_modules: list[str] = field(default_factory=list)
    fan_in: int = 0
    fan_out: int = 0
    internal_fan_out: int = 0
    external_fan_out: int = 0


@dataclass
class RepoMetricsSummary:
    """Repository-wide metrics summary."""

    modules: dict[str, ModuleMetrics] = field(default_factory=dict)
    total_loc: int = 0
    total_sloc: int = 0
    total_lloc: int = 0
    total_comments: int = 0
    total_blank: int = 0
    avg_cyclomatic_complexity: float = 0.0
    avg_maintainability_index: float = 0.0


def _convert_halstead_report(report: Any) -> HalsteadMetrics:
    """Convert radon HalsteadReport to typed dataclass."""
    return HalsteadMetrics(
        h1=int(report.h1),
        h2=int(report.h2),
        n1=int(report.N1),
        n2=int(report.N2),
        vocabulary=int(report.vocabulary),
        length=int(report.length),
        calculated_length=float(report.calculated_length),
        volume=float(report.volume),
        difficulty=float(report.difficulty),
        effort=float(report.effort),
        time=float(report.time),
        bugs=float(report.bugs),
    )


def extract_function_calls(code: str) -> dict[str, list[str]]:
    """Extract called function/method names for each function in code using Tree-sitter AST."""
    code_bytes = code.encode("utf-8")
    parser = Parser(PY_LANGUAGE)
    tree = parser.parse(code_bytes)

    calls_by_func: dict[str, list[str]] = {}

    def get_calls_in_node(node: Node) -> list[str]:
        found: list[str] = []
        for child in node.children:
            if child.type == "call":
                fn_node = child.child_by_field_name("function")
                if fn_node is not None:
                    call_name = code_bytes[fn_node.start_byte : fn_node.end_byte].decode(
                        errors="replace"
                    )
                    found.append(call_name)
            found.extend(get_calls_in_node(child))
        return found

    def walk_for_funcs(node: Node, parent_name: str | None = None) -> None:
        for child in node.children:
            if child.type == "class_definition":
                name_node = child.child_by_field_name("name")
                cname = (
                    code_bytes[name_node.start_byte : name_node.end_byte].decode(errors="replace")
                    if name_node
                    else "Class"
                )
                body = child.child_by_field_name("body")
                if body:
                    walk_for_funcs(body, parent_name=cname)
            elif child.type == "function_definition":
                name_node = child.child_by_field_name("name")
                if name_node is not None:
                    fname = code_bytes[name_node.start_byte : name_node.end_byte].decode(
                        errors="replace"
                    )
                    full_name = f"{parent_name}.{fname}" if parent_name else fname
                    body = child.child_by_field_name("body")
                    if body:
                        calls = get_calls_in_node(body)
                        calls_by_func[full_name] = calls
                        walk_for_funcs(body, parent_name=full_name)
            elif child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type in ("function_definition", "class_definition"):
                        walk_for_funcs(sub, parent_name=parent_name)
            else:
                if child.children:
                    walk_for_funcs(child, parent_name=parent_name)

    walk_for_funcs(tree.root_node)
    return calls_by_func


def compute_module_metrics(code: str, file_path: str = "module.py") -> ModuleMetrics:
    """Compute raw LOC, cyclomatic complexity, Halstead, MI, and calls for a single module."""
    # 1. Raw metrics via radon
    raw_res = r_raw.analyze(code)
    raw = RawMetrics(
        loc=raw_res.loc,
        lloc=raw_res.lloc,
        sloc=raw_res.sloc,
        comments=raw_res.comments,
        multi=raw_res.multi,
        blank=raw_res.blank,
    )

    # 2. Cyclomatic complexity via radon
    cc_blocks = r_cc.cc_visit(code)
    total_cc = sum(b.complexity for b in cc_blocks)
    avg_cc = float(total_cc / len(cc_blocks)) if cc_blocks else 1.0

    # 3. Halstead metrics via radon
    h_res = r_metrics.h_visit(code)
    halstead = _convert_halstead_report(h_res.total)

    # Halstead per function
    func_h_map: dict[str, HalsteadMetrics] = {}
    for func_entry in h_res.functions:
        if isinstance(func_entry, tuple) and len(func_entry) == 2:
            func_name, func_report = func_entry
            func_h_map[func_name] = _convert_halstead_report(func_report)

    # 4. Maintainability Index via radon
    try:
        mi = float(r_metrics.mi_visit(code, multi=True))
    except (SyntaxError, ValueError, TypeError):
        mi = 100.0

    # 5. Calls per function via AST
    calls_map = extract_function_calls(code)

    # 6. Build FunctionMetrics
    functions: dict[str, FunctionMetrics] = {}
    for block in cc_blocks:
        b_name = block.name
        full_name = f"{block.classname}.{b_name}" if getattr(block, "classname", None) else b_name
        b_calls = calls_map.get(full_name, calls_map.get(b_name, []))
        f_loc = max(1, block.endline - block.lineno + 1)
        f_h = func_h_map.get(b_name, func_h_map.get(full_name))

        functions[full_name] = FunctionMetrics(
            name=b_name,
            full_name=full_name,
            start_line=block.lineno,
            end_line=block.endline,
            loc=f_loc,
            cyclomatic_complexity=block.complexity,
            complexity_rank=r_cc.cc_rank(block.complexity),
            halstead=f_h,
            calls=b_calls,
            fan_out=len(set(b_calls)),
        )

    return ModuleMetrics(
        file_path=file_path,
        raw=raw,
        cyclomatic_complexity=total_cc,
        average_complexity=avg_cc,
        maintainability_index=mi,
        halstead=halstead,
        functions=functions,
    )


def compute_repository_metrics(
    modules_code: dict[str, str],
    modules_imports: dict[str, list[str]] | None = None,
) -> RepoMetricsSummary:
    """Compute repository-wide metrics with exact fan-in and fan-out calculation."""
    summary = RepoMetricsSummary()
    total_loc = 0
    total_sloc = 0
    total_lloc = 0
    total_comments = 0
    total_blank = 0
    total_cc_sum = 0
    mi_sum = 0.0

    module_import_map: dict[str, list[str]] = modules_imports or {}

    # Compute base metrics for each module
    for path_str, code in modules_code.items():
        m_metrics = compute_module_metrics(code, file_path=path_str)
        summary.modules[path_str] = m_metrics
        total_loc += m_metrics.raw.loc
        total_sloc += m_metrics.raw.sloc
        total_lloc += m_metrics.raw.lloc
        total_comments += m_metrics.raw.comments
        total_blank += m_metrics.raw.blank
        total_cc_sum += m_metrics.cyclomatic_complexity
        mi_sum += m_metrics.maintainability_index

    # Normalize known modules for matching: "a.py" -> "a", "pkg/b.py" -> "pkg.b"
    module_keys = set(summary.modules.keys())
    normalized_to_key: dict[str, str] = {}
    for k in module_keys:
        p = Path(k)
        stem = p.stem
        as_dot = ".".join(p.with_suffix("").parts)
        normalized_to_key[stem] = k
        normalized_to_key[as_dot] = k
        normalized_to_key[k] = k

    # Compute Module Fan-In and Fan-Out
    module_fan_in: dict[str, int] = defaultdict(int)

    for path_str, m_metrics in summary.modules.items():
        imports = module_import_map.get(path_str, [])
        m_metrics.imported_modules = imports
        distinct_imports = set(imports)
        m_metrics.fan_out = len(distinct_imports)

        internal_count = 0
        external_count = 0
        for imp in distinct_imports:
            # Check if imported name matches any local module
            matched_key = None
            imp_parts = imp.split(".")
            for i in range(len(imp_parts), 0, -1):
                candidate = ".".join(imp_parts[:i])
                if candidate in normalized_to_key and normalized_to_key[candidate] != path_str:
                    matched_key = normalized_to_key[candidate]
                    break

            if matched_key:
                internal_count += 1
                module_fan_in[matched_key] += 1
            else:
                external_count += 1

        m_metrics.internal_fan_out = internal_count
        m_metrics.external_fan_out = external_count

    for path_str, fan_in_val in module_fan_in.items():
        if path_str in summary.modules:
            summary.modules[path_str].fan_in = fan_in_val

    # Compute Function Fan-In across functions in repository
    all_funcs: dict[str, FunctionMetrics] = {}
    for m in summary.modules.values():
        for fname, fmetric in m.functions.items():
            all_funcs[fname] = fmetric
            # Also register short name if unique
            if fmetric.name not in all_funcs:
                all_funcs[fmetric.name] = fmetric

    func_fan_in: dict[str, int] = defaultdict(int)
    for m in summary.modules.values():
        for fmetric in m.functions.values():
            for called in fmetric.calls:
                called_target = called.split(".")[-1]
                if called in all_funcs:
                    func_fan_in[called] += 1
                elif called_target in all_funcs:
                    func_fan_in[called_target] += 1

    for m in summary.modules.values():
        for fname, fmetric in m.functions.items():
            fmetric.fan_in = func_fan_in.get(fname, func_fan_in.get(fmetric.name, 0))

    mod_count = len(summary.modules)
    summary.total_loc = total_loc
    summary.total_sloc = total_sloc
    summary.total_lloc = total_lloc
    summary.total_comments = total_comments
    summary.total_blank = total_blank
    summary.avg_cyclomatic_complexity = total_cc_sum / mod_count if mod_count else 0.0
    summary.avg_maintainability_index = mi_sum / mod_count if mod_count else 0.0

    return summary
