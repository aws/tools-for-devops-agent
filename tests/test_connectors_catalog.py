"""Unit tests for docs/hooks/connectors_catalog.py, the Connectors page hook.

The hook shows a connector that releases.yaml names at its production version,
read from Git history when this checkout carries another version, and labels the
rest Coming Soon. Most tests build a small Git repository in a temporary
directory, so they need git on the PATH. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "docs" / "hooks" / "connectors_catalog.py"
SCHEMA = ROOT / "connectors" / "schema" / "v1" / "connector.schema.json"

# Keep the fixture repositories' commits independent of the user's Git config.
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def _load_hook():
    """Import the hook by path, since docs/hooks isn't a package."""
    spec = importlib.util.spec_from_file_location("connectors_catalog", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hook = _load_hook()


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], env=GIT_ENV, check=True, capture_output=True, text=True
    ).stdout.strip()


class FixtureRepo:
    """A throwaway repository with connectors/ and skills/, like this one."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True)
        _git(root, "init", "-q")
        (root / "connectors").mkdir()
        skill = root / "skills" / "sumologic-log-search"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: sumologic-log-search\n---\n", encoding="utf-8")

    def connector(self, name="sumologic", version="1.0.0", *, readme=None, dark=False, **fields):
        directory = self.root / "connectors" / name
        directory.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "name": name,
            "version": version,
            "title": "Sumo Logic",
            "vendor": "Sumo Logic, Inc.",
            "description": "Search logs during investigations.",
            "categories": ["telemetry"],
            "tier": "partner-managed",
            "type": "mcp",
            "mcp": {"endpoints": [{"label": "US1", "endpoint": "https://mcp.example.com/mcp"}]},
            "skills": ["sumologic-log-search"],
            "docs_url": "https://example.com/docs",
            "support_url": "https://example.com/support",
            "maintainers": ["octocat"],
            **fields,
        }
        (directory / "connector.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        (directory / "README.md").write_text(
            readme if readme is not None else f"# Set up Sumo Logic\n\nSteps for {version}.\n", encoding="utf-8"
        )
        (directory / "logo.svg").write_text(f'<svg data-version="{version}"/>', encoding="utf-8")
        dark_logo = directory / "logo-dark.svg"
        if dark:
            dark_logo.write_text(f'<svg data-dark="{version}"/>', encoding="utf-8")
        elif dark_logo.exists():
            dark_logo.unlink()
        return self

    def releases(self, **versions):
        entries = [{"name": name.replace("_", "-"), "production": v} for name, v in sorted(versions.items())]
        (self.root / "connectors").mkdir(exist_ok=True)  # git rm of the last connector removes it
        (self.root / "connectors" / "releases.yaml").write_text(
            yaml.safe_dump({"schema_version": 1, "connectors": entries}), encoding="utf-8"
        )
        return self

    def commit(self, message="change") -> str:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", message)
        return _git(self.root, "rev-parse", "HEAD")

    def catalog(self):
        return hook.build_catalog(self.root)

    def only(self):
        catalog = self.catalog()
        assert len(catalog) == 1, [c.name for c in catalog]
        return catalog[0]


class FixtureTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = FixtureRepo(self.tmp / "repo")

    def page(self, connector) -> str:
        return hook.render_page(connector, self.repo.root)


class LabelTests(unittest.TestCase):
    """Every category and tier the schema allows has a display label, and no label is for a value it doesn't."""

    def setUp(self):
        self.properties = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]

    def test_category_labels_match_the_schema(self):
        self.assertEqual(set(hook.CATEGORY_LABELS), set(self.properties["categories"]["items"]["enum"]))

    def test_tier_labels_match_the_schema(self):
        self.assertEqual(set(hook.TIER_LABELS), set(self.properties["tier"]["enum"]))


class ReleaseTests(FixtureTestCase):
    """releases.yaml decides whether a connector is available, and at which version."""

    def test_a_connector_without_a_releases_entry_is_coming_soon(self):
        self.repo.connector(version="1.0.0").releases().commit()
        connector = self.repo.only()
        self.assertEqual(connector.status, hook.COMING_SOON)
        self.assertEqual(connector.to_json()["version"], "1.0.0")
        self.assertIn('!!! info "Coming Soon"', self.page(connector))
        self.assertIn("tag-coming-soon", self.page(connector))

    def test_a_missing_releases_file_leaves_every_connector_coming_soon(self):
        self.repo.connector().commit()
        self.assertEqual(self.repo.only().status, hook.COMING_SOON)

    def test_a_promoted_connector_is_available_at_its_production_version(self):
        self.repo.connector(version="1.0.0").commit()
        self.repo.releases(sumologic="1.0.0")  # the promotion pull request
        connector = self.repo.only()
        self.assertEqual(connector.status, hook.AVAILABLE)
        self.assertEqual(connector.ref, hook.CHECKOUT_REF)
        self.assertNotIn("Coming Soon", self.page(connector))

    def test_a_newer_version_on_main_doesnt_replace_the_production_one(self):
        first = self.repo.connector(version="1.0.0").commit("1.0.0")
        self.repo.connector(version="1.1.0").commit("1.1.0")
        self.repo.releases(sumologic="1.0.0")
        connector = self.repo.only()
        self.assertEqual(connector.status, hook.AVAILABLE)
        self.assertEqual(connector.to_json()["version"], "1.0.0")
        self.assertEqual(connector.ref, first)
        self.assertIn("Steps for 1.0.0.", connector.readme)
        self.assertEqual(connector.logo, b'<svg data-version="1.0.0"/>')
        self.assertIn(f"/tree/{first}/connectors/sumologic", self.page(connector))

    def test_the_newest_commit_at_the_production_version_is_used(self):
        self.repo.connector(version="1.0.0", readme="# T\n\nFirst.\n").commit()
        newest = self.repo.connector(version="1.0.0", readme="# T\n\nSecond.\n").commit()
        self.repo.connector(version="1.1.0").commit()
        self.repo.releases(sumologic="1.0.0")
        self.assertEqual(self.repo.only().ref, newest)

    def test_a_production_version_main_never_carried_fails_the_build(self):
        self.repo.connector(version="1.0.0").commit()
        self.repo.releases(sumologic="2.0.0")
        with self.assertRaisesRegex(hook.CatalogError, r"sumologic 2\.0\.0"):
            self.repo.catalog()

    def test_a_shallow_clone_says_to_fetch_the_history(self):
        self.repo.connector(version="1.0.0").commit()
        self.repo.connector(version="1.1.0").commit()
        clone = self.tmp / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", self.repo.root.as_uri(), str(clone)],
            env=GIT_ENV, check=True, capture_output=True,
        )
        (clone / "connectors" / "releases.yaml").write_text(
            "schema_version: 1\nconnectors:\n  - { name: sumologic, production: 1.0.0 }\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(hook.CatalogError, "fetch-depth: 0"):
            hook.build_catalog(clone)

    def test_a_released_connector_removed_from_main_is_read_from_history(self):
        self.repo.connector(version="1.0.0").commit()
        _git(self.repo.root, "rm", "-q", "-r", "connectors/sumologic")
        self.repo.commit("remove")
        self.repo.releases(sumologic="1.0.0")
        connector = self.repo.only()
        self.assertEqual(connector.status, hook.AVAILABLE)
        self.assertEqual(connector.title, "Sumo Logic")

    def test_a_deprecated_connector_is_left_out(self):
        self.repo.connector(deprecated=True).commit()
        self.assertEqual(self.repo.catalog(), [])

    def test_available_connectors_come_first(self):
        self.repo.connector("zeta", title="Zeta").connector("alpha", title="Alpha").commit()
        self.repo.releases(zeta="1.0.0")
        self.assertEqual([c.name for c in self.repo.catalog()], ["zeta", "alpha"])


class LogoTests(FixtureTestCase):
    """logo-dark.svg, when a connector has one, is what the dark scheme shows."""

    def test_a_dark_logo_is_shown_in_the_dark_scheme(self):
        self.repo.connector(dark=True).commit()
        connector = self.repo.only()
        data = connector.to_json()
        self.assertEqual(data["logo"], "assets/connectors/sumologic/logo.svg")
        self.assertEqual(data["logo_dark"], "assets/connectors/sumologic/logo-dark.svg")
        page = self.page(connector)
        self.assertIn("../assets/connectors/sumologic/logo.svg#only-light", page)
        self.assertIn("../assets/connectors/sumologic/logo-dark.svg#only-dark", page)

    def test_without_a_dark_logo_the_one_logo_shows_in_both_schemes(self):
        self.repo.connector(dark=False).commit()
        connector = self.repo.only()
        self.assertIsNone(connector.to_json()["logo_dark"])
        self.assertNotIn("#only-", self.page(connector))

    def test_a_released_dark_logo_comes_from_the_production_version(self):
        self.repo.connector(version="1.0.0", dark=True).commit()
        self.repo.connector(version="1.1.0", dark=False).commit()
        self.repo.releases(sumologic="1.0.0")
        self.assertEqual(self.repo.only().logo_dark, b'<svg data-dark="1.0.0"/>')


class PageTests(FixtureTestCase):
    """The connector page: a header from connector.yaml, the README, then the skills."""

    def test_the_page_names_its_skills_and_links_the_ones_with_a_page(self):
        self.repo.connector(skills=["sumologic-log-search", "not-in-this-repo"]).commit()
        page = self.page(self.repo.only())
        self.assertIn("- [`sumologic-log-search`](../skills/sumologic-log-search.md)", page)
        self.assertIn("- `not-in-this-repo`", page)
        self.assertNotIn("../skills/not-in-this-repo.md", page)

    def test_the_header_shows_vendor_tier_and_categories(self):
        self.repo.connector(categories=["telemetry", "devops"]).commit()
        page = self.page(self.repo.only())
        self.assertIn("by <strong>Sumo Logic, Inc.</strong>", page)
        self.assertIn('<span class="tag tag-tier">Partner-managed</span>', page)
        self.assertIn('<span class="tag tag-category">Telemetry</span>', page)
        self.assertIn('<span class="tag tag-category">DevOps</span>', page)

    def test_the_readme_title_is_dropped_and_relative_links_point_at_github(self):
        readme = (
            "# Set up Sumo Logic\n\n"
            "Read the [terms](../TERMS.md), the [skill](../../skills/x/) and the [vendor docs](https://example.com).\n\n"
            "```\n# a comment, not a heading [a](b.md)\n```\n"
        )
        self.repo.connector(readme=readme).commit()
        body = hook.transform_readme(readme, "sumologic", "main")
        self.assertNotIn("# Set up Sumo Logic", body)
        self.assertIn(f"[terms]({hook.REPO_URL}/blob/main/connectors/TERMS.md)", body)
        self.assertIn(f"[skill]({hook.REPO_URL}/blob/main/skills/x)", body)
        self.assertIn("[vendor docs](https://example.com)", body)
        self.assertIn("# a comment, not a heading [a](b.md)", body)

    def test_text_from_connector_yaml_is_escaped(self):
        self.repo.connector(title="<script>x</script>", vendor="A & B").commit()
        page = self.page(self.repo.only())
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("A &amp; B", page)


class PreBuildTests(FixtureTestCase):
    """on_pre_build writes the data file, pages and logos, and adds the pages to the nav."""

    def test_writes_data_pages_logos_and_nav(self):
        self.repo.connector(dark=True).commit()
        docs = self.repo.root / "docs"
        nav = [{"Connectors": [{"Catalog": ["connectors/index.md"]}]}]
        hook.on_pre_build({"docs_dir": str(docs), "nav": nav})

        data = json.loads((docs / "javascripts" / "connectors-data.json").read_text(encoding="utf-8"))
        self.assertEqual([c["id"] for c in data], ["sumologic"])
        self.assertTrue((docs / "connectors" / "sumologic.md").is_file())
        self.assertTrue((docs / "assets" / "connectors" / "sumologic" / "logo.svg").is_file())
        self.assertTrue((docs / "assets" / "connectors" / "sumologic" / "logo-dark.svg").is_file())
        self.assertEqual(nav[0]["Connectors"][0]["Catalog"][1], {"Sumo Logic": "connectors/sumologic.md"})

        # A logo-dark.svg the connector no longer has isn't left behind
        self.repo.connector(dark=False).commit()
        hook.on_pre_build({"docs_dir": str(docs), "nav": []})
        self.assertFalse((docs / "assets" / "connectors" / "sumologic" / "logo-dark.svg").exists())


class RepositoryTests(unittest.TestCase):
    """The catalog builds from this repository, and the site pages that show it are wired up."""

    def test_every_connector_in_the_repository_is_catalogued(self):
        catalog = hook.build_catalog(ROOT)
        expected = set()
        for manifest in (ROOT / "connectors").glob("*/connector.yaml"):
            if yaml.safe_load(manifest.read_text(encoding="utf-8")).get("deprecated") is not True:
                expected.add(manifest.parent.name)
        released = set(hook.read_releases(ROOT / "connectors" / "releases.yaml"))
        self.assertTrue(expected <= {c.name for c in catalog})
        for connector in catalog:
            with self.subTest(connector=connector.name):
                self.assertIsNotNone(connector.logo, "no logo.svg")
                self.assertEqual(connector.status == hook.AVAILABLE, connector.name in released)
                json.dumps(connector.to_json())

    def test_the_mcp_servers_page_lists_connectors_under_partner_hosted(self):
        page = (ROOT / "docs" / "mcp-servers" / "index.md").read_text(encoding="utf-8")
        section = page.split("## Partner-hosted", 1)
        self.assertEqual(len(section), 2, "no Partner-hosted section")
        self.assertRegex(
            section[1].split("\n## ", 1)[0],
            r'<div id="partner-connectors-root" data-source="\.\./javascripts/connectors-data\.json"',
        )

    def test_the_connectors_page_and_its_tab_exist(self):
        page = (ROOT / "docs" / "connectors" / "index.md").read_text(encoding="utf-8")
        self.assertIn('id="connectors-catalog-root"', page)
        mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
        self.assertIn("docs/hooks/connectors_catalog.py", mkdocs)
        self.assertRegex(mkdocs, r"- Connectors:\n\s+- Catalog:\n\s+- connectors/index\.md")
        self.assertIn('href="connectors/"', (ROOT / "docs" / "index.md").read_text(encoding="utf-8"))
        deploy = (ROOT / ".github" / "workflows" / "deploy-docs.yml").read_text(encoding="utf-8")
        self.assertIn("'connectors/**'", deploy)


if __name__ == "__main__":
    unittest.main()
