"""Tests verifying GitHub Actions CI workflow (P0-04)."""

import unittest
from pathlib import Path

import yaml


class TestCIWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent
        self.workflow_file = self.root_dir / ".github" / "workflows" / "ci.yml"

    def test_workflow_file_exists_and_valid_yaml(self) -> None:
        self.assertTrue(self.workflow_file.is_file(), "ci.yml workflow must exist")
        data = yaml.safe_load(self.workflow_file.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict, "ci.yml must parse to a dictionary")
        self.assertEqual(data.get("name"), "CI")

    def test_workflow_triggers_on_push_and_pr(self) -> None:
        data = yaml.safe_load(self.workflow_file.read_text(encoding="utf-8"))
        # yaml.safe_load parses unquoted `on:` as boolean True if not special-cased
        triggers = data.get("on") or data.get(True)
        self.assertIsNotNone(triggers, "Workflow must define triggers")
        self.assertIn("push", triggers, "Workflow must trigger on push")
        self.assertIn("pull_request", triggers, "Workflow must trigger on pull_request")

    def test_workflow_has_required_jobs(self) -> None:
        data = yaml.safe_load(self.workflow_file.read_text(encoding="utf-8"))
        jobs = data.get("jobs", {})
        expected_jobs = {"lint", "typecheck", "test", "web-build"}
        self.assertEqual(
            expected_jobs,
            expected_jobs.intersection(jobs.keys()),
            f"Missing CI jobs: {expected_jobs - set(jobs.keys())}",
        )

    def test_lint_job_runs_ruff(self) -> None:
        data = yaml.safe_load(self.workflow_file.read_text(encoding="utf-8"))
        lint_steps = data["jobs"]["lint"]["steps"]
        commands = " ".join(step.get("run", "") for step in lint_steps)
        self.assertIn("ruff check", commands)
        self.assertIn("ruff format", commands)

    def test_typecheck_job_runs_mypy_strict(self) -> None:
        data = yaml.safe_load(self.workflow_file.read_text(encoding="utf-8"))
        typecheck_steps = data["jobs"]["typecheck"]["steps"]
        commands = " ".join(step.get("run", "") for step in typecheck_steps)
        self.assertIn("mypy --strict", commands)

    def test_test_job_runs_pytest(self) -> None:
        data = yaml.safe_load(self.workflow_file.read_text(encoding="utf-8"))
        test_steps = data["jobs"]["test"]["steps"]
        commands = " ".join(step.get("run", "") for step in test_steps)
        self.assertIn("pytest", commands)

    def test_web_build_job_builds_image(self) -> None:
        data = yaml.safe_load(self.workflow_file.read_text(encoding="utf-8"))
        web_steps = data["jobs"]["web-build"]["steps"]
        commands = " ".join(step.get("run", "") for step in web_steps)
        self.assertIn("docker build", commands)


if __name__ == "__main__":
    unittest.main()
