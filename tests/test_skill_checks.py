"""Unit tests for .github/scripts/skill_checks.py.

Each test builds one skill folder in memory and runs the rules on it, so no
Git repository is needed. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

import skill_checks as sc  # noqa: E402

RULES = sc.Rules(
    agent_types=frozenset({"GENERIC", "CHAT", "INCIDENT_RCA"}),
    vocabulary={
        "agent-types": frozenset({"Chat tasks", "Evaluation"}),
        "aws-services": frozenset({"Amazon CloudWatch", "Amazon EKS"}),
        "technical-domains": frozenset({"Operations"}),
    },
    aliases={"CloudWatch": "Amazon CloudWatch"},
)

VALID_FRONTMATTER = """\
name: demo-skill
description: Use this skill when testing the skill publishing check.
metadata:
  author: octocat
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks"
"""


def skill_md(frontmatter: str = VALID_FRONTMATTER, body: str = "\n# Demo\n") -> bytes:
    return f"---\n{frontmatter}---\n{body}".encode("utf-8")


def tree(content: bytes | None = None, name: str = "demo-skill", **files: bytes) -> sc.SkillTree:
    entries = {}
    if content is not None:
        entries["SKILL.md"] = sc.Entry("SKILL.md", "100644", content)
    for path, data in files.items():
        entries[path] = sc.Entry(path, "100644", data)
    return sc.SkillTree(name, entries)


def frontmatter_with(**overrides: str | None) -> str:
    """VALID_FRONTMATTER with metadata keys replaced (value) or removed (None)."""
    metadata = {
        "author": "octocat",
        "version": '"1.0.0"',
        "aws-devops-agent-skills.agent-types": '"Chat tasks"',
    }
    for key, value in overrides.items():
        if value is None:
            metadata.pop(key, None)
        else:
            metadata[key] = value
    lines = "".join(f"  {key}: {value}\n" for key, value in metadata.items())
    return (
        "name: demo-skill\n"
        "description: Use this skill when testing the skill publishing check.\n"
        f"metadata:\n{lines}"
    )


class CheckSkillTestCase(unittest.TestCase):
    def check(self, skill: sc.SkillTree) -> tuple[list[sc.Finding], sc.SkillInfo | None]:
        return sc.check_skill(skill, RULES)

    def errors(self, skill: sc.SkillTree) -> list[sc.Finding]:
        return [f for f in self.check(skill)[0] if f.severity == "error"]

    def warnings(self, skill: sc.SkillTree) -> list[sc.Finding]:
        return [f for f in self.check(skill)[0] if f.severity == "warning"]

    def assertOneError(self, skill: sc.SkillTree, fragment: str, line: int | None = None) -> sc.Finding:
        errors = self.errors(skill)
        matching = [f for f in errors if fragment in f.message]
        self.assertTrue(matching, f"no error containing {fragment!r}; got {[f.message for f in errors]}")
        if line is not None:
            self.assertEqual(matching[0].line, line, matching[0].message)
        return matching[0]


class ValidSkillTests(CheckSkillTestCase):
    def test_valid_skill_has_no_findings(self):
        findings, info = self.check(tree(skill_md()))
        self.assertEqual(findings, [])
        self.assertEqual(info.name, "demo-skill")
        self.assertEqual(info.version, (1, 0, 0))
        self.assertEqual(info.metadata["author"], "octocat")

    def test_block_scalar_description_is_accepted(self):
        fm = VALID_FRONTMATTER.replace(
            "description: Use this skill when testing the skill publishing check.\n",
            "description: >-\n  Use this skill when testing\n  the skill publishing check.\n",
        )
        self.assertEqual(self.errors(tree(skill_md(fm))), [])

    def test_optional_fields_are_accepted(self):
        fm = frontmatter_with(
            summary='"Checks a demo skill."',
            deprecated='"false"',
            agent_types='"CHAT, INCIDENT_RCA"',
        ).replace("metadata:\n", "title: Demo Skill\ncompatibility: Requires nothing.\nmetadata:\n")
        self.assertEqual(self.check(tree(skill_md(fm)))[0], [])


class FileAndYamlTests(CheckSkillTestCase):
    def test_missing_skill_md(self):
        self.assertOneError(tree(None, **{"README.md": b"# Demo\n"}), "has no SKILL.md")

    def test_not_utf8(self):
        self.assertOneError(tree(b"---\nname: \xff\n---\n"), "not valid UTF-8")

    def test_no_opening_delimiter(self):
        self.assertOneError(tree(b"name: demo-skill\n"), "must start with a --- line", line=1)

    def test_no_closing_delimiter(self):
        self.assertOneError(tree(b"---\nname: demo-skill\n"), "no closing --- line")

    def test_invalid_yaml_reports_line(self):
        content = skill_md(VALID_FRONTMATTER + 'bad: "unclosed\n')
        self.assertOneError(tree(content), "not valid YAML")

    def test_anchor_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("author: octocat", "author: &who octocat")
        self.assertOneError(tree(skill_md(fm)), "anchors", line=5)

    def test_alias_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("author: octocat", "author: &who octocat") + "license: *who\n"
        self.assertOneError(tree(skill_md(fm)), "aliases")

    def test_tag_is_rejected(self):
        fm = VALID_FRONTMATTER.replace('version: "1.0.0"', "version: !!str 1.0.0")
        self.assertOneError(tree(skill_md(fm)), "tags", line=6)

    def test_flow_collection_is_rejected(self):
        fm = VALID_FRONTMATTER + "allowed-tools: [read, write]\n"
        self.assertOneError(tree(skill_md(fm)), "flow collections", line=8)

    def test_frontmatter_must_be_a_mapping(self):
        self.assertOneError(tree(b"---\n- one\n- two\n---\n"), "must be a mapping")

    def test_duplicate_key_reports_second_line(self):
        fm = VALID_FRONTMATTER + "name: demo-skill\n"
        self.assertOneError(tree(skill_md(fm)), 'duplicate key "name"', line=8)

    def test_duplicate_metadata_key(self):
        fm = VALID_FRONTMATTER + '  version: "1.0.1"\n'
        self.assertOneError(tree(skill_md(fm)), 'duplicate key "metadata.version"', line=8)

    def test_non_string_key_is_rejected(self):
        fm = VALID_FRONTMATTER + "1: one\n"
        self.assertOneError(tree(skill_md(fm)), "keys must be plain text")

    def test_unknown_top_level_key_is_a_warning(self):
        fm = VALID_FRONTMATTER + "owner: someone\n"
        warnings = self.warnings(tree(skill_md(fm)))
        self.assertEqual(len(warnings), 1)
        self.assertIn('unknown top-level key "owner"', warnings[0].message)
        self.assertEqual(self.errors(tree(skill_md(fm))), [])


class NameTests(CheckSkillTestCase):
    def with_name(self, name: str, folder: str = "demo-skill") -> sc.SkillTree:
        return tree(skill_md(VALID_FRONTMATTER.replace("name: demo-skill", f"name: {name}")), name=folder)

    def test_name_is_required(self):
        fm = VALID_FRONTMATTER.replace("name: demo-skill\n", "")
        self.assertOneError(tree(skill_md(fm)), '"name" is required')

    def test_name_must_be_a_string(self):
        self.assertOneError(self.with_name("true"), '"name" must be text, not true or false', line=2)

    def test_name_pattern(self):
        for bad in ("Demo-Skill", "demo--skill", "-demo", "demo-", "demo_skill"):
            with self.subTest(bad=bad):
                self.assertOneError(self.with_name(bad, folder=bad), "lowercase letters, digits and single hyphens")

    def test_name_length(self):
        long_name = "a" * 65
        self.assertOneError(self.with_name(long_name, folder=long_name), "65 characters; the limit is 64")

    def test_name_must_match_folder(self):
        self.assertOneError(self.with_name("other-skill"), 'but the folder is "demo-skill"', line=2)


class DescriptionAndTitleTests(CheckSkillTestCase):
    def test_description_is_required(self):
        fm = VALID_FRONTMATTER.replace("description: Use this skill when testing the skill publishing check.\n", "")
        self.assertOneError(tree(skill_md(fm)), '"description" is required')

    def test_description_must_not_be_empty(self):
        fm = VALID_FRONTMATTER.replace("Use this skill when testing the skill publishing check.", '""')
        self.assertOneError(tree(skill_md(fm)), '"description" must not be empty', line=3)

    def test_description_limit(self):
        fm = VALID_FRONTMATTER.replace("Use this skill when testing the skill publishing check.", "x" * 1025)
        self.assertOneError(tree(skill_md(fm)), "1,025 characters; the limit is 1,024")
        fm = VALID_FRONTMATTER.replace("Use this skill when testing the skill publishing check.", "x" * 1024)
        self.assertEqual(self.errors(tree(skill_md(fm))), [])

    def test_title_limit_and_single_line(self):
        fm = VALID_FRONTMATTER + f"title: {'T' * 101}\n"
        self.assertOneError(tree(skill_md(fm)), '"title" is 101 characters; the limit is 100')
        fm = VALID_FRONTMATTER + "title: |\n  Two\n  lines\n"
        self.assertOneError(tree(skill_md(fm)), '"title" must be a single line')


class MetadataTests(CheckSkillTestCase):
    def test_metadata_is_required(self):
        fm = "name: demo-skill\ndescription: Use this skill when testing.\n"
        self.assertOneError(tree(skill_md(fm)), '"metadata" is required')

    def test_metadata_must_be_a_mapping(self):
        fm = "name: demo-skill\ndescription: Use this skill when testing.\nmetadata: none\n"
        self.assertOneError(tree(skill_md(fm)), '"metadata" must be a mapping', line=4)

    def test_metadata_values_must_be_strings(self):
        fm = frontmatter_with(version="1.0")
        error = self.assertOneError(tree(skill_md(fm)), '"metadata.version" must be text, not a number', line=6)
        self.assertIn("quotes", error.message)

    def test_metadata_values_must_not_be_nested(self):
        fm = VALID_FRONTMATTER + "  extra:\n    nested: value\n"
        self.assertOneError(tree(skill_md(fm)), '"metadata.extra" must be text, not a mapping', line=8)

    def test_author_is_required_and_github_shaped(self):
        self.assertOneError(tree(skill_md(frontmatter_with(author=None))), '"metadata.author" is required')
        for bad in ('"-octocat"', '"octo cat"', '"octo--cat"', '"a,,b"', '""'):
            with self.subTest(bad=bad):
                self.assertOneError(tree(skill_md(frontmatter_with(author=bad))), "GitHub usernames")

    def test_author_accepts_a_comma_separated_list(self):
        self.assertEqual(self.errors(tree(skill_md(frontmatter_with(author='"octocat, hubot"')))), [])

    def test_version_is_required(self):
        self.assertOneError(tree(skill_md(frontmatter_with(version=None))), '"metadata.version" is required')

    def test_version_must_be_major_minor_patch(self):
        for bad in ('"2.6"', '"1.0.0-beta"', '"1.0.0+build"', '"01.0.0"', '"v1.0.0"', '"1.0.0.0"'):
            with self.subTest(bad=bad):
                self.assertOneError(tree(skill_md(frontmatter_with(version=bad))), "MAJOR.MINOR.PATCH", line=6)

    def test_unquoted_three_part_version_is_text(self):
        findings, info = self.check(tree(skill_md(frontmatter_with(version="1.2.3"))))
        self.assertEqual(findings, [])
        self.assertEqual(info.version, (1, 2, 3))

    def test_summary_limit_and_single_line(self):
        fm = frontmatter_with(summary=f'"{"s" * 201}"')
        self.assertOneError(tree(skill_md(fm)), '"metadata.summary" is 201 characters; the limit is 200')
        fm = frontmatter_with(summary='"two\\nlines"')
        self.assertOneError(tree(skill_md(fm)), '"metadata.summary" must be a single line')

    def test_deprecated_must_be_true_or_false_text(self):
        self.assertOneError(tree(skill_md(frontmatter_with(deprecated='"yes"'))), '"true" or "false"')
        self.assertOneError(tree(skill_md(frontmatter_with(deprecated="true"))), "must be text, not true or false")
        self.assertEqual(self.errors(tree(skill_md(frontmatter_with(deprecated='"true"')))), [])

    def test_agent_types_values(self):
        fm = frontmatter_with(agent_types='"CHAT, PAGER"')
        self.assertOneError(tree(skill_md(fm)), 'unknown value "PAGER"')
        fm = frontmatter_with(agent_types='"CHAT,"')
        self.assertOneError(tree(skill_md(fm)), "empty value between commas")


class DimensionTests(CheckSkillTestCase):
    def test_unknown_dimension_is_an_error(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.services": '"Amazon EKS"'})
        self.assertOneError(tree(skill_md(fm)), "not a known dimension")

    def test_empty_dimension_value_is_an_error(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.aws-services": '"Amazon EKS, "'})
        self.assertOneError(tree(skill_md(fm)), "empty value between commas")

    def test_unapproved_value_is_a_warning_with_suggestion(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.aws-services": '"CloudWatch, Amazon S3"'})
        skill = tree(skill_md(fm))
        self.assertEqual(self.errors(skill), [])
        messages = [w.message for w in self.warnings(skill)]
        self.assertEqual(len(messages), 2)
        self.assertIn('use "Amazon CloudWatch"', messages[0])
        self.assertIn('"Amazon S3" is not an approved aws-services value', messages[1])


class ParseVersionTests(unittest.TestCase):
    def test_strict_and_lenient(self):
        self.assertEqual(sc.parse_version("1.2.3"), (1, 2, 3))
        self.assertIsNone(sc.parse_version("2.6"))
        self.assertEqual(sc.parse_version("2.6", allow_two_part=True), (2, 6, 0))
        self.assertIsNone(sc.parse_version("1.2.3-rc.1", allow_two_part=True))


class LoadRulesTests(unittest.TestCase):
    def test_repository_rule_files_load(self):
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules")
        self.assertIn("GENERIC", rules.agent_types)
        self.assertIn("Amazon CloudWatch", rules.vocabulary["aws-services"])
        self.assertEqual(rules.aliases["CloudWatch"], "Amazon CloudWatch")
        for value, target in rules.aliases.items():
            self.assertNotIn(value, rules.vocabulary["aws-services"] | rules.vocabulary["technical-domains"])
            self.assertTrue(any(target in values for values in rules.vocabulary.values()), target)


class ConformanceTests(unittest.TestCase):
    def write_cases(self, cases) -> Path:
        import tempfile

        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        self.addCleanup(Path(handle.name).unlink)
        with handle:
            handle.write(__import__("json").dumps({"cases": cases}))
        return Path(handle.name)

    def test_repository_cases_give_their_expected_results(self):
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules")
        cases = sc.load_cases(ROOT / ".github" / "scripts" / "skill-rules" / "conformance-cases.json")
        self.assertEqual(sc.run_conformance(cases, rules), [])

    def test_malformed_case_files_are_rejected(self):
        files = {"SKILL.md": {"text": "x"}}
        bad = {
            "duplicate id": [{"id": "a", "name": "d", "expect": "pass", "files": files}] * 2,
            'needs an "error"': [{"id": "a", "name": "d", "expect": "fail", "files": files}],
            'exactly one of "text" or "base64"': [{"id": "a", "name": "d", "expect": "pass", "files": {"x": {}}}],
            '"expect" must be': [{"id": "a", "name": "d", "expect": "maybe", "files": files}],
        }
        for fragment, cases in bad.items():
            with self.subTest(fragment=fragment):
                with self.assertRaisesRegex(ValueError, fragment.replace("(", r"\(")):
                    sc.load_cases(self.write_cases(cases))

    def test_wrong_expectation_is_reported(self):
        case = {"id": "a", "name": "demo-skill", "expect": "fail", "error": "nope", "files": {"SKILL.md": {"text": skill_md().decode()}}}
        problems = sc.run_conformance([case], RULES)
        self.assertEqual(len(problems), 1)
        self.assertIn("expected an error containing 'nope', got: no errors", problems[0])


if __name__ == "__main__":
    unittest.main()
