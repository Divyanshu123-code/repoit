"""Tests verifying Repository Overview UI and live scan progress (P1-07)."""

import unittest
from pathlib import Path


class TestWebRepoOverview(unittest.TestCase):
    def setUp(self) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent
        self.web_dir = self.root_dir / "apps" / "web"

    def test_pages_and_components_exist(self) -> None:
        repos_page = self.web_dir / "src" / "pages" / "RepositoriesPage.tsx"
        overview_page = self.web_dir / "src" / "pages" / "RepoOverviewPage.tsx"

        self.assertTrue(repos_page.is_file(), "RepositoriesPage.tsx must exist")
        self.assertTrue(overview_page.is_file(), "RepoOverviewPage.tsx must exist")

    def test_routing_in_app(self) -> None:
        app_file = self.web_dir / "src" / "App.tsx"
        content = app_file.read_text(encoding="utf-8")

        self.assertIn("RepositoriesPage", content)
        self.assertIn("RepoOverviewPage", content)
        self.assertIn('path="/"', content)
        self.assertIn('path="/repositories/:id"', content)

    def test_api_client_scan_methods(self) -> None:
        client_file = self.web_dir / "src" / "api" / "client.ts"
        content = client_file.read_text(encoding="utf-8")

        self.assertIn("fetchRepositories", content)
        self.assertIn("fetchRepository", content)
        self.assertIn("registerRepository", content)
        self.assertIn("uploadRepositoryZip", content)
        self.assertIn("triggerScan", content)
        self.assertIn("fetchLatestScan", content)
        self.assertIn("fetchScans", content)

    def test_live_scan_progress_and_stages(self) -> None:
        overview_page = self.web_dir / "src" / "pages" / "RepoOverviewPage.tsx"
        content = overview_page.read_text(encoding="utf-8")

        # Acceptance Criteria: shows scan progress live
        self.assertIn("refetchInterval", content)
        self.assertIn("isScanning", content)

        # Pipeline stages in stepper
        self.assertIn("fetching", content)
        self.assertIn("filtering", content)
        self.assertIn("parsing", content)
        self.assertIn("metrics", content)
        self.assertIn("completed", content)

        # Failure display
        self.assertIn("error_message", content)

    def test_rule_5_source_labelling(self) -> None:
        """Every API/UI result is labelled by source: static | ml_predicted | graph_derived | llm_generated."""
        overview_page = self.web_dir / "src" / "pages" / "RepoOverviewPage.tsx"
        content = overview_page.read_text(encoding="utf-8")
        self.assertIn("source: static", content)


if __name__ == "__main__":
    unittest.main()
