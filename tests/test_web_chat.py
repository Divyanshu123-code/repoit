"""Tests verifying Chat UI with expandable evidence panel (P2-06).

Acceptance Criteria:
- Chat UI with expandable evidence panel.
- Hard Rule 5: Every API/UI result labelled by source (llm_generated, static).
"""

import unittest
from pathlib import Path


class TestWebChatUI(unittest.TestCase):
    def setUp(self) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent
        self.web_dir = self.root_dir / "apps" / "web"

    def test_chat_page_file_exists(self) -> None:
        chat_page = self.web_dir / "src" / "pages" / "RepoChatPage.tsx"
        self.assertTrue(chat_page.is_file(), "RepoChatPage.tsx must exist")

    def test_routing_in_app(self) -> None:
        app_file = self.web_dir / "src" / "App.tsx"
        content = app_file.read_text(encoding="utf-8")

        self.assertIn("RepoChatPage", content)
        self.assertIn('path="/repositories/:id/chat"', content)

    def test_overview_page_has_chat_link(self) -> None:
        overview_file = self.web_dir / "src" / "pages" / "RepoOverviewPage.tsx"
        content = overview_file.read_text(encoding="utf-8")

        self.assertIn("/chat", content)
        self.assertIn("Ask AI Assistant", content)

    def test_api_client_rag_methods_and_types(self) -> None:
        client_file = self.web_dir / "src" / "api" / "client.ts"
        content = client_file.read_text(encoding="utf-8")

        self.assertIn("askQuestion", content)
        self.assertIn("searchCode", content)
        self.assertIn("interface RAGResponse", content)
        self.assertIn("interface RAGCitation", content)
        self.assertIn("interface SearchResponse", content)

    def test_expandable_evidence_panel(self) -> None:
        """AC: Chat UI with expandable evidence panel."""
        chat_file = self.web_dir / "src" / "pages" / "RepoChatPage.tsx"
        content = chat_file.read_text(encoding="utf-8")

        # Evidence panel toggle
        self.assertIn("toggleEvidencePanel", content)
        self.assertIn("Evidence & Citations", content)

        # Code excerpt box
        self.assertIn("file_path", content)
        self.assertIn("start_line", content)
        self.assertIn("end_line", content)
        self.assertIn("similarity_score", content)

    def test_rule_5_source_labelling_in_chat(self) -> None:
        """Every API/UI result is labelled by source: static | ml_predicted | graph_derived | llm_generated."""
        chat_file = self.web_dir / "src" / "pages" / "RepoChatPage.tsx"
        content = chat_file.read_text(encoding="utf-8")

        self.assertIn("source: llm_generated", content)
        self.assertIn("source: static", content)

    def test_abstention_handling_in_ui(self) -> None:
        """Abstention warning displayed when model cannot answer from codebase."""
        chat_file = self.web_dir / "src" / "pages" / "RepoChatPage.tsx"
        content = chat_file.read_text(encoding="utf-8")

        self.assertIn("abstained", content)
        self.assertIn("Abstention", content)


if __name__ == "__main__":
    unittest.main()
