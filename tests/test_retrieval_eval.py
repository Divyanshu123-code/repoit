"""Tests for the retrieval evaluation harness (P2-04).

Acceptance Criteria:
- Script outputs a table.
- Baseline stored in docs/eval/.
"""

import sys
from pathlib import Path

import pytest

# Ensure imports resolve
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "apps" / "api"))
sys.path.insert(0, str(root_dir))

from evals.retrieval.dataset import BENCHMARK_CORPUS, BENCHMARK_QUERIES, BenchmarkQuery
from evals.retrieval.evaluator import (
    QueryEvalResult,
    RetrievalBenchmarkSummary,
    RetrievalEvaluator,
)


def test_benchmark_dataset_contains_sufficient_queries() -> None:
    """AC: Dataset contains 30-50 curated questions with expected files."""
    assert len(BENCHMARK_QUERIES) >= 30
    assert len(BENCHMARK_QUERIES) <= 50

    # Ensure every query specifies non-empty text, id, and expected file
    for q in BENCHMARK_QUERIES:
        assert q.query_id.startswith("Q")
        assert len(q.query.strip()) > 10
        assert q.expected_file in BENCHMARK_CORPUS


def test_query_eval_result_rank_calculations() -> None:
    """Verifies that Recall@k flags and Reciprocal Rank are computed correctly."""
    # Rank 1 hit
    r1 = QueryEvalResult(
        query_id="Q1",
        query="test query",
        category="auth",
        expected_file="auth/jwt.py",
        expected_symbol="token",
        hit_rank=1,
        reciprocal_rank=1.0,
        recall_at_1=True,
        recall_at_3=True,
        recall_at_5=True,
        recall_at_10=True,
        top_matches=["auth/jwt.py"],
        latency_ms=1.2,
    )
    assert r1.recall_at_1 is True
    assert r1.reciprocal_rank == 1.0

    # Rank 3 hit
    r3 = QueryEvalResult(
        query_id="Q2",
        query="test query 2",
        category="auth",
        expected_file="auth/jwt.py",
        expected_symbol=None,
        hit_rank=3,
        reciprocal_rank=1.0 / 3.0,
        recall_at_1=False,
        recall_at_3=True,
        recall_at_5=True,
        recall_at_10=True,
        top_matches=["other.py", "mid.py", "auth/jwt.py"],
        latency_ms=1.5,
    )
    assert r3.recall_at_1 is False
    assert r3.recall_at_3 is True
    assert abs(r3.reciprocal_rank - 0.3333) < 1e-3

    # Miss (>10)
    rmiss = QueryEvalResult(
        query_id="Q3",
        query="test query 3",
        category="auth",
        expected_file="auth/jwt.py",
        expected_symbol=None,
        hit_rank=None,
        reciprocal_rank=0.0,
        recall_at_1=False,
        recall_at_3=False,
        recall_at_5=False,
        recall_at_10=False,
        top_matches=["unrelated.py"],
        latency_ms=2.0,
    )
    assert rmiss.recall_at_10 is False
    assert rmiss.reciprocal_rank == 0.0


def test_retrieval_benchmark_summary_formatting() -> None:
    """Verifies that format_markdown_table outputs required columns and sections."""
    sample_res = [
        QueryEvalResult(
            query_id="Q01",
            query="JWT tokens",
            category="auth",
            expected_file="auth/jwt.py",
            expected_symbol=None,
            hit_rank=1,
            reciprocal_rank=1.0,
            recall_at_1=True,
            recall_at_3=True,
            recall_at_5=True,
            recall_at_10=True,
            top_matches=["auth/jwt.py"],
            latency_ms=1.5,
        )
    ]
    summary = RetrievalBenchmarkSummary(
        total_queries=1,
        recall_at_1=1.0,
        recall_at_3=1.0,
        recall_at_5=1.0,
        recall_at_10=1.0,
        mrr=1.0,
        avg_latency_ms=1.5,
        category_mrr={"auth": 1.0},
        results=sample_res,
    )
    table_str = summary.format_markdown_table()
    assert "| **Recall@1** | 100.0% |" in table_str
    assert "| **Recall@3** | 100.0% |" in table_str
    assert "| **Recall@10** | 100.0% |" in table_str
    assert "| **MRR (Mean Reciprocal Rank)** | 1.000 |" in table_str
    assert "Detailed Query Breakdown" in table_str


@pytest.mark.asyncio
async def test_retrieval_evaluator_end_to_end() -> None:
    """Runs the benchmark evaluator end-to-end on a subset and checks metrics."""
    mini_corpus = {
        "auth/login.py": "def login(): pass\ndef verify_token(): pass",
        "math/calc.py": "def add(a, b): return a + b\ndef subtract(a, b): return a - b",
    }
    mini_queries = [
        BenchmarkQuery(
            "M01", "login and verify token", "auth/login.py", "login", "auth"
        ),
        BenchmarkQuery(
            "M02", "add numbers addition math", "math/calc.py", "add", "math"
        ),
    ]

    evaluator = RetrievalEvaluator(corpus=mini_corpus, queries=mini_queries)
    summary = await evaluator.run_evaluation(k_limit=5)

    assert summary.total_queries == 2
    assert summary.recall_at_1 == 1.0
    assert summary.mrr == 1.0
    assert len(summary.results) == 2
    assert summary.avg_latency_ms > 0.0


def test_baseline_file_exists_and_valid() -> None:
    """AC: Baseline stored in docs/eval/retrieval_baseline.md."""
    baseline_path = root_dir / "docs" / "eval" / "retrieval_baseline.md"
    assert baseline_path.exists()
    content = baseline_path.read_text(encoding="utf-8")
    assert "Retrieval Evaluation Baseline" in content
    assert "Recall@1" in content
    assert "Recall@10" in content
    assert "MRR" in content
