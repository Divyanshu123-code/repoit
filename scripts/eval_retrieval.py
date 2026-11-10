#!/usr/bin/env python3
"""CLI script to execute the retrieval evaluation harness and generate docs/eval/retrieval_baseline.md (P2-04)."""

import asyncio
import sys
from pathlib import Path

# Add apps/api and workspace root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "apps" / "api"))
sys.path.insert(0, str(root_dir))

from evals.retrieval.evaluator import RetrievalEvaluator


async def main() -> None:
    evaluator = RetrievalEvaluator()
    print("Running retrieval evaluation harness across 35 benchmark queries...")
    summary = await evaluator.run_evaluation(k_limit=10)

    markdown_report = summary.format_markdown_table()
    print("\n" + markdown_report)

    output_path = root_dir / "docs" / "eval" / "retrieval_baseline.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"# Retrieval Evaluation Baseline (P2-04)\n\n"
        f"Generated automatically by `scripts/eval_retrieval.py`.\n\n"
        f"{markdown_report}\n",
        encoding="utf-8",
    )
    print(f"\nBaseline saved successfully to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
