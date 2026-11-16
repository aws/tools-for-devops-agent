"""Unit tests for docs/hooks/connectors_catalog.py, the Connectors page hook.

The hook shows a connector that releases.yaml names at its production version,
read from Git history when this checkout carries another version, and labels the
rest Coming Soon, and publishes connector pages only as sanitised HTML. Most tests
build a small Git repository in a temporary directory, so they need git on the
PATH; the sanitiser's tests need nh3, and mkdocs to render READMEs as the site
does, and are skipped without them. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import functools
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock
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


def svg(attributes: str = "", body: str = "") -> str:
    """A minimal logo the logo check accepts, unless body or attributes say otherwise."""
    return f'<svg xmlns="http://www.w3.org/2000/svg" {attributes}>{body}</svg>'


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

    def connector(self, name="sumologic", version="1.0.0", *, readme=None, dark=False, logo=None, **fields):
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
        (directory / "logo.svg").write_text(logo or svg(f'data-version="{version}"'), encoding="utf-8")
        dark_logo = directory / "logo-dark.svg"
        if dark:
            dark_logo.write_text(svg(f'data-dark="{version}"'), encoding="utf-8")
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
        self.assertEqual(connector.logo, svg('data-version="1.0.0"').encode())
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
        self.assertEqual(self.repo.only().logo_dark, svg('data-dark="1.0.0"').encode())


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


# The sanitiser's tests need nh3, and the rendering ones mkdocs too. build-docs.yml
# installs both and sets this, so there they fail rather than skip; the
# validate-skills job runs the rest of this file without them.
REQUIRE_DOCS_DEPS = os.environ.get("CONNECTORS_TESTS_REQUIRE_DOCS_DEPS") == "1"


def _needs(*modules: str):
    missing = [m for m in modules if importlib.util.find_spec(m) is None]
    return unittest.skipIf(bool(missing) and not REQUIRE_DOCS_DEPS, f"needs {', '.join(missing)}")


@functools.lru_cache(maxsize=1)
def _site_markdown_config():
    from mkdocs.config import load_config

    config = load_config(str(ROOT / "mkdocs.yml"))
    return config["markdown_extensions"], config["mdx_configs"]


def render(markdown_text: str) -> str:
    """Render Markdown with the site's own markdown_extensions, as mkdocs build does."""
    import markdown

    extensions, configs = _site_markdown_config()
    return markdown.Markdown(extensions=extensions, extension_configs=configs).convert(markdown_text)


# Markup that could run script, as _markup words it
_LIVE = re.compile(r"^(on[a-z]+=|<(script|iframe|object|embed|noscript|style|form|base|meta)>)|javascript:", re.I)


class SanitizerTestCase(unittest.TestCase):
    def assertInert(self, cleaned: str):
        live = [item for item in hook._markup(cleaned) if _LIVE.search(item)]
        self.assertEqual(live, [], "markup that can run script was published")


@_needs("nh3")
class SanitizeHtmlTests(SanitizerTestCase):
    """sanitize_html keeps the markup connector pages use and removes the rest, saying what it removed."""

    def test_the_markup_connector_pages_use_is_published_unchanged(self):
        fragment = (
            '<h2 id="setup">Setup<a class="headerlink" href="#setup" title="Permanent link">&para;</a></h2>'
            '<p><a href="https://example.com/docs" target="_blank" rel="noopener" class="md-button">'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16" class="connector-github-icon">'
            '<path fill="currentColor" d="M8 0"/></svg>View on GitHub</a></p>'
            '<div class="admonition info"><p class="admonition-title">Coming Soon</p></div>'
            '<p><img alt="Logo" class="connector-page-logo" src="../../assets/connectors/x/logo.svg#only-light" /></p>'
            '<table><thead><tr><th style="text-align: left;">Region</th></tr></thead>'
            '<tbody><tr><td style="text-align: left;">US</td></tr></tbody></table>'
            '<ul><li><a href="../../skills/x/"><code>x</code></a></li></ul>'
            '<p>Use <code>&lt;script&gt;</code>, <a href="mailto:support@example.com">mail us</a>.</p>'
        )
        cleaned, removed = hook.sanitize_html(fragment)
        self.assertEqual(removed, [])
        self.assertEqual(hook._markup(cleaned), hook._markup(fragment))

    def test_what_can_run_script_is_removed_and_named(self):
        cases = {
            "script": ("<script>alert(1)</script>", "<script>"),
            "event handler": ('<img src="x" onerror="alert(1)">', "onerror="),
            "slash-separated handler": ("<svg/onload=alert(1)>", "onload="),
            "javascript href": ('<a href="javascript:alert(1)">x</a>', "href='javascript:"),
            "entity-encoded javascript href": ('<a href="jav&#x61;script:alert(1)">x</a>', "href='javascript:"),
            "iframe": ('<iframe src="https://example.com"></iframe>', "<iframe>"),
            "embed": ('<embed src="https://example.com/x">', "<embed>"),
            "style tag": ("<style>body{display:none}</style>", "<style>"),
            "style attribute": ('<p style="position:fixed">x</p>', "style="),
            "noscript": ('<noscript><p title="</noscript><img src=x onerror=alert(1)>"></noscript>', "<noscript>"),
            "form": ('<form action="https://example.com"><input name="password"></form>', "<form>"),
        }
        for label, (fragment, named) in cases.items():
            with self.subTest(label):
                cleaned, removed = hook.sanitize_html(f"<p>Intro.</p>{fragment}")
                self.assertTrue(any(named in item for item in removed), removed)
                self.assertInert(cleaned)

    def test_comments_are_dropped_without_failing(self):
        cleaned, removed = hook.sanitize_html("<p>Hi</p><!-- a note -->")
        self.assertEqual(removed, [])
        self.assertNotIn("<!--", cleaned)

    def test_ids_and_names_in_materials_namespace_are_removed(self):
        # A README element with id="__config" would win Material's
        # querySelector("#__config") over the theme's own (PR #204 review).
        cases = {
            "config": ('<div id="__config">{"base":"https://example.com/"}</div>', "id='__config' on <div>"),
            "search name": ('<a name="__search">x</a>', "name='__search' on <a>"),
            "toc": ('<h2 id="__toc">Contents</h2>', "id='__toc' on <h2>"),
            "palette": ('<span id="__palette_0">x</span>', "id='__palette_0' on <span>"),
        }
        for label, (fragment, named) in cases.items():
            with self.subTest(label):
                cleaned, removed = hook.sanitize_html(fragment)
                self.assertIn(named, removed)
                self.assertNotIn('="__', cleaned)

    def test_heading_ids_and_code_line_anchors_are_kept(self):
        fragment = (
            '<h2 id="setup">Setup</h2><h3 id="init__">Init</h3>'
            '<a id="__codelineno-0-1" name="__codelineno-0-1" href="#__codelineno-0-1"></a>'
        )
        cleaned, removed = hook.sanitize_html(fragment)
        self.assertEqual(removed, [])
        self.assertEqual(hook._markup(cleaned), hook._markup(fragment))

    def test_placeholders_are_shown_as_text(self):
        fragment = "<p>URL: <WEBHOOK_URL>, Bearer <API_KEY>, <YOUR TOKEN>, <your-token/> and </CONNECTOR_ID>.</p>"
        cleaned, removed = hook.sanitize_html(fragment)
        self.assertEqual(removed, [])
        for text in ("&lt;WEBHOOK_URL&gt;", "&lt;API_KEY&gt;", "&lt;YOUR TOKEN&gt;", "&lt;your-token/&gt;", "&lt;/CONNECTOR_ID&gt;"):
            self.assertIn(text, cleaned)

    def test_real_elements_and_tags_with_attribute_values_still_fail(self):
        cases = {
            "script": ("<script>alert(1)</script>", "<script>"),
            "uppercase script": ("<SCRIPT>alert(1)</SCRIPT>", "<script>"),
            "obsolete element": ("<center>x</center>", "<center>"),
            "svg element": ("<animate>", "<animate>"),
            "placeholder with a handler": ('<API_KEY onclick="alert(1)">', "onclick='alert(1)' on <api_key>"),
            "placeholder with a link": ('<WEBHOOK_URL href="javascript:alert(1)">x', "<webhook_url>"),
        }
        for label, (fragment, named) in cases.items():
            with self.subTest(label):
                cleaned, removed = hook.sanitize_html(f"<p>{fragment}</p>")
                self.assertIn(named, removed)
                self.assertInert(cleaned)


class ElementListTests(unittest.TestCase):
    """Every allowed tag is a known element, so placeholders_as_text never turns one into text."""

    def test_safe_tags_are_known_elements(self):
        self.assertEqual(hook.SAFE_TAGS - hook.KNOWN_ELEMENTS, set())

    def test_placeholders_as_text_leaves_known_elements_alone(self):
        self.assertEqual(hook.placeholders_as_text("<p><B>x</B><br/></p>"), "<p><B>x</B><br/></p>")
        self.assertEqual(hook.placeholders_as_text("<p><TOKEN></p>"), "<p>&lt;TOKEN&gt;</p>")


class LogoSafetyTests(FixtureTestCase):
    """A logo is served from the site as a file, so one that could run script, or fetch anything, fails the build."""

    def test_every_logo_in_the_repository_passes(self):
        logos = sorted((ROOT / "connectors").glob("*/logo*.svg"))
        self.assertTrue(logos)
        for path in logos:
            with self.subTest(logo=str(path.relative_to(ROOT))):
                self.assertIsNone(hook.check_logo(path.read_bytes()))

    def test_markup_that_could_run_script_or_fetch_is_refused(self):
        xlink = 'xmlns:xlink="http://www.w3.org/1999/xlink"'
        cases = {
            # PR #204 review: both were published as-is from the Halo logo
            "script": (svg(body="<script>alert(document.domain)</script>"), "<script>"),
            "event handler": (svg(body='<path d="M0 0" onclick="alert(1)"/>'), "onclick"),
            "handler on the root": (svg('onload="alert(1)"'), "onload"),
            "link": (svg(body='<a href="https://example.com"><path d="M0 0"/></a>'), "<a>"),
            "foreignObject": (svg(body="<foreignObject><div>x</div></foreignObject>"), "<foreignObject>"),
            "image": (svg(body='<image href="https://example.com/x.png"/>'), "<image>"),
            "animation": (svg(body='<set attributeName="href" to="javascript:alert(1)"/>'), "<set>"),
            "external use": (svg(xlink, '<use xlink:href="https://example.com/x.svg#a"/>'), "href to"),
            "style import": (svg(body="<style>@import url(https://example.com/x.css);</style>"), "url()"),
            "style url": (svg(body="<style>.a{background:url(https://example.com/t.png)}</style>"), "url()"),
            "attribute url": (svg(body='<path d="M0 0" fill="url(https://example.com/g.svg#g)"/>'), "url()"),
            "entity": ('<!DOCTYPE svg [<!ENTITY x "y">]>' + svg(), "DOCTYPE"),
            "stylesheet instruction": ('<?xml-stylesheet href="https://example.com/x.css"?>' + svg(), "processing instruction"),
            "no SVG namespace": ('<svg viewBox="0 0 1 1"/>', "isn't an SVG"),
            "foreign attribute": (svg(body='<path xmlns:i="https://example.com/i" i:label="x" d="M0 0"/>'), "outside the SVG namespace"),
            "unknown attribute": (svg(body='<path d="M0 0" formaction="x"/>'), "formaction"),
            "not XML": ("<svg", "can't be read"),
        }
        for label, (logo, named) in cases.items():
            with self.subTest(label):
                problem = hook.check_logo(logo.encode())
                self.assertIsNotNone(problem)
                self.assertIn(named, problem)
        self.assertIn("UTF-8", hook.check_logo(svg().encode("utf-16")))

    def test_css_that_fetches_past_the_url_check_is_refused(self):
        # A browser resolves CSS escapes and these functions, so each of these
        # fetched an external URL while reading as neither url() nor @import
        # (PR #204 review). No script runs; the leak is the request itself.
        cases = {
            "escaped url in a style element": (svg(body=r"<style>.a{background:u\72l(https://example.com/t.png)}</style>"), "CSS escape"),
            "escaped url in a style attribute": (svg(body=r'<path d="M0 0" style="fill:u\72l(https://example.com/g.svg#g)"/>'), "CSS escape"),
            "escaped import": (svg(body=r'<style>@\69mport "https://example.com/x.css";</style>'), "CSS escape"),
            "image-set in a style element": (svg(body='<style>.a{background:image-set("https://example.com/t.png" 1x)}</style>'), "image-set()"),
            "image-set in a presentation attribute": (svg(body='<path d="M0 0" fill="image-set(&quot;https://example.com/t.png&quot; 1x)"/>'), "image-set()"),
            "src in a font-face": (svg(body="<style>@font-face{src:src(https://example.com/f.woff)}</style>"), "src()"),
        }
        for label, (logo, named) in cases.items():
            with self.subTest(label):
                problem = hook.check_logo(logo.encode())
                self.assertIsNotNone(problem, "the build would pass")
                self.assertIn(named, problem)

    def test_drawing_markup_and_references_within_the_file_are_allowed(self):
        xlink = 'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10"'
        logos = [
            svg(xlink, '<defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/></linearGradient>'
                       '<path id="p" d="M0 0"/></defs><use xlink:href="#p"/><path d="M0 0" fill="url(#g)"/>'),
            '<?xml version="1.0" encoding="UTF-8"?>' + svg('data-name="Layer 1"', '<title>Logo</title>'
                '<style>.cls-1{fill:#fff}</style><g clip-path="url(#c)"><path class="cls-1" d="M0 0"/></g>'),
            # The CSS rules above must not reject ordinary styling
            svg(body='<style>.a{fill:#fff;stroke-width:1.5;font-family:Helvetica,Arial,sans-serif}</style>'
                     '<mask id="m"><rect width="10" height="10"/></mask><g mask="url(#m)"><path class="a" d="M0 0"/></g>'),
        ]
        for logo in logos:
            self.assertIsNone(hook.check_logo(logo.encode()))

    def test_an_unsafe_logo_fails_the_build_naming_the_file(self):
        self.repo.connector(logo=svg(body="<script>alert(1)</script>")).commit()
        with self.assertRaisesRegex(hook.CatalogError, r"connectors/sumologic/logo\.svg has a <script> element"):
            self.repo.catalog()

    def test_a_released_logo_is_checked_at_its_version(self):
        first = self.repo.connector(version="1.0.0", dark=False, logo=svg(body='<path d="M0 0" onclick="x"/>')).commit()
        self.repo.connector(version="1.1.0").commit()
        self.repo.releases(sumologic="1.0.0")
        with self.assertRaisesRegex(hook.CatalogError, rf"logo\.svg at {first[:12]} has an event handler"):
            self.repo.catalog()


class MissingSanitizerTests(unittest.TestCase):
    """Without nh3 the build stops, rather than publish an unsanitised page."""

    def test_the_error_says_how_to_install_it(self):
        with unittest.mock.patch.dict(sys.modules, {"nh3": None}):
            with self.assertRaisesRegex(hook.CatalogError, r"pip install --require-hashes -r \.github/scripts/docs/requirements\.txt"):
                hook.sanitize_html("<p>x</p>")


@_needs("nh3", "mkdocs")
class RenderedReadmeTests(SanitizerTestCase):
    """READMEs rendered with the site's Markdown settings, then sanitised, as the build does."""

    # Each was a way past the earlier source scan (PR #204 review): text that
    # scan read as code, but that Markdown renders as live HTML.
    BYPASSES = {
        "escaped backticks": "Escaped \\`<img src=x onerror=alert(1)>\\` here.",
        "unclosed fence": "```\n<script>alert(1)</script>",
        "backtick in the info string": "```a`b\n<script>alert(1)</script>\n```",
        "slash-separated handler": "<svg/onload=alert(1)>",
        "attr_list attribute": '[docs](https://example.com){ onclick="alert(1)" }',
        "javascript link": "[x](javascript:alert(1))",
    }

    def test_each_bypass_is_removed_and_fails_the_build(self):
        for label, snippet in self.BYPASSES.items():
            with self.subTest(label):
                cleaned, removed = hook.sanitize_html(render(f"# Set up\n\nIntro.\n\n{snippet}\n"))
                self.assertNotEqual(removed, [], "the build would pass")
                self.assertInert(cleaned)

    def test_code_examples_and_site_markdown_are_published_unchanged(self):
        readme = (
            "# Set up\n\n"
            "Don't paste `<script>` tags or ``<img onerror=x>`` here. :warning:\n\n"
            '!!! note "Before you connect"\n\n    Create a key first.\n\n'
            "| Region | Endpoint |\n|:--|:--|\n| US | `https://mcp.example.com` |\n\n"
            '```html\n<script>alert(1)</script>\n<a href="javascript:alert(1)">x</a>\n```\n\n'
            '```python linenums="1"\nprint("hi")\n```\n'
        )
        cleaned, removed = hook.sanitize_html(render(readme))
        self.assertEqual(removed, [])
        self.assertInert(cleaned)
        self.assertIn('id="__codelineno-', cleaned)

    def test_a_readme_cant_take_over_materials_config(self):
        readme = (
            '# Set up\n\n<div id="__config">{"base":"https://example.com/","features":["navigation.instant"]}</div>\n\n'
            "## Contents {#__toc}\n\nSee the [docs](https://example.com/x/).\n"
        )
        cleaned, removed = hook.sanitize_html(render(readme))
        self.assertIn("id='__config' on <div>", removed)
        self.assertIn("id='__toc' on <h2>", removed)
        self.assertFalse([item for item in hook._markup(cleaned) if item.startswith(("id='__", "name='__"))])

    def test_placeholders_in_prose_and_tables_render_as_text(self):
        # As in connectors/elastic/README.md, which GitHub shows as text
        readme = (
            "# Set up\n\n- **URL**: <WEBHOOK_URL>\n\n"
            "| Header | Value |\n|---|---|\n| Authorization | Bearer <API_KEY> |\n\n"
            "```yaml\nconnector-id: <CONNECTOR_ID>\n```\n"
        )
        cleaned, removed = hook.sanitize_html(render(readme))
        self.assertEqual(removed, [])
        for text in ("&lt;WEBHOOK_URL&gt;", "&lt;API_KEY&gt;", "&lt;CONNECTOR_ID&gt;"):
            self.assertIn(text, cleaned)

    def test_every_connector_page_publishes_unchanged(self):
        catalog = hook.build_catalog(ROOT)
        self.assertTrue(catalog)
        for connector in catalog:
            with self.subTest(connector=connector.name):
                _, removed = hook.sanitize_html(render(hook.render_page(connector, ROOT)))
                self.assertEqual(removed, [])

    def test_on_page_content_fails_the_build_naming_the_readme(self):
        from mkdocs.exceptions import PluginError

        page = types.SimpleNamespace(file=types.SimpleNamespace(src_uri="connectors/sumologic.md"))
        self.addCleanup(hook._SHOWN_REFS.clear)
        hook._SHOWN_REFS["sumologic"] = "0123456789abcdef0123456789abcdef01234567"
        with self.assertRaisesRegex(PluginError, r"connectors/sumologic/README\.md at 0123456789ab .*<script>"):
            hook.on_page_content("<p>x</p><script>alert(1)</script>", page=page)

        safe = "<p>Hello</p>"
        self.assertEqual(hook._markup(hook.on_page_content(safe, page=page)), hook._markup(safe))

    def test_other_pages_are_left_alone(self):
        for src in ("connectors/index.md", "skills/x.md", "index.md"):
            with self.subTest(src):
                page = types.SimpleNamespace(file=types.SimpleNamespace(src_uri=src))
                self.assertEqual(hook.on_page_content("<p>x</p>", page=page), "<p>x</p>")


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

    def test_the_stylesheet_is_well_formed(self):
        # An unclosed rule swallows every rule after it: a merge once dropped the
        # Blogs section's last "}" and the browser ignored the Connectors styles.
        css = re.sub(r"/\*.*?\*/", "", (ROOT / "docs" / "stylesheets" / "extra.css").read_text(encoding="utf-8"), flags=re.S)
        depth = 0
        for number, line in enumerate(css.split("\n"), start=1):
            depth += line.count("{") - line.count("}")
            self.assertGreaterEqual(depth, 0, f"extra.css line {number} closes a rule that isn't open")
        self.assertEqual(depth, 0, "extra.css leaves a rule unclosed")

    def test_published_pages_cant_pull_in_repository_files(self):
        # pymdownx.snippets would let a README include any file under the repository root
        self.assertNotIn("pymdownx.snippets", (ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
        # and the deploy job's checkout keeps no token in .git/config to include
        deploy = (ROOT / ".github" / "workflows" / "deploy-docs.yml").read_text(encoding="utf-8")
        self.assertIn("persist-credentials: false", deploy)


if __name__ == "__main__":
    unittest.main()
