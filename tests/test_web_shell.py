"""Tests verifying React + TypeScript web shell implementation (P0-05)."""

import json
import unittest
from pathlib import Path


class TestWebShell(unittest.TestCase):
    def setUp(self) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent
        self.web_dir = self.root_dir / "apps" / "web"

    def test_package_json_dependencies(self) -> None:
        pkg_file = self.web_dir / "package.json"
        self.assertTrue(pkg_file.is_file(), "package.json must exist in apps/web")
        pkg = json.loads(pkg_file.read_text(encoding="utf-8"))

        dependencies = pkg.get("dependencies", {})
        dev_dependencies = pkg.get("devDependencies", {})

        self.assertIn("react", dependencies, "react dependency is required")
        self.assertIn("react-dom", dependencies, "react-dom dependency is required")
        self.assertIn(
            "@tanstack/react-query", dependencies, "TanStack React Query is required"
        )
        self.assertIn(
            "react-router-dom", dependencies, "react-router-dom is required for routing"
        )
        self.assertIn("typescript", dev_dependencies, "typescript is required")
        self.assertIn("vite", dev_dependencies, "vite is required")

    def test_tsconfig_has_strict_mode(self) -> None:
        tsconfig_file = self.web_dir / "tsconfig.json"
        self.assertTrue(tsconfig_file.is_file(), "tsconfig.json must exist in apps/web")
        config = json.loads(tsconfig_file.read_text(encoding="utf-8"))
        compiler_options = config.get("compilerOptions", {})
        self.assertTrue(
            compiler_options.get("strict"), "tsconfig must enforce strict: true"
        )

    def test_api_client_and_probes_exist(self) -> None:
        client_file = self.web_dir / "src" / "api" / "client.ts"
        self.assertTrue(client_file.is_file(), "src/api/client.ts must exist")
        content = client_file.read_text(encoding="utf-8")
        self.assertIn("fetchHealthz", content)
        self.assertIn("fetchReadyz", content)
        self.assertIn("/healthz", content)
        self.assertIn("/readyz", content)

    def test_health_page_and_app_routing(self) -> None:
        health_page = self.web_dir / "src" / "pages" / "HealthPage.tsx"
        self.assertTrue(
            health_page.is_file(), "src/pages/HealthPage.tsx must exist to show health"
        )
        health_content = health_page.read_text(encoding="utf-8")
        self.assertIn("useQuery", health_content)
        self.assertIn("healthz", health_content)
        self.assertIn("readyz", health_content)

        app_file = self.web_dir / "src" / "App.tsx"
        self.assertTrue(app_file.is_file(), "src/App.tsx must exist")
        app_content = app_file.read_text(encoding="utf-8")
        self.assertIn("Routes", app_content)
        self.assertIn("HealthPage", app_content)

    def test_dockerfile_multi_stage_build(self) -> None:
        dockerfile = self.web_dir / "Dockerfile"
        self.assertTrue(dockerfile.is_file(), "apps/web/Dockerfile must exist")
        content = dockerfile.read_text(encoding="utf-8")
        self.assertIn("FROM node", content)
        self.assertIn("npm run build", content)
        self.assertIn("FROM nginx", content)


if __name__ == "__main__":
    unittest.main()
