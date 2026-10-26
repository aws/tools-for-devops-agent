"""Unit tests for .github/scripts/skill_checks.py.

Each test builds one skill folder in memory and runs the rules on it, so no
Git repository is needed. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import dataclasses
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

import skill_checks as sc  # noqa: E402

RULES = sc.Rules(
    agent_types=frozenset({"GENERIC", "CHAT", "INCIDENT_RCA"}),
    vocabulary={
        "aws-services": frozenset({"Amazon CloudWatch", "Amazon EKS"}),
        "technical-domains": frozenset({"Operations"}),
    },
    aliases={"CloudWatch": "Amazon CloudWatch"},
    allowed_extensions=frozenset({"md", "json", "png", "html"}),
    published_excludes=("evals/", ".skilleval.yaml", "CHANGELOG.md"),
    # Made-up names, so the tests name no real internal host or tool.
    internal_names=sc._internal_name_patterns({"hosts": ["corp.example", "intra.example"], "terms": ["Rivendell"]}),
)

VALID_FRONTMATTER = """\
name: demo-skill
description: Use this skill when testing the skill publishing check.
metadata:
  author: octocat
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "CHAT"
  summary: "Checks a demo skill."
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
        "aws-devops-agent-skills.agent-types": '"CHAT"',
        "summary": '"Checks a demo skill."',
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

    def assertOneError(
        self, skill: sc.SkillTree, fragment: str, line: int | None = None, *, also: tuple[str, ...] = ()
    ) -> sc.Finding:
        """Exactly one error contains `fragment`, and the only other errors are the ones `also` names."""
        errors = self.errors(skill)
        messages = [f.message for f in errors]
        matching = [f for f in errors if fragment in f.message]
        self.assertEqual(len(matching), 1, f"want one error containing {fragment!r}; got {messages}")
        others = [m for m in messages if fragment not in m]
        self.assertEqual(len(others), len(also), f"unexpected extra errors: {others}")
        for extra in also:
            self.assertTrue(any(extra in m for m in others), f"no extra error containing {extra!r}; got {others}")
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
            **{"aws-devops-agent-skills.agent-types": '"CHAT, INCIDENT_RCA"'},
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
        self.assertOneError(tree(content), "not valid YAML", line=9)

    def test_anchor_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("author: octocat", "author: &who octocat")
        self.assertOneError(tree(skill_md(fm)), "anchors", line=5)

    def test_alias_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("author: octocat", "author: &who octocat") + "license: *who\n"
        self.assertOneError(tree(skill_md(fm)), "aliases", also=("anchors",))

    def test_tag_is_rejected(self):
        fm = VALID_FRONTMATTER.replace('version: "1.0.0"', "version: !!str 1.0.0")
        self.assertOneError(tree(skill_md(fm)), "tags", line=6)

    def test_flow_collection_is_rejected(self):
        fm = VALID_FRONTMATTER + "allowed-tools: [read, write]\n"
        self.assertOneError(tree(skill_md(fm)), "flow collections", line=9)

    def test_frontmatter_must_be_a_mapping(self):
        self.assertOneError(tree(b"---\n- one\n- two\n---\n"), "must be a mapping")

    def test_duplicate_key_reports_second_line(self):
        fm = VALID_FRONTMATTER + "name: demo-skill\n"
        self.assertOneError(tree(skill_md(fm)), 'duplicate key "name"', line=9)

    def test_duplicate_metadata_key(self):
        fm = VALID_FRONTMATTER + '  version: "1.0.1"\n'
        self.assertOneError(tree(skill_md(fm)), 'duplicate key "metadata.version"', line=9)

    def test_non_string_key_is_rejected(self):
        fm = VALID_FRONTMATTER + "1: one\n"
        self.assertOneError(tree(skill_md(fm)), "keys must be plain text")

    def test_unknown_top_level_key_is_a_warning(self):
        fm = VALID_FRONTMATTER + "owner: someone\n"
        warnings = self.warnings(tree(skill_md(fm)))
        self.assertEqual(len(warnings), 1)
        self.assertIn('unknown top-level key "owner"', warnings[0].message)
        self.assertEqual(self.errors(tree(skill_md(fm))), [])
        (warning,) = self.warnings(tree(skill_md(VALID_FRONTMATTER + "licence: MIT\n")))
        self.assertIn('unknown top-level key "licence" (did you mean "license"?)', warning.message)

    def test_keys_must_be_plain_text_at_any_depth(self):
        for key in ("1e3", "true", "~", "1"):
            with self.subTest(key=key):
                fm = VALID_FRONTMATTER + f"extra:\n  {key}: one\n"
                self.assertOneError(tree(skill_md(fm)), "keys must be plain text", line=10)
        self.assertEqual(self.errors(tree(skill_md(VALID_FRONTMATTER + 'extra:\n  "1e3": one\n'))), [])

    def test_duplicate_keys_are_rejected_at_any_depth(self):
        for extra, line in (("extra:\n  a: one\n  a: two\n", 11), ("extra:\n  - a: one\n    a: two\n", 11)):
            with self.subTest(extra=extra):
                self.assertOneError(tree(skill_md(VALID_FRONTMATTER + extra)), 'duplicate key "extra.a"', line=line)

    def test_line_breaks_other_parsers_dont_see_are_rejected(self):
        for char in ("\u2028", "\u2029", "\x85"):
            with self.subTest(code=hex(ord(char))):
                fm = VALID_FRONTMATTER.replace(
                    '  summary: "Checks a demo skill."\n',
                    f'  summary: "Checks a demo skill."{char}  deprecated: "true"\n',
                )
                self.assertOneError(tree(skill_md(fm)), f"U+{ord(char):04X}, which YAML parsers disagree on", line=8)

    def test_triple_dash_inside_the_frontmatter_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("testing the skill publishing check.", "testing --- the publishing check.")
        self.assertOneError(tree(skill_md(fm)), 'contains "---"', line=3)

    def test_directives_and_document_markers_are_rejected(self):
        self.assertOneError(tree(b"---\n%YAML 1.1\n--- # start\n" + skill_md()[4:]), "directives (%)", also=("document markers",))
        self.assertOneError(tree(skill_md(VALID_FRONTMATTER + "...\n")), "document markers", line=9)

    def test_empty_frontmatter_is_named(self):
        for content in (b"---\n\n---\n# Demo\n", b"---\n---\n# Demo\n"):
            with self.subTest(content=content):
                self.assertOneError(tree(content), "the frontmatter is empty")


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

    def test_name_with_trailing_newline_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("name: demo-skill", "name: |\n  demo-skill")
        self.assertOneError(tree(skill_md(fm)), "lowercase letters, digits and single hyphens", also=("they must match",))

    def test_deeply_nested_frontmatter_is_a_finding_not_a_crash(self):
        nested = "".join("  " * depth + f"k{depth}:\n" for depth in range(1, 1200)) + "  " * 1200 + "k: v\n"
        self.assertOneError(
            tree(skill_md(VALID_FRONTMATTER + "deep:\n" + nested)),
            "nested too deeply",
            also=("the limit is 32,768", "a published file can be at most"),
        )

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
        self.assertOneError(tree(skill_md(fm)), '"metadata.extra" must be text, not a mapping', line=9)

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

    def test_block_scalar_version_with_trailing_newline_is_rejected(self):
        fm = frontmatter_with(version="|\n    1.0.0")
        self.assertOneError(tree(skill_md(fm)), "MAJOR.MINOR.PATCH")

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

    def test_generic_cannot_be_combined_with_another_agent_type(self):
        """The Asset API rejects GENERIC alongside another type."""
        for value in ('"GENERIC, CHAT"', '"CHAT, GENERIC"', '"GENERIC, CHAT, INCIDENT_RCA"'):
            with self.subTest(value=value):
                fm = frontmatter_with(**{"aws-devops-agent-skills.agent-types": value})
                self.assertOneError(tree(skill_md(fm)), "must stand alone")

    def test_generic_on_its_own_is_accepted(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.agent-types": '"GENERIC"'})
        self.assertEqual(self.errors(tree(skill_md(fm))), [])

    def test_agent_types_values(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.agent-types": '"CHAT, PAGER"'})
        self.assertOneError(tree(skill_md(fm)), 'unknown value "PAGER"')
        fm = frontmatter_with(**{"aws-devops-agent-skills.agent-types": '"CHAT,"'})
        self.assertOneError(tree(skill_md(fm)), "empty value between commas")


class DimensionTests(CheckSkillTestCase):
    def test_unknown_dimension_is_an_error(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.services": '"Amazon EKS"'})
        self.assertOneError(tree(skill_md(fm)), "not a known dimension")

    def test_misspelled_prefix_is_an_error(self):
        for key in (
            "aws-devops-agent-skill.aws-services",
            "AWS-DevOps-Agent-Skills.aws-services",
            "aws_devops_agent_skills.aws-services",
            "aws-devops-agent-skils.aws-services",
            "aws-devops-agnet-skills.aws-services",
            "devops-agent-skills.aws-services",
            "aws-devops-agent-skills:aws-services",
        ):
            with self.subTest(key=key):
                skill = tree(skill_md(frontmatter_with(**{key: '"Amazon EKS"'})))
                self.assertOneError(skill, "misspells the aws-devops-agent-skills. prefix")
                self.assertEqual(self.warnings(skill), [])

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


class SummaryAndAgentTypeTests(CheckSkillTestCase):
    def test_missing_summary_is_a_warning_for_every_skill(self):
        skill = tree(skill_md(frontmatter_with(summary=None)))
        self.assertEqual(self.errors(skill), [])
        (warning,) = self.warnings(skill)
        self.assertIn('"metadata.summary" is missing', warning.message)
        self.assertEqual(warning.line, 4)

    def test_missing_agent_types_warns_that_the_skill_loads_for_every_agent(self):
        skill = tree(skill_md(frontmatter_with(**{"aws-devops-agent-skills.agent-types": None})))
        self.assertEqual(self.errors(skill), [])
        (warning,) = self.warnings(skill)
        self.assertIn("installs as GENERIC and loads for every agent", warning.message)
        self.assertEqual(warning.line, 4)

    def test_agent_types_is_checked_against_the_api_values_not_the_vocabulary(self):
        """The key sets which agents load the skill, so it skips the catalog vocabulary."""
        fm = frontmatter_with(**{"aws-devops-agent-skills.agent-types": '"CHAT, INCIDENT_RCA"'})
        skill = tree(skill_md(fm))
        self.assertEqual(self.errors(skill), [])
        self.assertEqual(self.warnings(skill), [])

    def test_display_spelling_of_an_agent_type_is_an_error(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.agent-types": '"Chat tasks"'})
        self.assertOneError(tree(skill_md(fm)), 'unknown value "Chat tasks"')

    def test_explicit_generic_does_not_warn(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.agent-types": '"GENERIC"'})
        self.assertEqual(self.check(tree(skill_md(fm)))[0], [])


class LimitsAndTierTests(CheckSkillTestCase):
    def test_index_is_a_reserved_name(self):
        fm = frontmatter_with().replace("name: demo-skill", "name: index")
        self.assertOneError(tree(skill_md(fm), name="index"), "reserved for the skill catalog's index", line=2)

    def test_a_very_long_version_part_is_an_error_not_a_crash(self):
        fm = frontmatter_with(version='"1.' + "9" * 4301 + '.0"')
        self.assertOneError(tree(skill_md(fm)), "each part can have at most 10 digits")

    def test_version_length_limits(self):
        for bad in ('"1.0.12345678901"', '"12345678901.0.0"'):
            with self.subTest(bad=bad):
                self.assertOneError(tree(skill_md(frontmatter_with(version=bad))), "at most 10 digits", line=6)
        long_version = '"' + ".".join(["1234567890"] * 3) + '"'  # 32 characters, 10 digits each: allowed
        self.assertEqual(self.errors(tree(skill_md(frontmatter_with(version=long_version)))), [])

    def test_tier_values(self):
        for good in ('"aws-managed"', '"partner-managed"'):
            with self.subTest(good=good):
                self.assertEqual(self.errors(tree(skill_md(frontmatter_with(tier=good)))), [])
        self.assertOneError(tree(skill_md(frontmatter_with(tier='"community"'))), '"metadata.tier" must be')
        self.assertOneError(tree(skill_md(frontmatter_with(tier='"AWS-managed"'))), '"metadata.tier" must be')

    def test_spec_text_fields_must_not_be_empty(self):
        for key in ("license", "compatibility", "allowed-tools"):
            with self.subTest(key=key):
                fm = frontmatter_with().replace("metadata:\n", f'{key}: ""\nmetadata:\n')
                self.assertOneError(tree(skill_md(fm)), f'"{key}" must not be empty', line=4)

    def test_compatibility_limit(self):
        fm = frontmatter_with().replace("metadata:\n", f"compatibility: {'c' * 501}\nmetadata:\n")
        self.assertOneError(tree(skill_md(fm)), '"compatibility" is 501 characters; the limit is 500')
        fm = frontmatter_with().replace("metadata:\n", f"compatibility: {'c' * 500}\nmetadata:\n")
        self.assertEqual(self.errors(tree(skill_md(fm))), [])

    def test_byte_order_mark_is_named(self):
        content = "\ufeff".encode() + skill_md()
        self.assertOneError(tree(content), "byte order mark", line=1)

    def test_tab_anywhere_in_the_frontmatter_is_rejected(self):
        for value, line in (('"Checks\ta demo skill."', 8), (">-\n    Checks\ta demo skill.", 9)):
            with self.subTest(value=value):
                self.assertOneError(tree(skill_md(frontmatter_with(summary=value))), "tab character", line=line)

    def test_a_key_with_no_value_says_so(self):
        fm = frontmatter_with().replace("metadata:\n", "license:\nmetadata:\n")
        error = self.assertOneError(tree(skill_md(fm)), '"license" has no value; give it a value or remove the key')
        self.assertNotIn("Put the value in quotes", error.message)
        error = self.assertOneError(tree(skill_md(frontmatter_with(author=""))), '"metadata.author" has no value')
        self.assertNotIn("remove the key", error.message)

    def test_special_yaml_values_are_named(self):
        fm = frontmatter_with().replace("metadata:\n", "license: =\nmetadata:\n")
        self.assertOneError(tree(skill_md(fm)), '"license" must be text, not a special YAML value')

    def test_values_other_parsers_read_as_numbers_must_be_quoted(self):
        for value in ("1e3", "-1.0e3", "+.5", "0o17", "+0o17", "1_0e3", "._5", "1_0.5e3"):
            with self.subTest(value=value):
                fm = frontmatter_with().replace("metadata:\n", f"title: {value}\nmetadata:\n")
                self.assertOneError(tree(skill_md(fm)), "other YAML parsers read")
        fm = frontmatter_with().replace("metadata:\n", 'title: "1e3"\nmetadata:\n')
        self.assertEqual(self.errors(tree(skill_md(fm))), [])

    def test_empty_title_is_rejected(self):
        fm = frontmatter_with().replace("metadata:\n", 'title: "  "\nmetadata:\n')
        self.assertOneError(tree(skill_md(fm)), '"title" must not be empty')

    def test_empty_summary_counts_as_missing(self):
        for value in ('""', '"   "'):
            with self.subTest(value=value):
                skill = tree(skill_md(frontmatter_with(summary=value)))
                self.assertEqual(self.errors(skill), [])
                (warning,) = self.warnings(skill)
                self.assertIn('"metadata.summary" is empty', warning.message)
                self.assertEqual(warning.line, 8)

    def test_non_text_values_do_not_also_warn_as_missing(self):
        fm = frontmatter_with(summary="\n    - one", **{"aws-devops-agent-skills.agent-types": "\n    - CHAT"})
        skill = tree(skill_md(fm))
        self.assertEqual(
            sorted(f.message.split('"')[1] for f in self.errors(skill)),
            ["metadata.aws-devops-agent-skills.agent-types", "metadata.summary"],
        )
        self.assertEqual(self.warnings(skill), [])

    def test_unknown_metadata_key_warns_with_a_suggestion(self):
        skill = tree(skill_md(frontmatter_with(deprecate='"true"')))
        self.assertEqual(self.errors(skill), [])
        (warning,) = self.warnings(skill)
        self.assertIn('unknown metadata key "deprecate"; did you mean "deprecated"?', warning.message)

    def test_long_body_is_a_warning(self):
        # A blank line and 499 lines, each ending in a newline. The skill evaluation
        # tool also counts the empty piece after the last newline, so 501.
        body = "\n" + "".join(f"Line {i}.\n" for i in range(499))
        skill = tree(skill_md(body=body))
        self.assertEqual(self.errors(skill), [])
        (warning,) = self.warnings(skill)
        self.assertIn("the SKILL.md body is 501 lines", warning.message)
        self.assertEqual(self.warnings(tree(skill_md(body="\n" + "x\n" * 498))), [])


def with_files(*paths: str, mode: str = "100644", data: bytes = b"text\n") -> sc.SkillTree:
    skill = tree(skill_md())
    for path in paths:
        skill.entries[path] = sc.Entry(path, mode, data)
    return skill


class PublishedSetTests(unittest.TestCase):
    def test_excludes_evals_eval_config_and_changelog_but_keeps_readme_and_images(self):
        skill = with_files(
            "README.md",
            "CHANGELOG.md",
            ".skilleval.yaml",
            "evals/evals.json",
            "references/a.md",
            "docs/CHANGELOG.md",
            "images/diagram.png",
        )
        self.assertEqual(
            sorted(sc.published_files(skill, RULES)),
            ["README.md", "SKILL.md", "docs/CHANGELOG.md", "images/diagram.png", "references/a.md"],
        )

    def test_repository_published_set_matches_the_catalog(self):
        gitignore = (ROOT / "skills" / ".gitignore").read_text(encoding="utf-8")
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules", gitignore)
        self.assertEqual(rules.published_excludes, ("evals/", ".skilleval.yaml", "CHANGELOG.md"))

    def test_zip_is_deterministic(self):
        files = {"b.md": b"b", "a.md": b"a" * 100}
        self.assertEqual(sc.build_zip(files), sc.build_zip(dict(reversed(files.items()))))


class PackageTests(CheckSkillTestCase):
    def test_typical_skill_passes(self):
        skill = with_files("README.md", "references/guide.md", "assets/diagram.png", "evals/evals.json")
        self.assertEqual(self.errors(skill), [])

    def test_file_count_limit(self):
        paths = [f"references/{i:03}.md" for i in range(99)]
        self.assertEqual(self.errors(with_files(*paths)), [])
        self.assertOneError(with_files(*paths, "references/extra.md"), "101 published files; the limit is 100")

    def test_file_count_warning(self):
        paths = [f"references/{i:03}.md" for i in range(90)]
        self.assertEqual(self.warnings(with_files(*paths[:89])), [])
        (warning,) = self.warnings(with_files(*paths))
        self.assertIn("91 published files, over 90% of the limit of 100", warning.message)

    def test_evals_do_not_count_toward_the_file_limit(self):
        paths = [f"evals/run/{i:03}.json" for i in range(200)]
        self.assertEqual(self.errors(with_files(*paths)), [])

    def test_zip_size_limit_and_warning(self):
        import random

        rng = random.Random(7)

        def skill_with(count: int, size: int) -> sc.SkillTree:
            skill = tree(skill_md())
            for i in range(count):
                path = f"assets/big{i}.png"
                skill.entries[path] = sc.Entry(path, "100644", rng.randbytes(size))
            return skill

        near = skill_with(5, 760_000)
        self.assertEqual(self.errors(near), [])
        (warning,) = self.warnings(near)
        self.assertIn("zip to", warning.message)
        self.assertIn("over 90% of the 4,128,768-byte limit", warning.message)
        self.assertOneError(skill_with(5, 900_000), "the limit is 4,128,768")

    def test_file_size_limit(self):
        self.assertEqual(self.errors(with_files("references/big.md", data=b"a" * 1_048_576)), [])
        self.assertOneError(
            with_files("references/big.md", data=b"a" * 1_048_577), "a published file can be at most 1,048,576"
        )
        self.assertEqual(self.errors(with_files("evals/big.json", data=b"a" * 2_000_000)), [])

    def test_file_size_warning(self):
        self.assertEqual(self.warnings(with_files("references/big.md", data=b"a" * 943_718)), [])
        (warning,) = self.warnings(with_files("references/big.md", data=b"a" * 943_719))
        self.assertIn("over 90% of the 1,048,576-byte limit", warning.message)
        self.assertEqual(warning.path, "references/big.md")

    def test_frontmatter_size_limit(self):
        fm = frontmatter_with().replace("metadata:\n", "compatibility: " + "c" * 400 + "\nmetadata:\n")
        padding = "".join(f'  extra-{i}: "{"x" * 300}"\n' for i in range(110))
        self.assertOneError(tree(skill_md(fm + padding)), "the limit is 32,768", line=1)
        self.assertEqual(self.errors(tree(skill_md(fm))), [])

    def test_executable_symlink_and_submodule_are_rejected_anywhere(self):
        self.assertOneError(with_files("references/a.md", mode="100755"), "executable")
        self.assertOneError(with_files("evals/run.json", mode="100755"), "executable")
        self.assertOneError(with_files("references/link.md", mode="120000", data=b"../../x"), "symbolic link")
        self.assertOneError(with_files("vendor", mode="160000", data=b""), "Git submodule")

    def test_path_rules(self):
        cases = {
            "references/my notes.md": "letters, digits",
            "references/naïve.md": "letters, digits",
            "references/CON.md": "reserved name",
            "references/com0.md": "reserved name",
            "references/LPT0/a.md": "reserved name",
            "references/caf\udce9.md": "letters, digits",
            "references/notes.": "ends with a period",
            "references/" + "a" * 510 + ".md": "the limit is 512",
            "references/__proto__/a.md": "silently drop",
        }
        for path, fragment in cases.items():
            with self.subTest(path=path):
                self.assertOneError(with_files(path), fragment)

    def test_folder_name_with_trailing_newline_is_rejected(self):
        self.assertOneError(with_files("references\n/a.md"), "letters, digits")

    def test_case_collision(self):
        self.assertOneError(with_files("references/Guide.md", "references/guide.md"), "differ only in case")

    def test_folder_case_collision_is_reported_once(self):
        skill = with_files("references/Guide/Sub/a.md", "references/guide/sub/b.md", "references/guide/c.md")
        messages = [f.message for f in self.errors(skill) if "folders" in f.message]
        self.assertEqual(len(messages), 1, messages)
        self.assertIn('"references/Guide" and "references/guide" differ only in case', messages[0])

    def test_file_and_folder_with_the_same_path_collide(self):
        self.assertOneError(with_files("references/Notes.md", "references/notes.md/a.md"), "is a folder")

    def test_hidden_files_are_rejected_in_the_published_set_only(self):
        self.assertOneError(with_files(".DS_Store"), "hidden")
        self.assertOneError(with_files("references/.notes.md"), "hidden")
        self.assertOneError(with_files(".claude/settings.json"), "hidden")
        self.assertEqual(self.errors(with_files(".skilleval.yaml", "evals/.cache.json")), [])
        self.assertOneError(with_files(".skilleval.yml"), "hidden")  # only .skilleval.yaml is left out

    def test_eval_debug_folders_and_run_metadata_are_rejected(self):
        self.assertOneError(with_files("evals/functional/v1/cli_debug/run.json"), "cli_debug/ folder")
        self.assertOneError(with_files("evals/sdk_debug/trace.json"), "sdk_debug/ folder")
        self.assertOneError(with_files("evals/functional/v2/_metadata.json"), "run metadata")
        self.assertOneError(with_files("evals/CLI_Debug/run.json"), "CLI_Debug/ folder")
        self.assertOneError(with_files("references/evals/functional/v1/_metadata.json"), "run metadata")
        self.assertEqual(self.errors(with_files("evals/functional/v2/benchmark.json", "references/_metadata.json")), [])

    def test_extension_allowlist(self):
        self.assertOneError(with_files("references/run.sh"), 'extension ".sh"')
        self.assertOneError(with_files("LICENSE"), "no file extension")
        self.assertEqual(self.errors(with_files("references/page.HTML")), [])
        self.assertEqual(self.errors(with_files("evals/results.log")), [])

    def test_scripts_folder_is_rejected_anywhere(self):
        self.assertOneError(with_files("scripts/run.md"), "scripts/ folders")
        self.assertOneError(with_files("evals/scripts/run.json"), "scripts/ folders")

    def test_shebang_in_published_file(self):
        self.assertOneError(with_files("references/run.md", data=b"#!/bin/sh\necho hi\n"), "starts with #!")


AWS_KEY_ID = "AKIA" + "Q7X2" * 4
PEM_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"


class ContentSafetyTests(CheckSkillTestCase):
    def test_access_key_id_anywhere_in_the_folder(self):
        data = f"line one\nkey = {AWS_KEY_ID}\n".encode()
        error = self.assertOneError(with_files("evals/journal.json", data=data), "AWS access key ID")
        self.assertEqual((error.path, error.line), ("evals/journal.json", 2))
        self.assertNotIn(AWS_KEY_ID, error.message)

    def test_documented_example_key_is_allowed(self):
        data = ("AKIA" + "IOSFODNN7EXAMPLE\n").encode()
        self.assertEqual(self.errors(with_files("references/a.md", data=data)), [])

    def test_private_key(self):
        data = f"\n\n{PEM_HEADER}\nMIIB...\n".encode()
        self.assertOneError(with_files("references/a.md", data=data), "private key", line=3)
        for header in ("-----BEGIN " + "PGP PRIVATE KEY BLOCK-----", "PuTTY-User-Key-File-" + "3: ssh-ed25519"):
            with self.subTest(header=header):
                data = f"ok\n{header}\n".encode()
                self.assertOneError(with_files("evals/run.json", data=data), "private key", line=2)

    def test_invisible_characters(self):
        for char in (
            "\u200b", "\u202e", "\u2066", "\ufeff", "\U000e0041",
            "\u00ad", "\u061c", "\u180e", "\u3164", "\u206a", "\ufe00", "\U000e0100",
            "\u180b", "\u17b4", "\u2065", "\ufff0", "\U0001d173", "\U000e0080",
        ):
            with self.subTest(code=hex(ord(char))):
                data = f"fine\nhidden{char}text\n".encode()
                self.assertOneError(with_files("references/a.md", data=data), f"U+{ord(char):04X}", line=2)

    def test_one_presentation_selector_after_a_character_is_allowed(self):
        data = "\u26a0\ufe0f Warning\n\u2139\ufe0e Note\n".encode()
        self.assertEqual(self.errors(with_files("references/a.md", data=data)), [])
        data = "fine\n\u26a0\ufe0f\ufe0f\ufe0f run\n".encode()
        self.assertOneError(with_files("references/a.md", data=data), "U+FE0F", line=2)

    def test_invisible_characters_in_skill_md(self):
        content = skill_md(body="\n# Demo\nignore\u200bprevious\n")
        self.assertOneError(tree(content), "U+200B", line=12)

    def test_active_html_and_insecure_links_warn(self):
        data = b'<script>alert(1)</script>\n<iframe src="x"></iframe>\n[a](javascript:void(0))\n[b](http://example.com)\n'
        skill = with_files("references/a.md", data=data)
        self.assertEqual(self.errors(skill), [])
        messages = " | ".join(w.message for w in self.warnings(skill))
        for fragment in ("<script>", "<iframe>", "javascript:", "http://"):
            self.assertIn(fragment, messages)

    def test_every_link_form_warns(self):
        for line in (b"<http://example.com>", b"[x]: http://example.com", b'<a href="http://example.com">x</a>'):
            with self.subTest(line=line):
                (warning,) = self.warnings(with_files("references/a.md", data=b"ok\n" + line + b"\n"))
                self.assertIn("http://", warning.message)
                self.assertEqual(warning.line, 2)
        for line in (
            b"> [x]: http://example.com/a",
            b"- [x]: http://example.com/b",
            b"[the page](&#104;ttp://example.com/d)",
            b"[the page](http\\://example.com/e)",
            b'<a href="&#104;ttp://example.com/f">x</a>',
            b"[a\\]b]: http://example.com/g",
            b'<a href="&#104ttp://example.com/z">x</a>',
            b"[x](&#00000104;ttp://example.com/q)",
        ):
            with self.subTest(line=line):
                (warning,) = self.warnings(with_files("references/a.md", data=b"ok\n" + line + b"\n"))
                self.assertIn("http://", warning.message)
                self.assertEqual(warning.line, 2)
        for data, line in (
            (b"[x]:\nhttp://example.com/c\n", 1),
            (b"- a\n  - b\n\n    [x]: http://example.com/k\n", 4),
            (b'See <abbr title="one&#10;two">x</abbr>.\n\n[the page](http\\://example.com/w)\n', 3),
        ):
            with self.subTest(data=data):
                (warning,) = self.warnings(with_files("references/a.md", data=data))
                self.assertIn("http://", warning.message)
                self.assertEqual(warning.line, line)
        # Without its ";", Markdown leaves a character reference as text, so this is no link.
        self.assertEqual(self.warnings(with_files("references/a.md", data=b"[the page](&#104ttp://example.com/z)\n")), [])
        for line in (b"[x]: <javascript:run()>", b"[x](<javascript:run()>)", b"[x](&#106;avascript:run())"):
            with self.subTest(line=line):
                (warning,) = self.warnings(with_files("references/a.md", data=line + b"\n"))
                self.assertIn("javascript:", warning.message)

    def test_link_schemes_in_prose_do_not_warn(self):
        data = b"The IMDS address is http://169.254.169.254.\nA javascript: URL runs code.\n"
        self.assertEqual(self.warnings(with_files("references/a.md", data=data)), [])

    def test_placeholders_and_comments_do_not_warn(self):
        data = b"Returns { data: <object> | null }\n<!-- REPEAT per queue -->\n<details>more</details>\n"
        self.assertEqual(self.warnings(with_files("references/a.md", data=data)), [])

    def test_script_in_html_or_svg_warns(self):
        rules = dataclasses.replace(RULES, allowed_extensions=RULES.allowed_extensions | {"svg"})
        for path, script in (
            ("assets/report.html", b"<SCRIPT>run()</SCRIPT>"),
            ("assets/diagram.svg", b"<SCRIPT>run()</SCRIPT>"),
            ("assets/diagram.svg", b"<svg:script>run()</svg:script>"),
        ):
            with self.subTest(path=path, script=script):
                findings, _ = sc.check_skill(with_files(path, data=b"<p>ok</p>\n" + script + b"\n"), rules)
                self.assertEqual([f for f in findings if f.severity == "error"], [])
                (warning,) = [f for f in findings if f.severity == "warning"]
                self.assertIn("<script> element", warning.message)
                self.assertEqual(warning.line, 2)
        self.assertEqual(self.warnings(with_files("assets/report.html", data=b"<p>no scripts</p>\n")), [])


class AddedContentTests(unittest.TestCase):
    def test_internal_names_on_added_lines_warn(self):
        base = with_files("evals/journal.json", data=b'{"role": "ops"}\n')
        head = with_files("evals/journal.json", data=b'{"role": "ops"}\n{"role": "ops-Rivendell"}\nsee https://w.x.intra.example/p\n')
        (warning,) = sc.check_added_content(base, head, RULES)
        self.assertEqual((warning.path, warning.line), ("evals/journal.json", 2))
        self.assertIn('adds "Rivendell"', warning.message)
        self.assertIn("1 more line(s)", warning.message)

    def test_names_already_on_the_base_branch_do_not_warn(self):
        data = b"host: build.corp.example\n"
        base = with_files("references/a.md", data=data)
        self.assertEqual(sc.check_added_content(base, with_files("references/a.md", data=data), RULES), [])
        shifted = with_files("references/a.md", data=b"intro\n" + data)
        self.assertEqual(sc.check_added_content(base, shifted, RULES), [])
        moved = tree(skill_md(), **{"references/b.md": data})
        self.assertEqual(sc.check_added_content(base, moved, RULES), [])

    def test_lines_are_numbered_at_newlines_only(self):
        data = "one\x0ctwo\nthree \u2028 four\r\nsee build.corp.example\r\n".encode()
        (warning,) = sc.check_added_content(None, with_files("references/a.md", data=data), RULES)
        self.assertEqual(warning.line, 3)

    def test_a_new_skill_is_scanned_whole(self):
        (warning,) = sc.check_added_content(None, with_files("references/a.md", data=b"ok\nsee Docs.CORP.Example\n"), RULES)
        self.assertIn("Docs.CORP.Example", warning.message)

    def test_lookalikes_do_not_match(self):
        data = b"notcorp.example\nfoo-corp.examples\nrivendellian\ncorp.example.org\nfoo_corp.example\n"
        self.assertEqual(sc.check_added_content(None, with_files("references/a.md", data=data), RULES), [])


class GitattributesTests(unittest.TestCase):
    def test_lines_that_change_archived_bytes_under_skills(self):
        applies = [
            "*.md text eol=crlf",
            "skills/** export-ignore",
            "/skills/x/a.md export-subst",
            "*.json filter=lfs",
            "**/x.md ident",
            "/skills export-ignore",
            "sk*/** ident",
            "*.md\teol=crlf",
            "\\skills/** eol=crlf",  # A backslash escapes the next character.
            "/[s]kills/** export-ignore",
            '"skills/a b/*.md" eol=crlf',
            "skills/**\rexport-ignore",  # Git also splits a line at a carriage return.
            "[\x0bs]kills/** export-ignore",
            "[attr]crlfy text eol=crlf",  # A macro counts where it is defined.
            "[attr]gone export-ignore",
        ]
        ignored = [
            "# comment",
            "",
            "*.png binary",
            "*.md -text",
            "mcp/** export-ignore",
            "/docs/*.md eol=lf",
            "[attr]bin -diff",
            "*.md linguist-documentation",
            "/README.md export-ignore",  # Anchored at the root.
            "/*.md text eol=crlf",
            "!*.md eol=crlf",  # Git ignores negative patterns here.
            '"docs/a b/*.md" eol=crlf',
            "* text=auto",
            "*.md text",
            "*.md eol=lf",
            "*.md crlf=input",
        ]
        for line in applies:
            with self.subTest(line=line):
                self.assertTrue(sc.gitattributes_line_applies_to_skills(line))
        for line in ignored:
            with self.subTest(line=line):
                self.assertFalse(sc.gitattributes_line_applies_to_skills(line))


def versioned(version: str = "1.0.0", **files: bytes) -> sc.SkillTree:
    fm = VALID_FRONTMATTER.replace('version: "1.0.0"', f'version: "{version}"')
    return tree(skill_md(fm), **files)


class ContentHashTests(unittest.TestCase):
    def test_hash_is_sha256_over_sorted_path_and_file_digest_records(self):
        import hashlib

        files = {"b.md": b"bee\n", "a/c.md": b"sea\n"}
        expected = hashlib.sha256(
            b"a/c.md\0" + hashlib.sha256(b"sea\n").hexdigest().encode() + b"\n"
            + b"b.md\0" + hashlib.sha256(b"bee\n").hexdigest().encode() + b"\n"
        ).hexdigest()
        self.assertEqual(sc.content_hash(files), expected)

    def test_any_byte_or_path_change_changes_the_hash(self):
        base = sc.content_hash({"a.md": b"x"})
        self.assertNotEqual(base, sc.content_hash({"a.md": b"x "}))
        self.assertNotEqual(base, sc.content_hash({"b.md": b"x"}))


class HistoryTests(unittest.TestCase):
    def history(self, base, head, retired=frozenset()) -> list[sc.Finding]:
        return sc.check_history("demo-skill", base, head, RULES, retired)

    def errors(self, base, head, retired=frozenset()) -> list[str]:
        return [f.message for f in self.history(base, head, retired) if f.severity == "error"]

    def test_unchanged_skill_passes(self):
        self.assertEqual(self.history(versioned(), versioned()), [])

    def test_removed_folder_is_an_error(self):
        (message,) = self.errors(versioned(), None)
        self.assertIn('set metadata.deprecated: "true"', message)

    def test_new_skill_passes_unless_its_path_was_retired(self):
        self.assertEqual(self.history(None, versioned()), [])
        (message,) = self.errors(None, versioned(), retired=frozenset({"demo-skill"}))
        self.assertIn("was used by a skill that was removed", message)

    def test_content_change_needs_a_higher_version(self):
        base = versioned("1.0.0", **{"references/a.md": b"one\n"})
        head = versioned("1.0.0", **{"references/a.md": b"two\n"})
        (message,) = self.errors(base, head)
        self.assertIn("metadata.version must go up from 1.0.0", message)
        finding = next(f for f in self.history(base, head) if f.severity == "error")
        self.assertEqual((finding.path, finding.line), ("SKILL.md", 6))

    def test_readme_and_images_changes_need_a_bump(self):
        base = versioned("1.0.0", **{"README.md": b"# Demo\n", "images/a.png": b"1"})
        for changed in ({"README.md": b"# Demo, fixed\n", "images/a.png": b"1"}, {"README.md": b"# Demo\n", "images/a.png": b"2"}):
            with self.subTest(changed=sorted(changed)):
                (message,) = self.errors(base, versioned("1.0.0", **changed))
                self.assertIn("metadata.version must go up from 1.0.0", message)

    def test_unpublished_changes_need_no_bump(self):
        base = versioned("1.0.0", **{"CHANGELOG.md": b"a\n", "evals/evals.json": b"{}\n"})
        head = versioned("1.0.0", **{"CHANGELOG.md": b"b\n", "evals/evals.json": b"[]\n", ".skilleval.yaml": b"x\n"})
        self.assertEqual(self.history(base, head), [])

    def test_version_must_never_go_down(self):
        (message,) = self.errors(versioned("1.2.0"), versioned("1.1.9"))
        self.assertIn("went down from 1.2.0 to 1.1.9", message)

    def test_bump_with_changelog_passes(self):
        base = versioned("1.0.0", **{"CHANGELOG.md": b"## 1.0.0\n"})
        head = versioned("1.1.0", **{"CHANGELOG.md": b"## 1.1.0\n## 1.0.0\n"})
        self.assertEqual(self.history(base, head), [])

    def test_bump_without_changelog_change_warns(self):
        base = versioned("1.0.0", **{"CHANGELOG.md": b"## 1.0.0\n"})
        head = versioned("1.0.1", **{"CHANGELOG.md": b"## 1.0.0\n"})
        (finding,) = self.history(base, head)
        self.assertEqual(finding.severity, "warning")
        self.assertIn("CHANGELOG.md", finding.message)

    def test_two_part_base_version_is_compared_as_patch_zero(self):
        self.assertEqual(self.errors(versioned("2.6"), versioned("2.6.1", **{"CHANGELOG.md": b"x\n"})), [])
        (error,) = self.errors(versioned("2.6"), versioned("2.6.0"))
        self.assertIn("must go up from 2.6.0", error)

    def test_unreadable_base_version_skips_the_version_rules_with_a_warning(self):
        for base in (versioned("latest"), tree(b"---\n---\n# Demo\n"), tree(b"---\r\n---\r\n# Demo\r\n")):
            with self.subTest(base=base.entries["SKILL.md"].data[:12]):
                (finding,) = self.history(base, versioned("1.0.0"))
                self.assertEqual(finding.severity, "warning")
                self.assertIn("were not checked", finding.message)

    def test_a_repeated_base_version_is_read_as_pyyaml_reads_it(self):
        base = tree(skill_md(VALID_FRONTMATTER + '  version: "2.0.0"\n'))
        (error,) = self.errors(base, versioned("1.0.1", **{"CHANGELOG.md": b"x\n"}))
        self.assertIn("went down from 2.0.0", error)

    def test_a_very_long_base_version_part_skips_the_version_rules(self):
        (finding,) = self.history(versioned("1." + "9" * 4301 + ".0"), versioned("1.0.0"))
        self.assertEqual(finding.severity, "warning")
        self.assertIn("were not checked", finding.message)

    def test_a_base_copy_is_read_by_pyyaml_alone(self):
        # Rules that came later, such as no "---" inside the frontmatter, don't hide the base version.
        fm = VALID_FRONTMATTER.replace("testing the skill publishing check.", "testing --- the check.")
        base = tree(skill_md(fm))
        (error,) = self.errors(base, versioned("3.0.0", **{"CHANGELOG.md": b"x\n"}))
        self.assertIn("can only go up one step from 1.0.0", error)

    def test_version_goes_up_one_step_at_a_time(self):
        changelog = {"CHANGELOG.md": b"new entry\n"}
        for new in ("3.4.1", "3.5.0", "4.0.0"):
            with self.subTest(new=new):
                self.assertEqual(self.history(versioned("3.4.0"), versioned(new, **changelog)), [])
        for new in ("3.4.2", "3.6.0", "79.5.0", "3.5.1", "4.0.1", "4.1.0"):
            with self.subTest(new=new):
                (message,) = self.errors(versioned("3.4.0"), versioned(new, **changelog))
                self.assertIn("can only go up one step from 3.4.0: to 3.4.1, 3.5.0 or 4.0.0", message)

    def test_new_skill_starts_at_1_0_0(self):
        self.assertEqual(self.history(None, versioned("1.0.0")), [])
        (message,) = self.errors(None, versioned("2.0.0"))
        self.assertIn("a new skill starts at version 1.0.0, not 2.0.0", message)

    def test_a_folder_is_never_removed_even_in_an_emergency(self):
        (finding,) = sc.check_history("demo-skill", versioned(), None, RULES, frozenset())
        self.assertIn("never removed, even in an emergency", finding.message)
        self.assertIn('metadata.deprecated: "true"', finding.message)

    def test_invalid_head_version_is_left_to_check_skill(self):
        self.assertEqual(self.history(versioned("1.0.0"), versioned("1.0")), [])


class ParseVersionTests(unittest.TestCase):
    def test_a_very_long_part_is_rejected_not_a_crash(self):
        self.assertIsNone(sc.parse_version("1." + "9" * 4301 + ".0"))

    def test_only_major_minor_patch_parses(self):
        self.assertEqual(sc.parse_version("1.2.3"), (1, 2, 3))
        self.assertIsNone(sc.parse_version("2.6"))
        self.assertIsNone(sc.parse_version("1.2.3-rc.1"))

    def test_a_merge_base_copy_may_have_two_parts(self):
        self.assertEqual(sc.parse_version("2.6", allow_two_part=True), (2, 6, 0))
        self.assertIsNone(sc.parse_version("1.2.3-rc.1", allow_two_part=True))


class LoadRulesTests(unittest.TestCase):
    def test_repository_rule_files_load(self):
        gitignore = (ROOT / "skills" / ".gitignore").read_text(encoding="utf-8")
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules", gitignore)
        self.assertEqual(
            rules.allowed_extensions,
            frozenset("md txt json yaml yml xml csv tsv html htm png jpg jpeg gif svg webp pdf".split()),
        )
        self.assertIn("evals/", rules.published_excludes)
        self.assertIn("GENERIC", rules.agent_types)
        self.assertIn("Amazon CloudWatch", rules.vocabulary["aws-services"])
        self.assertEqual(rules.aliases["CloudWatch"], "Amazon CloudWatch")
        for value, target in rules.aliases.items():
            self.assertNotIn(value, rules.vocabulary["aws-services"] | rules.vocabulary["technical-domains"])
            self.assertTrue(any(target in values for values in rules.vocabulary.values()), target)


class LoadRulesValidationTests(unittest.TestCase):
    def rules_dir(self, agent_types, vocabulary) -> Path:
        import json
        import tempfile

        target = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, target)
        source = ROOT / ".github" / "scripts" / "skill-rules"
        for name in source.iterdir():
            (target / name.name).write_bytes(name.read_bytes())
        if agent_types is not None:
            (target / "agent-types.json").write_text(json.dumps(agent_types), encoding="utf-8")
        if vocabulary is not None:
            (target / "vocabulary.json").write_text(json.dumps(vocabulary), encoding="utf-8")
        return target

    def test_string_where_a_list_is_expected_fails_closed(self):
        vocabulary = {"values": {"aws-services": "Amazon EKS", "technical-domains": []}, "aliases": {}}
        with self.assertRaisesRegex(ValueError, "list of non-empty strings"):
            sc.load_rules(self.rules_dir(None, vocabulary), "!*.md\n")
        with self.assertRaisesRegex(ValueError, "list of non-empty strings"):
            sc.load_rules(self.rules_dir({"values": "GENERIC"}, None), "!*.md\n")

    def test_aliases_must_map_strings_to_strings(self):
        vocabulary = {"values": {"aws-services": [], "technical-domains": []}, "aliases": {"a": 1}}
        with self.assertRaisesRegex(ValueError, "aliases"):
            sc.load_rules(self.rules_dir(None, vocabulary), "!*.md\n")


class ConformanceTests(unittest.TestCase):
    def write_cases(self, cases) -> Path:
        import tempfile

        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        self.addCleanup(Path(handle.name).unlink)
        with handle:
            handle.write(__import__("json").dumps({"cases": cases}))
        return Path(handle.name)

    def test_repository_cases_give_their_expected_results(self):
        gitignore = (ROOT / "skills" / ".gitignore").read_text(encoding="utf-8")
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules", gitignore)
        cases = sc.load_cases(ROOT / ".github" / "scripts" / "skill-rules" / "conformance-cases.json")
        self.assertEqual(sc.run_conformance(cases, rules), [])

    def test_malformed_case_files_are_rejected(self):
        files = {"SKILL.md": {"text": "x"}}
        bad = {
            "duplicate id": [{"id": "a", "name": "d", "expect": "pass", "files": files}] * 2,
            'needs an "error"': [{"id": "a", "name": "d", "expect": "fail", "files": files}],
            'exactly one of "text" or "base64"': [{"id": "a", "name": "d", "expect": "pass", "files": {"x": {}}}],
            '"expect" must be': [{"id": "a", "name": "d", "expect": "maybe", "files": files}],
            '"base" must be an object': [{"id": "a", "name": "d", "expect": "pass", "base": [], "files": files}],
            '"retired" must be true or false': [{"id": "a", "name": "d", "expect": "pass", "retired": "yes", "files": files}],
            '"files" must be an object': [{"id": "a", "name": "d", "expect": "pass", "files": None}],
        }
        for fragment, cases in bad.items():
            with self.subTest(fragment=fragment):
                with self.assertRaisesRegex(ValueError, fragment.replace("(", r"\(")):
                    sc.load_cases(self.write_cases(cases))

    def test_malformed_golden_hash_is_rejected(self):
        files = {"SKILL.md": {"text": "x"}}
        bad = {
            "content_hash object": {"files": files},
            "content_hash.files is malformed": {"files": {"SKILL.md": {}}, "sha256": "0" * 64},
        }
        for fragment, golden in bad.items():
            with self.subTest(fragment=fragment):
                path = self.write_cases([])
                path.write_text(json.dumps({"cases": [], "content_hash": golden}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, fragment):
                    sc.load_golden_hash(path)

    def test_wrong_expectation_is_reported(self):
        case = {"id": "a", "name": "demo-skill", "expect": "fail", "error": "nope", "files": {"SKILL.md": {"text": skill_md().decode()}}}
        problems = sc.run_conformance([case], RULES)
        self.assertEqual(len(problems), 1)
        self.assertIn("expected an error containing 'nope', got: no errors", problems[0])


class GitignoreAllowlistTests(unittest.TestCase):
    def test_reads_extension_lines_only(self):
        text = "*\n!*/\n!.gitignore\n# comment\n!*.md\n!*.PNG\n**/scripts/\n"
        self.assertEqual(sc.allowed_extensions_from_gitignore(text), frozenset({"md", "png"}))

    def test_empty_allowlist_fails_closed(self):
        with self.assertRaises(ValueError):
            sc.allowed_extensions_from_gitignore("*\n")


if __name__ == "__main__":
    unittest.main()
