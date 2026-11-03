"""Tests verifying repository scaffold and initial configuration (P0-01)."""

from pathlib import Path
import unittest


class TestScaffold(unittest.TestCase):
    def setUp(self) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent

    def test_required_directories_exist(self) -> None:
        required_dirs = [
            "apps/web",
            "apps/api",
            "apps/worker",
            "packages/ml",
            "infra",
            "docs",
        ]
        for rel_path in required_dirs:
            target = self.root_dir / rel_path
            self.assertTrue(
                target.is_dir(),
                f"Expected directory {rel_path} does not exist",
            )

    def test_placeholder_readmes_exist_and_non_empty(self) -> None:
        dirs_with_readme = [
            "apps/web",
            "apps/api",
            "apps/worker",
            "packages/ml",
            "infra",
        ]
        for rel_dir in dirs_with_readme:
            readme_path = self.root_dir / rel_dir / "README.md"
            self.assertTrue(
                readme_path.is_file(),
                f"Missing README.md in {rel_dir}",
            )
            content = readme_path.read_text(encoding="utf-8").strip()
            self.assertGreater(
                len(content),
                0,
                f"README.md in {rel_dir} is empty",
            )

    def test_gitignore_covers_required_categories(self) -> None:
        gitignore_path = self.root_dir / ".gitignore"
        self.assertTrue(gitignore_path.is_file(), ".gitignore must exist")
        content = gitignore_path.read_text(encoding="utf-8")

        # Python
        self.assertIn("__pycache__/", content)
        self.assertIn(".venv/", content)
        self.assertIn(".pytest_cache/", content)

        # Node
        self.assertIn("node_modules/", content)

        # macOS
        self.assertIn(".DS_Store", content)

        # Environment files
        self.assertIn(".env", content)
        self.assertIn("!.env.example", content)

        # Data & models
        self.assertIn("/data/", content)
        self.assertIn("/packages/ml/data/", content)
        self.assertIn("/packages/ml/artifacts/", content)
        lines = [line.strip() for line in content.splitlines()]
        self.assertNotIn("data/", lines)
        self.assertNotIn("models/", lines)
        self.assertIn("*.joblib", content)

    def test_env_example_contains_core_services(self) -> None:
        env_example_path = self.root_dir / ".env.example"
        self.assertTrue(env_example_path.is_file(), ".env.example must exist")
        content = env_example_path.read_text(encoding="utf-8")

        self.assertIn("DATABASE_URL=", content)
        self.assertIn("REDIS_URL=", content)
        self.assertIn("API_PORT=", content)
        self.assertIn("LLM_PROVIDER=", content)

    def test_root_readme_has_overview_and_map(self) -> None:
        readme_path = self.root_dir / "README.md"
        self.assertTrue(readme_path.is_file(), "Root README.md must exist")
        content = readme_path.read_text(encoding="utf-8")

        self.assertIn("RepoPilot AI", content)
        self.assertIn("Folder Map", content)
        self.assertIn("apps/api", content)
        self.assertIn("apps/web", content)
        self.assertIn("apps/worker", content)
        self.assertIn("packages/ml", content)
        self.assertIn("infra", content)
        self.assertIn("Run Steps", content)


if __name__ == "__main__":
    unittest.main()

