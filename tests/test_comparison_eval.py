"""Tests verifying embedding models and chunk size comparative evaluation (P2-07)."""

import unittest
from pathlib import Path

import pytest

from evals.retrieval.comparison import RetrievalComparisonExperiment


class TestComparisonEval(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent

    @pytest.mark.asyncio
    async def test_comparison_experiment_runs_successfully(self) -> None:
        experiment = RetrievalComparisonExperiment()
        # Test evaluating two distinct configurations
        s1 = await experiment.evaluate_configuration(
            config_name="Test Symbol Aware",
            chunk_size=1500,
            is_symbol_aware=True,
            dimension=32,
        )
        s2 = await experiment.evaluate_configuration(
            config_name="Test Window Fallback",
            chunk_size=500,
            is_symbol_aware=False,
            dimension=32,
        )

        self.assertGreater(s1.total_chunks, 0)
        self.assertGreater(s2.total_chunks, 0)
        self.assertGreaterEqual(s1.mrr, 0.0)
        self.assertGreaterEqual(s2.mrr, 0.0)
        self.assertLessEqual(s1.mrr, 1.0)
        self.assertLessEqual(s2.mrr, 1.0)

    def test_decision_recorded_in_decisions_file(self) -> None:
        """AC: Decision recorded in docs/DECISIONS.md."""
        decisions_file = self.root_dir / "docs" / "DECISIONS.md"
        content = decisions_file.read_text(encoding="utf-8")

        self.assertIn("P2-07", content)
        self.assertIn("Symbol-aware", content)

    def test_comparison_report_exists_and_valid(self) -> None:
        """AC: Comparative evaluation report exists in docs/eval/."""
        report_file = self.root_dir / "docs" / "eval" / "embedding_chunk_comparison.md"
        self.assertTrue(
            report_file.is_file(), "embedding_chunk_comparison.md must exist"
        )
        content = report_file.read_text(encoding="utf-8")

        self.assertIn("Embedding Models and Chunk Sizes Comparison", content)
        self.assertIn("Recall@1", content)
        self.assertIn("Recall@10", content)
        self.assertIn("MRR", content)
        self.assertIn("Champion Configuration for Production", content)


if __name__ == "__main__":
    unittest.main()
