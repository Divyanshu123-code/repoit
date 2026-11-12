"""Ruff static analysis runner and finding normalizer (P4-01).

Executes Ruff in an isolated sandbox with no user code execution,
and maps findings into a normalized schema satisfying:
- Hard Rule 3: Repository content is untrusted input (isolated run, no execution).
- Hard Rule 5: Source labelled strictly as 'static'.
- P4-01 Criteria: findings stored with rule, severity, line.
"""

import ast
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

FindingSeverity = Literal["error", "warning", "info"]
FindingCategory = Literal["security", "syntax", "complexity", "bugrisk", "style", "lint"]

logger = logging.getLogger("repopilot.static.runner")

# Common rule prefixes mapped to categories and default severities
RULE_MAPPINGS: dict[str, tuple[str, FindingSeverity]] = {
    # Security (bandit)
    "S": ("security", "error"),
    # Pyflakes syntax and fatal runtime errors
    "F821": ("syntax", "error"),  # Undefined name
    "F706": ("syntax", "error"),  # Return outside function
    "F632": ("syntax", "error"),  # Use == instead of is
    "F401": ("lint", "info"),  # Unused import
    "F841": ("lint", "info"),  # Unused variable
    "F": ("bugrisk", "error"),
    # Bugbear
    "B": ("bugrisk", "warning"),
    # Async
    "ASYNC": ("bugrisk", "warning"),
    # Complexity
    "C90": ("complexity", "warning"),
    "PLR09": ("complexity", "warning"),
    # Pycodestyle
    "E9": ("syntax", "error"),
    "E": ("style", "warning"),
    "W": ("style", "warning"),
    # Isort & Docstrings
    "I": ("style", "info"),
    "D": ("style", "info"),
    # Type checking
    "ANN": ("style", "info"),
    "UP": ("style", "info"),
}


def classify_rule(rule_code: str) -> tuple[str, FindingSeverity]:
    """Map a linter rule code (e.g., 'F401', 'S101', 'B008') to normalized category and severity."""
    code = rule_code.strip().upper()

    # Exact match first
    if code in RULE_MAPPINGS:
        return RULE_MAPPINGS[code]

    # Prefix match (longest prefix first)
    for prefix in sorted(RULE_MAPPINGS.keys(), key=len, reverse=True):
        if code.startswith(prefix):
            return RULE_MAPPINGS[prefix]

    return ("lint", "warning")


@dataclass(frozen=True)
class NormalizedFinding:
    """Normalized representation of a static analysis finding."""

    file_path: str
    rule: str
    category: str
    severity: FindingSeverity
    message: str
    line_start: int
    line_end: int
    column_start: int | None = None
    column_end: int | None = None
    rule_url: str | None = None
    fix_available: bool = False
    fix_message: str | None = None
    source: str = "static"  # Hard Rule 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "rule": self.rule,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "column_start": self.column_start,
            "column_end": self.column_end,
            "rule_url": self.rule_url,
            "fix_available": self.fix_available,
            "fix_message": self.fix_message,
            "source": self.source,
        }


def normalize_ruff_json(
    raw_json: str | list[dict[str, Any]],
    base_dir: Path | str | None = None,
) -> list[NormalizedFinding]:
    """Parse and normalize raw Ruff JSON diagnostic output into NormalizedFinding records.

    Args:
        raw_json: Raw JSON string or parsed JSON list from `ruff check --output-format=json`.
        base_dir: Optional base directory to make file paths cleanly relative.

    Returns:
        List of NormalizedFinding objects.
    """
    if isinstance(raw_json, str):
        if not raw_json.strip():
            return []
        try:
            items: list[dict[str, Any]] = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to decode Ruff JSON output: %s", exc)
            return []
    else:
        items = raw_json

    base_path = Path(base_dir).resolve() if base_dir is not None else None
    normalized: list[NormalizedFinding] = []

    for item in items:
        rule = str(item.get("code") or item.get("name") or "UNKNOWN")
        msg = str(item.get("message") or "")
        filename = str(item.get("filename") or "")

        # Normalize file path relative to repo root
        if base_path is not None:
            try:
                rel_path = str(Path(filename).resolve().relative_to(base_path))
            except ValueError:
                rel_path = filename
        else:
            rel_path = filename

        # Ensure forward slashes
        rel_path = rel_path.replace("\\", "/")

        # Line and column locations
        loc = item.get("location") or {}
        end_loc = item.get("end_location") or {}
        line_start = int(loc.get("row") or 1)
        line_end = int(end_loc.get("row") or line_start)
        col_start = int(loc["column"]) if "column" in loc else None
        col_end = int(end_loc["column"]) if "column" in end_loc else None

        category, severity = classify_rule(rule)

        # Fix metadata
        fix = item.get("fix")
        fix_available = fix is not None
        fix_msg = fix.get("message") if isinstance(fix, dict) else None

        rule_url = item.get("url")

        normalized.append(
            NormalizedFinding(
                file_path=rel_path,
                rule=rule,
                category=category,
                severity=severity,
                message=msg,
                line_start=line_start,
                line_end=line_end,
                column_start=col_start,
                column_end=col_end,
                rule_url=rule_url,
                fix_available=fix_available,
                fix_message=fix_msg,
                source="static",  # Hard Rule 5
            )
        )

    return normalized


def resolve_ruff_binary() -> str:
    """Find the path to the ruff executable."""
    env_ruff = os.getenv("RUFF_BINARY_PATH")
    if env_ruff and Path(env_ruff).exists():
        return env_ruff

    # Check venv executable
    venv_ruff = Path(sys.executable).parent / "ruff"
    if venv_ruff.exists():
        return str(venv_ruff)

    # Check system PATH
    sys_path_ruff = shutil.which("ruff")
    if sys_path_ruff:
        return sys_path_ruff

    return "ruff"


def run_ruff_check(
    target_path: Path | str,
    timeout_seconds: int = 45,
    select_rules: list[str] | None = None,
) -> list[NormalizedFinding]:
    """Execute Ruff linter safely with --isolated flag (no user code execution).

    Args:
        target_path: Directory or file to scan.
        timeout_seconds: Subprocess execution timeout in seconds.
        select_rules: Optional list of rule codes to enable (e.g. ['E', 'F', 'B', 'S']).

    Returns:
        List of NormalizedFinding objects.
    """
    path_obj = Path(target_path).resolve()
    if not path_obj.exists():
        logger.warning("Target path does not exist for static analysis: %s", target_path)
        return []

    ruff_bin = resolve_ruff_binary()

    # Rule selection: enable core correctness, bugs, style, and security
    # E: pycodestyle errors, F: pyflakes, B: bugbear, S: bandit (security), C90: mccabe
    rules = ",".join(select_rules) if select_rules else "E,F,B,S,C90"

    cmd = [
        ruff_bin,
        "check",
        "--output-format=json",
        "--isolated",  # Hard Rule 3: Do not load untrusted repo config
        "--no-cache",
        f"--select={rules}",
        str(path_obj),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return normalize_ruff_json(proc.stdout, base_dir=path_obj)
    except FileNotFoundError:
        logger.warning("Ruff binary '%s' not found. Falling back to AST static check.", ruff_bin)
        return fallback_ast_check(path_obj)
    except subprocess.TimeoutExpired:
        logger.error(
            "Ruff static check timed out after %d seconds on %s", timeout_seconds, target_path
        )
        return []
    except Exception as exc:  # noqa: BLE001
        logger.error("Error executing Ruff check: %s. Falling back to AST check.", exc)
        return fallback_ast_check(path_obj)


def fallback_ast_check(target_dir: Path) -> list[NormalizedFinding]:
    """Resilient fallback AST static scan when ruff binary is unavailable."""
    findings: list[NormalizedFinding] = []

    files: list[Path] = []
    if target_dir.is_file() and target_dir.suffix == ".py":
        files = [target_dir]
    elif target_dir.is_dir():
        files = list(target_dir.rglob("*.py"))

    for f_path in files:
        try:
            rel_path = str(f_path.relative_to(target_dir)).replace("\\", "/")
        except ValueError:
            rel_path = f_path.name

        try:
            content = f_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(f_path))

            for node in ast.walk(tree):
                # Detect bare except
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    findings.append(
                        NormalizedFinding(
                            file_path=rel_path,
                            rule="B001",
                            category="bugrisk",
                            severity="warning",
                            message="Do not use bare `except:`, it also catches SystemExit and KeyboardInterrupt",
                            line_start=node.lineno,
                            line_end=node.end_lineno or node.lineno,
                            source="static",
                        )
                    )
                # Detect assert statements in production code
                elif isinstance(node, ast.Assert):
                    findings.append(
                        NormalizedFinding(
                            file_path=rel_path,
                            rule="S101",
                            category="security",
                            severity="error",
                            message="Use of `assert` detected. Asserts are removed in optimized bytecode.",
                            line_start=node.lineno,
                            line_end=node.end_lineno or node.lineno,
                            source="static",
                        )
                    )
        except SyntaxError as syn_err:
            findings.append(
                NormalizedFinding(
                    file_path=rel_path,
                    rule="E999",
                    category="syntax",
                    severity="error",
                    message=f"SyntaxError: {syn_err.msg}",
                    line_start=syn_err.lineno or 1,
                    line_end=syn_err.lineno or 1,
                    source="static",
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to AST parse file %s: %s", f_path, exc)

    return findings
