"""Tests verifying Docker Compose and container definitions (P0-02)."""

import unittest
from pathlib import Path

import yaml


class TestDockerCompose(unittest.TestCase):
    def setUp(self) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent
        self.compose_file = self.root_dir / "docker-compose.yml"

    def test_compose_file_exists_and_valid_yaml(self) -> None:
        self.assertTrue(self.compose_file.is_file(), "docker-compose.yml must exist")
        content = self.compose_file.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        self.assertIsInstance(data, dict, "docker-compose.yml must parse to a dict")
        self.assertIn(
            "services", data, "docker-compose.yml must have a 'services' block"
        )

    def test_all_five_services_present(self) -> None:
        data = yaml.safe_load(self.compose_file.read_text(encoding="utf-8"))
        services = data.get("services", {})
        expected_services = {"api", "worker", "web", "postgres", "redis"}
        self.assertEqual(
            expected_services,
            expected_services.intersection(services.keys()),
            f"Missing services: {expected_services - set(services.keys())}",
        )

    def test_postgres_configuration(self) -> None:
        data = yaml.safe_load(self.compose_file.read_text(encoding="utf-8"))
        pg = data["services"]["postgres"]
        self.assertIn("pgvector", pg["image"], "PostgreSQL must use pgvector image")
        self.assertIn("healthcheck", pg, "Postgres must define a healthcheck")
        test_cmd = str(pg["healthcheck"]["test"])
        self.assertIn(
            "pg_isready", test_cmd, "Postgres healthcheck must run pg_isready"
        )

    def test_redis_configuration(self) -> None:
        data = yaml.safe_load(self.compose_file.read_text(encoding="utf-8"))
        redis = data["services"]["redis"]
        self.assertIn("redis:", redis["image"], "Redis image must be specified")
        self.assertIn("healthcheck", redis, "Redis must define a healthcheck")
        test_cmd = str(redis["healthcheck"]["test"])
        self.assertIn(
            "redis-cli", test_cmd, "Redis healthcheck must run redis-cli ping"
        )

    def test_api_configuration(self) -> None:
        data = yaml.safe_load(self.compose_file.read_text(encoding="utf-8"))
        api = data["services"]["api"]
        self.assertIn("build", api, "API service must define a build configuration")
        self.assertIn("healthcheck", api, "API must define a healthcheck")
        test_cmd = str(api["healthcheck"]["test"])
        self.assertIn("/healthz", test_cmd, "API healthcheck must target /healthz")
        depends = api.get("depends_on", {})
        self.assertIn("postgres", depends, "API must depend on postgres")
        self.assertIn("redis", depends, "API must depend on redis")

    def test_worker_configuration(self) -> None:
        data = yaml.safe_load(self.compose_file.read_text(encoding="utf-8"))
        worker = data["services"]["worker"]
        self.assertIn(
            "build", worker, "Worker service must define a build configuration"
        )
        depends = worker.get("depends_on", {})
        self.assertIn("postgres", depends, "Worker must depend on postgres")
        self.assertIn("redis", depends, "Worker must depend on redis")

    def test_web_configuration(self) -> None:
        data = yaml.safe_load(self.compose_file.read_text(encoding="utf-8"))
        web = data["services"]["web"]
        self.assertIn("build", web, "Web service must define a build configuration")
        self.assertIn("ports", web, "Web service must expose a port")

    def test_dockerfiles_exist(self) -> None:
        for component in ["api", "worker", "web"]:
            dockerfile = self.root_dir / "apps" / component / "Dockerfile"
            self.assertTrue(
                dockerfile.is_file(), f"Missing Dockerfile in apps/{component}"
            )
            content = dockerfile.read_text(encoding="utf-8")
            self.assertIn(
                "FROM ", content, f"Dockerfile in apps/{component} missing FROM"
            )
            self.assertTrue(
                "CMD " in content or "ENTRYPOINT " in content,
                f"Dockerfile in apps/{component} missing CMD or ENTRYPOINT",
            )


if __name__ == "__main__":
    unittest.main()
