"""Tests verifying architectural decisions lock (P0-06)."""

import unittest
from pathlib import Path


class TestDecisions(unittest.TestCase):
    def setUp(self) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent
        self.decisions_file = self.root_dir / "docs" / "DECISIONS.md"

    def test_decisions_file_exists(self) -> None:
        self.assertTrue(
            self.decisions_file.is_file(),
            "docs/DECISIONS.md must exist",
        )

    def test_no_open_decisions_remain(self) -> None:
        content = self.decisions_file.read_text(encoding="utf-8")
        self.assertNotIn(
            "## Open decisions",
            content,
            "No 'Open decisions' section should remain in docs/DECISIONS.md",
        )
        self.assertIn(
            "No open items remain",
            content,
            "docs/DECISIONS.md must explicitly confirm no open items remain",
        )

    def test_all_phase_0_decisions_locked_in_table(self) -> None:
        content = self.decisions_file.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("|")
        ]
        # Table rows start with '| <num> |' (skipping header and separator lines)
        data_rows = [row for row in lines if row.split("|")[1].strip().isdigit()]

        self.assertGreaterEqual(
            len(data_rows),
            14,
            f"Expected at least 14 locked decisions, found {len(data_rows)}",
        )

        # Check key locked topics from Phase 0
        self.assertIn("gpt-4o-mini", content, "LLM provider decision must be locked")
        self.assertIn(
            "text-embedding-3-small", content, "Embedding model decision must be locked"
        )
        self.assertIn("Arq", content, "Job queue decision (Arq) must be locked")
        self.assertIn("GitHub OAuth", content, "Auth decision must be locked")
        self.assertIn(
            "Deployment target", content, "Deployment target decision must be locked"
        )


if __name__ == "__main__":
    unittest.main()
