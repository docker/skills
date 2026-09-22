import tempfile
import unittest
from pathlib import Path

import yaml

from compose_assets import discover_compose_assets, validate_compose_asset, validate_compose_assets


class ComposeAssetTests(unittest.TestCase):
    def validate(self, service):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compose.yaml"
            return validate_compose_asset(path, {"services": {"app": service}}, directory)

    def assert_error(self, service, text):
        errors = self.validate(service)
        self.assertTrue(any(text in error for error in errors), errors)
        self.assertTrue(all("service 'app'" in error for error in errors), errors)

    def test_literal_credentials_in_mapping_and_list_environment_fail(self):
        for environment, key in (
            ({"DB_PASSWORD": "literal"}, "DB_PASSWORD"),
            ({"SERVICE_PASSWD": "literal"}, "SERVICE_PASSWD"),
            ({"CLIENT_SECRET": "literal"}, "CLIENT_SECRET"),
            ({"ACCESS_TOKEN": "literal"}, "ACCESS_TOKEN"),
            (["VENDOR_API_KEY=literal"], "VENDOR_API_KEY"),
        ):
            with self.subTest(key=key):
                self.assert_error({"environment": environment}, f"key '{key}' has a nonempty literal credential")

    def test_interpolation_empty_file_and_database_flags_are_allowed(self):
        environment = {
            "DB_PASSWORD": "${DB_PASSWORD:-dev}",
            "ACCESS_TOKEN": "$ACCESS_TOKEN",
            "CLIENT_SECRET": "",
            "VENDOR_API_KEY": None,
            "DB_PASSWORD_FILE": "/run/secrets/password",
            "MYSQL_ALLOW_EMPTY_PASSWORD": "yes",
            "MYSQL_RANDOM_ROOT_PASSWORD": "yes",
            "MARIADB_ALLOW_EMPTY_PASSWORD": "yes",
            "MARIADB_ALLOW_EMPTY_ROOT_PASSWORD": "yes",
            "MARIADB_RANDOM_ROOT_PASSWORD": "yes",
        }
        self.assertEqual(self.validate({"environment": environment}), [])
        self.assertEqual(self.validate({"environment": ["DB_PASSWORD", "ACCESS_TOKEN="]}), [])

    def test_literal_url_password_fails_under_any_environment_key(self):
        self.assert_error(
            {"environment": {"DATABASE_URL": "postgres://user:[REDACTED]@db:5432/app"}},
            "key 'DATABASE_URL' contains a literal password in URL userinfo",
        )

    def test_interpolated_or_passwordless_urls_are_allowed(self):
        for url in (
            "postgres://user:${DB_PASSWORD:-dev}@db:5432/app",
            "postgres://user:$DB_PASSWORD@db:5432/app",
            "postgres://user@db:5432/app",
            "redis://cache:6379/0",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.validate({"environment": {"DATABASE_URL": url}}), [])

    def test_unbound_datastore_ports_fail_in_short_and_long_syntax(self):
        ports = [
            "5432:5432",
            "0.0.0.0:3306:3306",
            "[::]:6379:6379",
            {"target": 27017, "published": 27017},
            {"target": 11211, "published": "11211", "host_ip": "0.0.0.0"},
            {"target": "5672", "published": 5672, "host_ip": "::"},
            "9200:9200/tcp",
            "5432",
        ]
        errors = self.validate({"ports": ports})
        self.assertEqual(len(errors), len(ports), errors)
        self.assertTrue(all("publishes datastore port" in error for error in errors))

    def test_loopback_non_datastore_unpublished_and_interpolated_ports_are_allowed(self):
        ports = [
            "127.0.0.1:5432:5432",
            "[::1]:6379:6379",
            "8080:8080",
            {"target": 3306},
            {"target": 27017, "published": 27017, "host_ip": "127.0.0.1"},
            "${POSTGRES_PORT:-5432}:5432",
            {"target": 9200, "published": "${ELASTIC_PORT:-9200}"},
        ]
        self.assertEqual(self.validate({"ports": ports}), [])

    def test_image_requires_explicit_non_latest_tag_or_digest(self):
        for image in ("postgres", "registry.example:5000/team/postgres", "postgres:latest", "postgres:"):
            with self.subTest(image=image):
                self.assert_error({"image": image}, "image")
        for image in ("postgres:17", "redis:7-alpine", "registry.example:5000/team/app:1", "app@sha256:abc"):
            with self.subTest(image=image):
                self.assertEqual(self.validate({"image": image}), [])
        self.assertEqual(self.validate({"build": "."}), [])

    def test_docker_socket_mount_fails_in_short_and_long_syntax(self):
        for volume in (
            "/var/run/docker.sock:/var/run/docker.sock",
            "/var/run/docker.sock:/var/run/docker.sock:ro",
            "/run/docker.sock:/var/run/docker.sock:ro",
            "type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock",
            {"type": "bind", "source": "/var/run/docker.sock", "target": "/var/run/docker.sock"},
            {"type": "bind", "src": "/var/run/docker.sock", "dst": "/var/run/docker.sock"},
        ):
            with self.subTest(volume=volume):
                self.assert_error({"volumes": [volume]}, "mounts /var/run/docker.sock")

    def test_other_bind_mounts_and_named_volumes_are_allowed(self):
        volumes = [
            "./src:/app/src",
            "db-data:/var/lib/postgresql/data",
            {"type": "bind", "source": "./src", "target": "/app/src"},
        ]
        self.assertEqual(self.validate({"volumes": volumes}), [])

    def test_discovery_only_returns_compose_mappings_from_yaml_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "skills" / "example" / "assets"
            assets.mkdir(parents=True)
            (assets / "compose.yaml").write_text("services:\n  app:\n    image: app:1\n", encoding="utf-8")
            (assets / "compose.yml").write_text("services:\n  app:\n    build: .\n", encoding="utf-8")
            (assets / "metadata.yaml").write_text("name: example\n", encoding="utf-8")
            (assets / "example.md").write_text("services:\n  bad:\n    image: app:latest\n", encoding="utf-8")
            (root / "skills" / "outside.yaml").write_text("services: {}\n", encoding="utf-8")

            discovered, errors = discover_compose_assets(root)
            self.assertEqual(errors, [])
            self.assertEqual([path.name for path, _ in discovered], ["compose.yaml", "compose.yml"])

    def test_parse_errors_are_reported_with_a_fix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "skills" / "example" / "assets"
            assets.mkdir(parents=True)
            (assets / "broken.yaml").write_text("services: [\n", encoding="utf-8")
            discovered, errors = discover_compose_assets(root)
            self.assertEqual(discovered, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("skills/example/assets/broken.yaml: cannot parse YAML", errors[0])
            self.assertIn("fix or remove the invalid asset", errors[0])

    def test_repository_compose_assets_have_no_findings(self):
        root = Path(__file__).resolve().parents[1]
        discovered, parse_errors = discover_compose_assets(root)
        self.assertEqual(parse_errors, [])
        expected = {
            "skills/docker-compose-patterns/assets/compose-dev-override.yaml",
            "skills/docker-compose-patterns/assets/compose-web-app.yaml",
            "skills/docker-project-foundations/assets/compose-dev.yaml",
        }
        self.assertEqual({path.relative_to(root).as_posix() for path, _ in discovered}, expected)
        self.assertEqual(validate_compose_assets(root), [])


if __name__ == "__main__":
    unittest.main()
