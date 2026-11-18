"""Unit tests for docs/hooks/skills_catalog.py, the GitHub Pages catalog hook.

The hook renders metadata.aws-devops-agent-skills.agent-types, which carries the
API values, as readable labels. That label map is a second list of the agent
types, so these tests keep it in step with agent-types.json: a value added there
without a label would show the raw API value in the catalog.

They also check that skills whose metadata.tier is aws-support-managed stay off
the site while mkdocs.yml says so, that a page naming one fails the build, and
that the hook reads the tier as .github/scripts/skill_checks.py does. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = ROOT / ".github" / "scripts" / "skill-rules"
HOOK = ROOT / "docs" / "hooks" / "skills_catalog.py"
sys.path.insert(0, str(ROOT / ".github" / "scripts"))


def _load_hook():
    """Import the hook by path, since docs/hooks isn't a package."""
    spec = importlib.util.spec_from_file_location("skills_catalog", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _agent_types() -> list[str]:
    return json.loads((RULES_DIR / "agent-types.json").read_text(encoding="utf-8"))["values"]


def _skill_md(name: str, tier_line: str = "") -> str:
    """A SKILL.md for `name`, with tier_line, if given, in its metadata."""
    metadata = '  author: octocat\n  version: "1.0.0"\n' + (f"  {tier_line}\n" if tier_line else "")
    return (
        f"---\nname: {name}\ndescription: Use this skill when testing the docs catalog.\n"
        f"metadata:\n{metadata}---\n\n# {name}\n"
    )


class AgentTypeLabelTests(unittest.TestCase):
    """AGENT_TYPE_LABELS and agent-types.json must list the same agent types."""

    def setUp(self):
        self.labels = _load_hook().AGENT_TYPE_LABELS
        self.values = _agent_types()

    def test_every_agent_type_has_a_label(self):
        missing = [v for v in self.values if v not in self.labels]
        self.assertEqual(
            missing,
            [],
            f"these would show as raw API values in the catalog; add a label in "
            f"{HOOK.relative_to(ROOT)}: {missing}",
        )

    def test_every_label_names_a_real_agent_type(self):
        unknown = [v for v in self.labels if v not in self.values]
        self.assertEqual(
            unknown,
            [],
            f"labels for values that aren't in agent-types.json, so they can never be shown: {unknown}",
        )

    def test_labels_are_non_empty_single_line_text(self):
        for value, label in self.labels.items():
            with self.subTest(value=value):
                self.assertIsInstance(label, str)
                self.assertTrue(label.strip(), "label is empty")
                self.assertEqual(label, label.strip(), "label has surrounding whitespace")
                self.assertNotIn("\n", label)


class DimensionRenderingTests(unittest.TestCase):
    """Every skill in the repository renders a label, never a raw API value."""

    def setUp(self):
        self.hook = _load_hook()

    def test_agent_types_are_rendered_as_labels(self):
        catalog = self.hook._build_catalog(str(ROOT))
        self.assertTrue(catalog, "the catalog is empty, so nothing was checked")
        labels = set(self.hook.AGENT_TYPE_LABELS.values())
        api_values = set(self.hook.AGENT_TYPE_LABELS)
        for skill in catalog:
            with self.subTest(skill=skill["id"]):
                rendered = skill["dimensions"].get("agent-types", [])
                self.assertTrue(rendered, "no agent types rendered")
                for shown in rendered:
                    self.assertIn(shown, labels, f"{shown!r} is not a known label")
                    self.assertNotIn(shown, api_values, f"the raw API value {shown!r} reached the catalog")


class AuthorLinkTests(unittest.TestCase):
    """Each author in metadata.author gets its own link, and a team links to its organization."""

    def setUp(self):
        self.hook = _load_hook()

    def links(self, author: str) -> list[tuple[str, str]]:
        block = self.hook._build_skill_meta_block({"author": author, "dimensions": {}})
        return re.findall(r'<a href="([^"]+)"[^>]*><strong>([^<]+)</strong></a>', block)

    def test_a_user_links_to_their_profile(self):
        self.assertEqual(self.links("octocat"), [("https://github.com/octocat", "octocat")])

    def test_a_team_links_to_its_organization(self):
        self.assertEqual(self.links("octo-org/octo-team"), [("https://github.com/octo-org", "octo-org/octo-team")])

    def test_a_list_gets_one_link_per_author(self):
        self.assertEqual(
            self.links("octocat, hubot, octo-org/octo-team"),
            [
                ("https://github.com/octocat", "octocat"),
                ("https://github.com/hubot", "hubot"),
                ("https://github.com/octo-org", "octo-org/octo-team"),
            ],
        )


class AwsSupportManagedTests(unittest.TestCase):
    """extra.skills_catalog.show_aws_support_managed decides whether aws-support-managed skills are on the site."""

    def setUp(self):
        self.hook = _load_hook()
        # The hook finds the repository by removing "/docs" from docs_dir, so
        # the rest of the path must not contain it.
        self.root = Path(tempfile.mkdtemp(prefix="skills-catalog-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.docs = self.root / "docs"
        (self.docs / "skills").mkdir(parents=True)
        (self.docs / "skills" / "index.md").write_text("# Skills Catalog\n", encoding="utf-8")
        self.add_skill("partner-skill", _skill_md("partner-skill", 'tier: "partner-managed"'))
        self.add_skill("support-skill", _skill_md("support-skill", 'tier: "aws-support-managed"'))

    def add_skill(self, name: str, skill_md: str) -> None:
        folder = self.root / "skills" / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(skill_md, encoding="utf-8")

    def config(self, extra: dict) -> dict:
        return {"docs_dir": str(self.docs), "nav": [{"Skills": [{"Catalog": ["skills/index.md"]}]}], "extra": extra}

    def build(self, show: bool) -> dict:
        """Run the hook as mkdocs build does, and return the skills in its catalog data, pages and nav."""
        config = self.config({"skills_catalog": {"show_aws_support_managed": show}})
        self.hook.on_pre_build(config)
        data = json.loads((self.docs / "javascripts" / "skills-data.json").read_text(encoding="utf-8"))
        catalog_nav = config["nav"][0]["Skills"][0]["Catalog"]
        return {
            "data": [skill["id"] for skill in data],
            "pages": sorted(p.stem for p in (self.docs / "skills").glob("*.md") if p.name != "index.md"),
            "nav": [path for entry in catalog_nav[1:] for path in entry.values()],
        }

    def page(self, markdown: str, meta: dict | None = None):
        """A page, as mkdocs passes it to on_page_content once its Markdown is final."""
        return types.SimpleNamespace(
            file=types.SimpleNamespace(src_uri="custom-agents/demo.md"), markdown=markdown, meta=meta or {}
        )

    def test_false_leaves_the_skills_out_of_the_data_the_pages_and_the_nav(self):
        self.assertEqual(
            self.build(False),
            {"data": ["partner-skill"], "pages": ["partner-skill"], "nav": ["skills/partner-skill.md"]},
        )

    def test_true_lists_them(self):
        self.assertEqual(
            self.build(True),
            {
                "data": ["partner-skill", "support-skill"],
                "pages": ["partner-skill", "support-skill"],
                "nav": ["skills/partner-skill.md", "skills/support-skill.md"],
            },
        )

    def test_false_removes_a_page_an_earlier_build_wrote(self):
        self.build(True)
        self.assertEqual(self.build(False)["pages"], ["partner-skill"])

    def test_the_build_log_names_the_skills_left_out_and_says_why(self):
        with self.assertLogs("mkdocs.hooks.skills_catalog", "INFO") as logs:
            self.build(False)
        self.assertEqual(
            logs.output,
            [
                "INFO:mkdocs.hooks.skills_catalog:Skills catalog: leaving support-skill off the site while "
                "extra.skills_catalog.show_aws_support_managed is false, since it's aws-support-managed",
            ],
        )
        with self.assertNoLogs("mkdocs.hooks.skills_catalog", "INFO"):
            self.build(True)

    def test_the_build_log_doesnt_blame_the_tier_for_frontmatter_that_cant_be_read(self):
        self.add_skill("broken-skill", "---\nname: broken-skill\ndescription: Use when: things break\n---\n")
        with self.assertLogs("mkdocs.hooks.skills_catalog", "INFO") as logs:
            self.assertEqual(self.build(False)["data"], ["partner-skill"])
        broken, support = logs.output
        self.assertIn("leaving broken-skill off the site", broken)
        self.assertIn("since its tier can't be read: line 3 of SKILL.md isn't valid YAML (", broken)
        self.assertNotIn("aws-support-managed", broken)
        self.assertIn("leaving support-skill off the site", support)
        self.assertIn("since it's aws-support-managed", support)

    def test_a_page_that_names_a_skill_left_out_fails_the_strict_build(self):
        self.build(False)
        page = self.page("- The [support-skill skill](../../skills/support-skill/)\n")
        with self.assertLogs("mkdocs.hooks.skills_catalog", "WARNING") as logs:
            self.assertEqual(self.hook.on_page_content("<p>page</p>", page=page), "<p>page</p>")
        self.assertEqual(
            logs.output,
            [
                "WARNING:mkdocs.hooks.skills_catalog:Skills catalog: custom-agents/demo.md names support-skill, "
                "which is left off the site while extra.skills_catalog.show_aws_support_managed is false, "
                "since it's aws-support-managed",
            ],
        )
        self.build(True)
        with self.assertNoLogs("mkdocs.hooks.skills_catalog", "WARNING"):
            self.hook.on_page_content("", page=page)

    def test_a_page_names_a_skill_with_its_name_as_a_whole_word(self):
        self.build(False)
        for markdown in (
            "support-skill",
            "Load the `support-skill` skill.",
            "[It](../skills/support-skill.md) helps.",
            '<a href="https://github.com/aws/tools-for-devops-agent/tree/main/skills/support-skill">',
            "| `support-skill` | context |",
            "It needs support-skill.",
            "Load _support-skill_ first.",
            "Load __support-skill__ first.",
            "Load *support-skill* first.",
            "Support-Skill",
            "Support Skill",
            "Try **Support Skill** first.",
            "Try _Support Skill_ first.",
            "| SUPPORT SKILL | context |",
            "It needs support skill.",
            "It needs the Support\nSkill skill.",
            "It needs the Support\u00a0Skill skill.",
        ):
            with self.subTest(markdown=markdown), self.assertLogs("mkdocs.hooks.skills_catalog", "WARNING"):
                self.hook.on_page_content("", page=self.page(markdown))
        for markdown in (
            "support-skill-report and partner-skill",
            "my-support-skill",
            "support-skills",
            "support_skill",
            "Support Skills",
            "SupportSkill",
            "Support-Skill-Report",
        ):
            with self.subTest(markdown=markdown), self.assertNoLogs("mkdocs.hooks.skills_catalog", "WARNING"):
                self.hook.on_page_content("", page=self.page(markdown))

    def test_the_page_warning_quotes_a_name_written_differently(self):
        self.build(False)
        with self.assertLogs("mkdocs.hooks.skills_catalog", "WARNING") as logs:
            self.hook.on_page_content("", page=self.page("See the Support\n  Skill skill."))
        self.assertEqual(
            logs.output,
            [
                'WARNING:mkdocs.hooks.skills_catalog:Skills catalog: custom-agents/demo.md names support-skill as '
                '"Support Skill", which is left off the site while extra.skills_catalog.show_aws_support_managed '
                "is false, since it's aws-support-managed",
            ],
        )

    def test_a_longer_name_of_another_tool_doesnt_name_the_skill(self):
        (self.root / "custom-agents" / "support-skill-report").mkdir(parents=True)
        self.build(False)
        for markdown in (
            "# Support Skill Report",
            "Run the support skill report agent.",
            "Run [support-skill-report](../custom-agents/support-skill-report.md).",
        ):
            with self.subTest(markdown=markdown), self.assertNoLogs("mkdocs.hooks.skills_catalog", "WARNING"):
                self.hook.on_page_content("", page=self.page(markdown))
        for markdown in (
            "# Support Skill Report\n\nIt needs Support Skill.",
            "The Support Skill reporter",
        ):
            with self.subTest(markdown=markdown), self.assertLogs("mkdocs.hooks.skills_catalog", "WARNING"):
                self.hook.on_page_content("", page=self.page(markdown))

    def test_a_page_names_a_skill_in_its_front_matter(self):
        self.build(False)
        with self.assertLogs("mkdocs.hooks.skills_catalog", "WARNING") as logs:
            self.hook.on_page_content("", page=self.page("# Demo\n", meta={"title": "Support Skill in practice"}))
        self.assertIn('names support-skill as "Support Skill"', logs.output[0])
        with self.assertNoLogs("mkdocs.hooks.skills_catalog", "WARNING"):
            self.hook.on_page_content("", page=self.page("# Demo\n", meta={"hide": ["navigation", "toc"]}))

    def test_the_page_warning_says_why_each_skill_is_left_out(self):
        self.add_skill("broken-skill", "# broken-skill\n\nNo frontmatter.\n")
        self.build(False)
        with self.assertLogs("mkdocs.hooks.skills_catalog", "WARNING") as logs:
            self.hook.on_page_content("", page=self.page("Install broken-skill and support-skill first."))
        broken, support = logs.output
        self.assertIn("custom-agents/demo.md names broken-skill", broken)
        self.assertIn("since its tier can't be read: SKILL.md has no frontmatter between --- lines", broken)
        self.assertIn("custom-agents/demo.md names support-skill", support)
        self.assertIn("since it's aws-support-managed", support)

    def test_the_setting_must_be_true_or_false(self):
        for extra in (
            {},
            {"skills_catalog": None},
            {"skills_catalog": {}},
            {"skills_catalog": {"show_aws_support_managed": None}},
            {"skills_catalog": {"show_aws_support_managed": "false"}},
            {"skills_catalog": {"show_aws_support_managed": 0}},
        ):
            with self.subTest(extra=extra), self.assertRaisesRegex(
                self.hook.PluginError, r"extra\.skills_catalog\.show_aws_support_managed .* true or false"
            ):
                self.hook.on_pre_build(self.config(extra))

    def test_the_tier_is_read_as_yaml(self):
        for tier_line in (
            "tier: aws-support-managed",
            'tier: "aws-support-managed"',
            "tier: 'aws-support-managed'",
            "tier: aws-support-managed  # a comment",
            'tier: "aws-support-managed" # a comment',
        ):
            with self.subTest(tier_line=tier_line):
                self.assertEqual(self.hook._why_hidden(_skill_md("demo", tier_line)), "it's aws-support-managed")

    def test_other_tiers_stay_listed(self):
        for tier_line in (
            "",
            'tier: "partner-managed"',
            'tier: "aws-managed"',
            'tier: "aws-support"',
            'tier: "aws-managed"  # not aws-support-managed',
            'summary: "aws-support-managed"',
        ):
            with self.subTest(tier_line=tier_line):
                self.assertIsNone(self.hook._why_hidden(_skill_md("demo", tier_line)))

    def test_frontmatter_that_is_missing_or_isnt_yaml_leaves_the_skill_out(self):
        for case, text, why in (
            (
                "an unclosed list",
                '---\nname: demo\ndescription: [unclosed\nmetadata:\n  tier: "partner-managed"\n---\n',
                r"line 4 of SKILL\.md isn't valid YAML \(.+\)",
            ),
            (
                "a second colon",
                "---\nname: demo\ndescription: Use when: things break\n---\n",
                r"line 3 of SKILL\.md isn't valid YAML \(mapping values are not allowed here\)",
            ),
            (
                "a tab",
                '---\nname: demo\nmetadata:\n\ttier: "partner-managed"\n---\n',
                r"line 4 of SKILL\.md isn't valid YAML \(.+\)",
            ),
            ("a control character", "---\nname: demo\x07\n---\n", r"its frontmatter isn't valid YAML"),
            (
                "too deep",
                "---\nname: demo\nmetadata:\n  tier: " + "[" * 3000 + "]" * 3000 + "\n---\n",
                r"its frontmatter is nested too deeply",
            ),
            (
                "no closing line",
                '---\nname: demo\nmetadata:\n  tier: "partner-managed"\n',
                r"SKILL\.md has no frontmatter between --- lines",
            ),
            ("no frontmatter", "# demo\n\nNo frontmatter.\n", r"SKILL\.md has no frontmatter between --- lines"),
        ):
            with self.subTest(case):
                self.assertRegex(self.hook._why_hidden(text), rf"^its tier can't be read: {why}$")


class SkillChecksAgreementTests(unittest.TestCase):
    """The hook copies how .github/scripts/skill_checks.py finds the frontmatter, and the tier's spelling."""

    def test_the_frontmatter_is_found_as_the_publishing_check_finds_it(self):
        import skill_checks

        hook = _load_hook()
        self.assertEqual(hook._FRONTMATTER.pattern, skill_checks.FRONTMATTER_PATTERN.pattern)
        self.assertEqual(hook._FRONTMATTER.flags, skill_checks.FRONTMATTER_PATTERN.flags)

    def test_the_hidden_tier_is_one_the_publishing_check_accepts(self):
        import skill_checks

        self.assertIn(_load_hook().AWS_SUPPORT_MANAGED, skill_checks.TIERS)


if __name__ == "__main__":
    unittest.main()
