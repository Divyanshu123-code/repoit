"""Unit tests for radon code metrics and fan-in/fan-out coupling (P1-05)."""

import pytest

from app.parsing import (
    compute_module_metrics,
    compute_repository_metrics,
    extract_function_calls,
)

# Hand-computed fixture 1: Linear function with predictable metrics
LINEAR_FIXTURE_CODE = """def linear_func(x):
    # Single comment
    y = x + 1
    return y
"""

# Hand-computed fixture 2: Branching function with CC = 4
BRANCHING_FIXTURE_CODE = """def branch_func(a, b):
    # Positivity checks
    if a > 0 and b > 0:
        return a + b
    elif a < 0:
        return -a
    else:
        return b
"""

# Hand-computed fixture 3: Call graph with known fan-in / fan-out
COUPLING_FIXTURE_CODE = """def func_c():
    return 42

def func_b():
    return func_c() + 1

def func_a():
    x = func_b()
    y = func_c()
    return x + y
"""


def test_hand_computed_linear_metrics() -> None:
    """Verify raw and CC metrics match hand-computed expectations for linear code."""
    metrics = compute_module_metrics(LINEAR_FIXTURE_CODE, file_path="linear.py")

    # Hand-computed raw metrics:
    # 4 lines total: def, comment, y=x+1, return y
    assert metrics.raw.loc == 4
    assert metrics.raw.comments == 1
    assert metrics.raw.blank == 0
    assert metrics.raw.sloc == 3
    assert metrics.raw.lloc == 3

    # Hand-computed CC:
    # 1 execution path -> CC = 1
    assert metrics.cyclomatic_complexity == 1
    assert metrics.average_complexity == 1.0
    assert "linear_func" in metrics.functions
    f = metrics.functions["linear_func"]
    assert f.cyclomatic_complexity == 1
    assert f.complexity_rank == "A"
    assert f.calls == []
    assert f.fan_out == 0


def test_hand_computed_branching_metrics() -> None:
    """Verify cyclomatic complexity matches hand-computed branches."""
    metrics = compute_module_metrics(BRANCHING_FIXTURE_CODE, file_path="branch.py")

    # Hand-computed CC:
    # base = 1
    # if a > 0 (+1)
    # and b > 0 (+1)
    # elif a < 0 (+1)
    # Total = 4
    assert metrics.cyclomatic_complexity == 4
    f = metrics.functions["branch_func"]
    assert f.cyclomatic_complexity == 4
    assert f.complexity_rank == "A"


def test_hand_computed_halstead_properties() -> None:
    """Verify mathematical identities of Halstead metrics on fixture."""
    metrics = compute_module_metrics(BRANCHING_FIXTURE_CODE)
    h = metrics.halstead

    # Halstead formulas verification
    assert h.h1 > 0  # distinct operators
    assert h.h2 > 0  # distinct operands
    assert h.n1 > 0  # total operators
    assert h.n2 > 0  # total operands
    assert h.vocabulary == h.h1 + h.h2
    assert h.length == h.n1 + h.n2
    assert h.volume > 0.0
    assert h.difficulty > 0.0
    assert h.effort == pytest.approx(h.difficulty * h.volume, rel=1e-3)


def test_hand_computed_function_coupling() -> None:
    """Verify function-level fan-in and fan-out match hand-computed call graph."""
    # Hand-computed call graph:
    # func_a calls func_b, func_c  -> fan_out=2, fan_in=0
    # func_b calls func_c          -> fan_out=1, fan_in=1 (from func_a)
    # func_c calls nobody          -> fan_out=0, fan_in=2 (from func_a and func_b)
    calls = extract_function_calls(COUPLING_FIXTURE_CODE)
    assert set(calls["func_a"]) == {"func_b", "func_c"}
    assert set(calls["func_b"]) == {"func_c"}
    assert calls["func_c"] == []

    summary = compute_repository_metrics(
        modules_code={"coupling.py": COUPLING_FIXTURE_CODE},
        modules_imports={"coupling.py": []},
    )
    mod = summary.modules["coupling.py"]

    fa = mod.functions["func_a"]
    fb = mod.functions["func_b"]
    fc = mod.functions["func_c"]

    assert fa.fan_out == 2
    assert fa.fan_in == 0

    assert fb.fan_out == 1
    assert fb.fan_in == 1

    assert fc.fan_out == 0
    assert fc.fan_in == 2


def test_hand_computed_module_fan_in_and_fan_out() -> None:
    """Verify module-level fan-in and fan-out match hand-computed dependency graph."""
    # Hand-computed dependency graph:
    # alpha.py imports: beta, gamma, math (2 internal, 1 external) -> fan_out=3, fan_in=0
    # beta.py  imports: gamma              (1 internal, 0 external) -> fan_out=1, fan_in=1
    # gamma.py imports: sys                (0 internal, 1 external) -> fan_out=1, fan_in=2
    modules_code = {
        "alpha.py": "import beta\nimport gamma\nimport math\n",
        "beta.py": "import gamma\n",
        "gamma.py": "import sys\n",
    }
    modules_imports = {
        "alpha.py": ["beta", "gamma", "math"],
        "beta.py": ["gamma"],
        "gamma.py": ["sys"],
    }

    summary = compute_repository_metrics(modules_code, modules_imports)

    alpha = summary.modules["alpha.py"]
    beta = summary.modules["beta.py"]
    gamma = summary.modules["gamma.py"]

    # Alpha
    assert alpha.fan_out == 3
    assert alpha.internal_fan_out == 2
    assert alpha.external_fan_out == 1
    assert alpha.fan_in == 0

    # Beta
    assert beta.fan_out == 1
    assert beta.internal_fan_out == 1
    assert beta.external_fan_out == 0
    assert beta.fan_in == 1

    # Gamma
    assert gamma.fan_out == 1
    assert gamma.internal_fan_out == 0
    assert gamma.external_fan_out == 1
    assert gamma.fan_in == 2

    # Overall totals
    assert summary.total_loc == 5
    assert len(summary.modules) == 3
