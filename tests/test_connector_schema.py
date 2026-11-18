"""Tests for connectors/schema/v1/: the string rules in its schemas, and the files the catalog publisher accepts.

Standard library only, so the repository's test job runs them without a JSON Schema
dependency. A small evaluator covers the keywords the string rules use; the schemas
as a whole are validated by the connector check that consumes them.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "connectors" / "schema" / "v1"
CONNECTOR = json.loads((SCHEMA_DIR / "connector.schema.json").read_text(encoding="utf-8"))

# RE2, used by Go, Rust and some server SDKs, has no lookaround or backreferences.
RE2_UNSUPPORTED = re.compile(r"\(\?<?[=!]|\\[1-9]")


def patterns(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "pattern" and isinstance(value, str):
                yield value
            else:
                yield from patterns(value)
    elif isinstance(node, list):
        for item in node:
            yield from patterns(item)


def resolve(schema: dict) -> dict:
    ref = schema.get("$ref")
    if ref is None:
        return schema
    node = CONNECTOR
    for part in ref.removeprefix("#/").split("/"):
        node = node[part]
    return resolve({**node, **{k: v for k, v in schema.items() if k != "$ref"}})


def accepts(schema: dict, value: str) -> bool:
    """Whether ``value`` satisfies a string schema built from the keywords below."""
    schema = resolve(schema)
    checks = [
        "minLength" not in schema or len(value) >= schema["minLength"],
        "maxLength" not in schema or len(value) <= schema["maxLength"],
        "pattern" not in schema or re.search(schema["pattern"], value) is not None,
        "const" not in schema or value == schema["const"],
        all(accepts(s, value) for s in schema.get("allOf", [])),
        "anyOf" not in schema or any(accepts(s, value) for s in schema["anyOf"]),
        "not" not in schema or not accepts(schema["not"], value),
    ]
    return all(checks)


DEFS = CONNECTOR["$defs"]
PREFIX = DEFS["apiKeyAuth"]["properties"]["headers"]["items"]["properties"]["prefix"]
CONFIG_PATTERN = DEFS["mcp"]["properties"]["config"]["items"]["properties"]["pattern"]


class SchemaFilesTests(unittest.TestCase):
    def test_every_schema_file_is_json(self):
        for path in sorted(SCHEMA_DIR.glob("*.json")):
            with self.subTest(path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_every_pattern_compiles_and_avoids_what_re2_lacks(self):
        for path in sorted(SCHEMA_DIR.glob("*.json")):
            for pattern in patterns(json.loads(path.read_text(encoding="utf-8"))):
                with self.subTest(file=path.name, pattern=pattern):
                    re.compile(pattern)
                    self.assertIsNone(RE2_UNSUPPORTED.search(pattern))


class StringRuleTests(unittest.TestCase):
    def check(self, schema: dict, good: list[str], bad: list[str]) -> None:
        for value in good:
            with self.subTest(accepts=value):
                self.assertTrue(accepts(schema, value))
        for value in bad:
            with self.subTest(rejects=value):
                self.assertFalse(accepts(schema, value))

    def test_maintainers_are_usernames_or_teams_without_an_at_sign(self):
        self.check(
            {"$ref": "#/$defs/githubHandle"},
            good=["octocat", "a", "mona-lisa", "a" * 39, "acme/team-ai", "acme/team_ai", "a" * 39 + "/t"],
            bad=[
                "@octocat", "@acme/team-ai", "a" * 40, "a" * 40 + "/t", "/team", "acme/", "acme/team/sub",
                "acme/team ai", "-acme", "acme-", "mona--lisa", "acme/" + "t" * 101,
            ],
        )

    def test_a_contact_email_is_one_address(self):
        self.check(
            CONNECTOR["properties"]["contact_email"],
            good=["devops-agent@acme.example", "a@b.co", "partner.alerts+aws@acme.example"],
            bad=["acme", "a@b", "a b@acme.example", "@acme.example", "a@@acme.example", "a@acme.example ", "x" * 250 + "@a.co"],
        )

    def test_categories_include_devops(self):
        categories = CONNECTOR["properties"]["categories"]["items"]["enum"]
        self.assertEqual(categories, ["cloud", "telemetry", "pipeline", "communication", "devops"])

    def test_a_header_prefix_takes_no_placeholder(self):
        self.check(PREFIX, good=["Bearer ", "Token ", "", "{x}", "a{"], bad=["{{config.x}}", "Bearer {{config.x}}", "{{"])

    def test_a_config_pattern_is_anchored(self):
        self.check(CONFIG_PATTERN, good=["^(us1|us2|eu)$", "^[a-z0-9-]{1,63}$"], bad=["[a-z0-9-]+", "^[a-z]+", "[a-z]+$"])

    def test_versions_are_strict_semver_with_short_parts(self):
        self.check(
            {"$ref": "#/$defs/version"},
            good=["0.0.0", "1.4.0", "1234567890.0.1"],
            bad=["1.0", "01.0.0", "1.0.0-beta", "12345678901.0.0", "v1.0.0"],
        )

    def test_names_are_slugs(self):
        self.check(
            {"$ref": "#/$defs/capabilityName"},
            good=["sumologic", "acme-observability", "a"],
            bad=["Sumo", "sumo_logic", "-acme", "acme-", "a--b", "a" * 65],
        )


class CatalogSchemaSetTests(unittest.TestCase):
    def test_the_schema_files_are_the_set_the_catalog_publisher_accepts(self):
        """The publisher bundles its own copies of these files and accepts connectors/schema/v1/ only when it matches.

        Any other bytes stop every publish run, skills included, so a change here
        merges only once a publisher release bundles it. Update these hashes in
        the same pull request.
        """
        accepted = {
            "connector.schema.json": "d8763d5b3d1d02600650117a38722a65a39ac62d52186b36f8727b496714329d",
            "published-files.json": "a9b62504d44b5d3a1cb7324d0b34b326a14b829f5e07d2ca4db24d3ebe272aac",
            "releases.schema.json": "95f3c897e1e41fe93d19f8aed7dfdac12f498eaf48f8b46c62add2881ad92c2f",
        }
        hashes = {name: hashlib.sha256((SCHEMA_DIR / name).read_bytes()).hexdigest() for name in accepted}
        self.assertEqual(hashes, accepted)


if __name__ == "__main__":
    unittest.main()
